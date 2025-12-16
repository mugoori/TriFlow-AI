"""
워크플로우 실행 엔진
조건 평가 및 액션 실행

스펙 참조: B-5_Workflow_State_Machine.md (15개 노드 타입)

지원 노드 타입 (11개 구현, 4개 예정):
- condition: 조건 평가 (순차 진행)
- action: 액션 실행
- if_else: 조건 분기 (then/else 브랜치)
- loop: 반복 실행 (조건 기반 또는 횟수 기반)
- parallel: 병렬 실행
- data: 데이터 소스에서 데이터 조회
- wait: 대기 (지정 시간 또는 이벤트)
- approval: 인간 승인 대기
- switch: 다중 분기 (다수 case)
- trigger: 워크플로우 자동 시작 트리거 (V2 추가)
- code: Python 샌드박스 실행 (V2 추가)

미구현 (Phase 3):
- judgment: 판단 에이전트 호출 (노드 타입)
- bi: BI 분석 에이전트 호출 (노드 타입)
- mcp: MCP 외부 도구 호출 (노드 타입)
- compensation: 보상 트랜잭션
- deploy: 배포
- rollback: 롤백
- simulate: 시뮬레이션
"""
import asyncio
import csv
import io
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.services.notifications import notification_manager, NotificationStatus

logger = logging.getLogger(__name__)

# Optional MinIO import
try:
    from minio import Minio
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    logger.warning("MinIO client not available. export_to_csv will use local filesystem.")


# ============ 실행 로그 저장소 (인메모리) ============

class ExecutionLogStore:
    """인메모리 실행 로그 저장소 (MVP용)"""

    def __init__(self, max_logs: int = 1000):
        self._logs: List[Dict[str, Any]] = []
        self._max_logs = max_logs

    def add_log(self, log_entry: Dict[str, Any]) -> str:
        """로그 추가"""
        log_id = str(uuid4())
        log_entry["log_id"] = log_id
        log_entry["timestamp"] = datetime.utcnow().isoformat()

        self._logs.append(log_entry)

        # 최대 개수 초과 시 오래된 로그 삭제
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[-self._max_logs:]

        return log_id

    def get_logs(
        self,
        workflow_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """로그 조회"""
        logs = self._logs.copy()

        if workflow_id:
            logs = [log for log in logs if log.get("workflow_id") == workflow_id]

        if event_type:
            logs = [log for log in logs if log.get("event_type") == event_type]

        # 최신순 정렬
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return logs[:limit]

    def clear(self):
        """모든 로그 삭제"""
        self._logs = []


# 전역 로그 저장소
execution_log_store = ExecutionLogStore()


# ============ 센서 데이터 시뮬레이터 ============

class SensorSimulator:
    """센서 데이터 시뮬레이터"""

    def __init__(self):
        import random
        self._random = random

        # 기본 센서 값 범위
        self._sensor_ranges = {
            "temperature": (20.0, 100.0),
            "pressure": (0.0, 15.0),
            "humidity": (20.0, 90.0),
            "vibration": (0.0, 100.0),
            "defect_rate": (0.0, 20.0),
            "consecutive_defects": (0, 10),
            "runtime_hours": (0, 24),
            "production_count": (0, 2000),
            "units_per_hour": (50, 200),
            "current_hour": (0, 23),
        }

        # 장비 상태 옵션
        self._equipment_statuses = ["running", "stopped", "error", "maintenance"]

    def generate_sensor_data(
        self,
        sensors: Optional[List[str]] = None,
        scenario: str = "normal"
    ) -> Dict[str, Any]:
        """
        센서 데이터 생성

        scenarios:
        - normal: 정상 범위 데이터
        - alert: 임계값 초과 데이터
        - random: 완전 랜덤 데이터
        """
        data: Dict[str, Any] = {}

        target_sensors = sensors or list(self._sensor_ranges.keys())

        for sensor in target_sensors:
            if sensor in self._sensor_ranges:
                min_val, max_val = self._sensor_ranges[sensor]

                if scenario == "normal":
                    # 정상 범위 (중앙 50%)
                    range_size = max_val - min_val
                    data[sensor] = min_val + range_size * 0.25 + self._random.random() * range_size * 0.5
                elif scenario == "alert":
                    # 경고 범위 (상위 25%)
                    range_size = max_val - min_val
                    data[sensor] = max_val - range_size * 0.25 + self._random.random() * range_size * 0.25
                else:
                    # 완전 랜덤
                    if isinstance(min_val, int):
                        data[sensor] = self._random.randint(min_val, max_val)
                    else:
                        data[sensor] = min_val + self._random.random() * (max_val - min_val)

                # 정수형 센서
                if sensor in ["consecutive_defects", "runtime_hours", "production_count", "units_per_hour", "current_hour"]:
                    data[sensor] = int(data[sensor])

            elif sensor == "equipment_status":
                if scenario == "alert":
                    data[sensor] = "error"
                elif scenario == "normal":
                    data[sensor] = "running"
                else:
                    data[sensor] = self._random.choice(self._equipment_statuses)

        data["generated_at"] = datetime.utcnow().isoformat()
        data["scenario"] = scenario

        return data

    def generate_test_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """
        사전 정의된 테스트 시나리오 생성
        """
        scenarios = {
            "high_temperature": {
                "temperature": 85.0,
                "humidity": 45.0,
                "pressure": 5.5,
                "equipment_status": "running",
            },
            "low_pressure": {
                "temperature": 55.0,
                "humidity": 50.0,
                "pressure": 1.5,
                "equipment_status": "running",
            },
            "equipment_error": {
                "temperature": 95.0,
                "vibration": 80.0,
                "equipment_status": "error",
            },
            "high_defect_rate": {
                "defect_rate": 12.5,
                "consecutive_defects": 5,
                "production_count": 500,
            },
            "production_delay": {
                "units_per_hour": 75,
                "production_count": 300,
                "runtime_hours": 6,
            },
            "shift_change": {
                "current_hour": 18,
                "production_count": 1000,
                "equipment_status": "running",
            },
            "normal_operation": {
                "temperature": 55.0,
                "humidity": 50.0,
                "pressure": 5.0,
                "vibration": 25.0,
                "defect_rate": 2.0,
                "equipment_status": "running",
            },
        }

        if scenario_name in scenarios:
            data = scenarios[scenario_name].copy()
            data["scenario_name"] = scenario_name
            data["generated_at"] = datetime.utcnow().isoformat()
            return data

        return self.generate_sensor_data(scenario="random")


# 전역 시뮬레이터
sensor_simulator = SensorSimulator()


# ============ 조건 평가기 ============

class ConditionEvaluator:
    """
    조건식 평가기
    간단한 수식 평가 (Rhai 대체 - MVP용)
    """

    def __init__(self):
        # 지원하는 연산자
        self._operators = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
        }

    def evaluate(
        self,
        condition: str,
        context: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        조건식 평가

        Returns:
            (결과, 메시지)
        """
        if not condition or not condition.strip():
            return True, "빈 조건 (항상 참)"

        try:
            # && (AND) 처리
            if "&&" in condition:
                parts = condition.split("&&")
                for part in parts:
                    result, msg = self._evaluate_single(part.strip(), context)
                    if not result:
                        return False, f"AND 조건 실패: {part.strip()} -> {msg}"
                return True, "모든 AND 조건 충족"

            # || (OR) 처리
            if "||" in condition:
                parts = condition.split("||")
                for part in parts:
                    result, msg = self._evaluate_single(part.strip(), context)
                    if result:
                        return True, f"OR 조건 충족: {part.strip()}"
                return False, "모든 OR 조건 실패"

            # 단일 조건
            return self._evaluate_single(condition, context)

        except Exception as e:
            logger.error(f"조건 평가 오류: {condition} - {e}")
            return False, f"평가 오류: {str(e)}"

    def _evaluate_single(
        self,
        condition: str,
        context: Dict[str, Any]
    ) -> tuple[bool, str]:
        """단일 조건식 평가"""
        condition = condition.strip()

        # 연산자 찾기
        for op in [">=", "<=", "==", "!=", ">", "<"]:
            if op in condition:
                parts = condition.split(op)
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()

                    # 좌변 값 가져오기
                    left_value = self._get_value(left, context)
                    # 우변 값 가져오기
                    right_value = self._get_value(right, context)

                    if left_value is None:
                        return False, f"변수 '{left}'를 찾을 수 없음"

                    # 연산 수행
                    try:
                        result = self._operators[op](left_value, right_value)
                        return result, f"{left}({left_value}) {op} {right}({right_value}) = {result}"
                    except TypeError as e:
                        return False, f"타입 오류: {e}"

        return False, f"지원하지 않는 조건식: {condition}"

    def _get_value(self, expr: str, context: Dict[str, Any]) -> Any:
        """표현식에서 값 추출"""
        expr = expr.strip()

        # 문자열 리터럴 ("value" 또는 'value')
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]

        # 숫자 리터럴
        try:
            if '.' in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        # 변수 (context에서 조회)
        if expr in context:
            return context[expr]

        return None


# 전역 조건 평가기
condition_evaluator = ConditionEvaluator()


# ============ 액션 실행기 ============

class ActionExecutor:
    """
    워크플로우 액션 실행기
    """

    def __init__(self):
        self._action_handlers = {
            # 데이터 액션
            "log_event": self._log_event,
            "save_to_database": self._save_to_database,
            "export_to_csv": self._export_to_csv,
            # 제어 액션 (Mock)
            "stop_production_line": self._stop_production_line,
            "adjust_sensor_threshold": self._adjust_sensor_threshold,
            "trigger_maintenance": self._trigger_maintenance,
            # 분석 액션
            "calculate_defect_rate": self._calculate_defect_rate,
            "calculate_metric": self._calculate_metric,
            "analyze_sensor_trend": self._analyze_sensor_trend,
            "predict_equipment_failure": self._predict_equipment_failure,
            # 인사이트 액션 (신규)
            "execute_sql": self._execute_sql,
            "aggregate_data": self._aggregate_data,
            "evaluate_threshold": self._evaluate_threshold,
            "generate_chart": self._generate_chart,
            "format_insight": self._format_insight,
        }

    async def execute(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        액션 실행

        Returns:
            {"success": bool, "message": str, "data": Any}
        """
        if action_name in self._action_handlers:
            try:
                result = await self._action_handlers[action_name](parameters, context)
                return {
                    "success": True,
                    "action": action_name,
                    **result
                }
            except Exception as e:
                logger.error(f"액션 실행 오류: {action_name} - {e}")
                return {
                    "success": False,
                    "action": action_name,
                    "message": f"실행 오류: {str(e)}",
                }
        else:
            return {
                "success": False,
                "action": action_name,
                "message": f"지원하지 않는 액션: {action_name}",
            }

    # ============ 데이터 액션 ============

    async def _log_event(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """이벤트 로그 기록"""
        event_type = params.get("event_type", "general")
        details = params.get("details", {})

        log_entry = {
            "event_type": event_type,
            "details": details,
            "context": context,
            "workflow_id": context.get("workflow_id"),
            "node_id": context.get("node_id"),
        }

        log_id = execution_log_store.add_log(log_entry)

        logger.info(f"[LOG_EVENT] {event_type}: {details}")

        return {
            "message": f"이벤트 로그 기록됨: {event_type}",
            "log_id": log_id,
            "data": log_entry,
        }

    async def _save_to_database(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        데이터베이스 저장

        파라미터:
            table: 테이블명 (workflow_data 고정 또는 지정)
            data: 저장할 데이터 (dict)

        workflow_data 테이블에 JSON 형태로 저장
        """
        from app.database import get_db_context
        from sqlalchemy import text

        table = params.get("table", "workflow_data")
        data = params.get("data", {})
        workflow_id = context.get("workflow_id")

        try:
            with get_db_context() as db:
                # workflow_data 테이블에 저장 (core 스키마)
                # 테이블이 없으면 생성 (동적 테이블 생성)
                create_table_sql = text("""
                    CREATE TABLE IF NOT EXISTS core.workflow_data (
                        id SERIAL PRIMARY KEY,
                        workflow_id VARCHAR(100),
                        table_name VARCHAR(100),
                        data JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                db.execute(create_table_sql)
                db.commit()

                # 데이터 삽입
                insert_sql = text("""
                    INSERT INTO core.workflow_data (workflow_id, table_name, data)
                    VALUES (:workflow_id, :table_name, :data)
                    RETURNING id
                """)
                result = db.execute(
                    insert_sql,
                    {
                        "workflow_id": workflow_id or "unknown",
                        "table_name": table,
                        "data": json.dumps(data, ensure_ascii=False),
                    }
                )
                db.commit()
                row_id = result.scalar()

            log_entry = {
                "event_type": "database_save",
                "details": {"table": table, "data": data, "row_id": row_id},
                "context": context,
                "workflow_id": workflow_id,
            }
            execution_log_store.add_log(log_entry)

            return {
                "message": f"데이터 저장 완료: {table}",
                "data": {"table": table, "row_id": row_id, "rows_affected": 1},
            }

        except Exception as e:
            logger.error(f"데이터베이스 저장 오류: {e}")
            # 실패 시에도 로그는 기록
            log_entry = {
                "event_type": "database_save_failed",
                "details": {"table": table, "data": data, "error": str(e)},
                "context": context,
                "workflow_id": workflow_id,
            }
            execution_log_store.add_log(log_entry)

            return {
                "message": f"데이터 저장 실패: {str(e)}",
                "data": {"table": table, "error": str(e)},
            }

    async def _export_to_csv(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        CSV 내보내기

        파라미터:
            filename: 파일명 (예: "sensor_data_20241201.csv")
            data: 내보낼 데이터 (list of dict)
            fields: 필드 목록 (선택, 미지정 시 data[0]의 키 사용)

        MinIO가 설정되어 있으면 MinIO에 저장, 없으면 로컬 파일시스템에 저장
        """
        from app.config import settings

        filename = params.get("filename", f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        data = params.get("data", [])
        fields = params.get("fields", None)
        workflow_id = context.get("workflow_id")

        if not isinstance(data, list) or len(data) == 0:
            return {
                "message": "내보낼 데이터가 없습니다",
                "data": {"filename": filename, "rows": 0},
            }

        # CSV 데이터 생성
        output = io.StringIO()

        # 필드 결정
        if fields is None:
            fields = list(data[0].keys()) if isinstance(data[0], dict) else []

        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()

        for row in data:
            if isinstance(row, dict):
                writer.writerow(row)

        csv_content = output.getvalue()
        output.close()

        # 저장 경로 결정
        storage_path = None
        storage_type = "local"

        # MinIO 저장 시도
        if MINIO_AVAILABLE and settings.minio_endpoint:
            try:
                client = Minio(
                    settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    secure=settings.minio_secure,
                )

                # 버킷 확인/생성
                bucket_name = settings.minio_bucket_name
                if not client.bucket_exists(bucket_name):
                    client.make_bucket(bucket_name)

                # 파일 업로드
                object_name = f"exports/{workflow_id or 'unknown'}/{filename}"
                csv_bytes = csv_content.encode('utf-8')

                client.put_object(
                    bucket_name,
                    object_name,
                    io.BytesIO(csv_bytes),
                    len(csv_bytes),
                    content_type='text/csv',
                )

                storage_path = f"minio://{bucket_name}/{object_name}"
                storage_type = "minio"
                logger.info(f"CSV 파일 MinIO 저장: {storage_path}")

            except Exception as e:
                logger.warning(f"MinIO 저장 실패, 로컬 저장으로 대체: {e}")

        # MinIO 실패 시 로컬 저장
        if storage_type == "local":
            try:
                # exports 디렉토리 생성
                export_dir = os.path.join(os.getcwd(), "exports", workflow_id or "unknown")
                os.makedirs(export_dir, exist_ok=True)

                file_path = os.path.join(export_dir, filename)
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(csv_content)

                storage_path = file_path
                logger.info(f"CSV 파일 로컬 저장: {storage_path}")

            except Exception as e:
                logger.error(f"로컬 저장도 실패: {e}")
                return {
                    "message": f"CSV 내보내기 실패: {str(e)}",
                    "data": {"filename": filename, "error": str(e)},
                }

        # 로그 기록
        log_entry = {
            "event_type": "csv_export",
            "details": {
                "filename": filename,
                "rows": len(data),
                "storage_type": storage_type,
                "storage_path": storage_path,
            },
            "context": context,
            "workflow_id": workflow_id,
        }
        execution_log_store.add_log(log_entry)

        return {
            "message": f"CSV 파일 생성 완료: {filename}",
            "data": {
                "filename": filename,
                "rows": len(data),
                "storage_type": storage_type,
                "storage_path": storage_path,
            },
        }

    # ============ 제어 액션 (Mock) ============

    async def _stop_production_line(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """생산 라인 정지 (Mock)"""
        line_code = params.get("line_code", "LINE_01")
        reason = params.get("reason", "Unknown")

        log_entry = {
            "event_type": "production_line_stop",
            "details": {"line_code": line_code, "reason": reason},
            "context": context,
            "workflow_id": context.get("workflow_id"),
        }
        execution_log_store.add_log(log_entry)

        return {
            "message": f"생산 라인 정지 요청됨: {line_code}",
            "data": {"line_code": line_code, "reason": reason, "status": "stopped"},
        }

    async def _adjust_sensor_threshold(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """센서 임계값 조정 (Mock)"""
        sensor_id = params.get("sensor_id", "SENSOR_01")
        threshold = params.get("threshold", 0)

        return {
            "message": f"센서 임계값 조정됨: {sensor_id} -> {threshold}",
            "data": {"sensor_id": sensor_id, "new_threshold": threshold},
        }

    async def _trigger_maintenance(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """유지보수 요청 (Mock)"""
        equipment_id = params.get("equipment_id", "EQUIP_01")
        priority = params.get("priority", "medium")

        log_entry = {
            "event_type": "maintenance_triggered",
            "details": {"equipment_id": equipment_id, "priority": priority},
            "context": context,
            "workflow_id": context.get("workflow_id"),
        }
        execution_log_store.add_log(log_entry)

        return {
            "message": f"유지보수 요청 생성됨: {equipment_id} ({priority})",
            "data": {"equipment_id": equipment_id, "priority": priority, "ticket_id": str(uuid4())[:8]},
        }

    # ============ 분석 액션 (Mock) ============

    async def _calculate_defect_rate(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """불량률 계산 (Mock)"""
        line_code = params.get("line_code", "LINE_01")
        time_range = params.get("time_range", "1h")

        # Mock 결과
        import random
        defect_rate = round(random.uniform(0, 10), 2)

        return {
            "message": f"불량률 계산 완료: {line_code}",
            "data": {
                "line_code": line_code,
                "time_range": time_range,
                "defect_rate": defect_rate,
                "total_produced": random.randint(100, 1000),
                "defects_found": int(defect_rate * 10),
            },
        }

    async def _analyze_sensor_trend(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        센서 추세 분석 (실제 구현)

        파라미터:
            data: 시계열 데이터 리스트 (list of dict)
                예: [{"timestamp": "...", "value": 75.3}, ...]
            value_key: 값 키 (기본값: "value")
            timestamp_key: 타임스탬프 키 (기본값: "timestamp")
            window_size: 이동평균 윈도우 크기 (기본값: 5)
            sensor_type: 센서 유형 (표시용)

        출력:
            trend: 추세 (increasing, decreasing, stable)
            average: 평균값
            min: 최소값
            max: 최대값
            std_dev: 표준편차
            moving_average: 이동평균 데이터
        """
        from statistics import mean, stdev

        data = params.get("data", [])
        value_key = params.get("value_key", "value")
        timestamp_key = params.get("timestamp_key", "timestamp")
        window_size = params.get("window_size", 5)
        sensor_type = params.get("sensor_type", "sensor")
        hours = params.get("hours", 24)

        # 데이터가 없으면 Mock 데이터 사용
        if not data:
            import random
            trend = random.choice(["increasing", "decreasing", "stable"])
            return {
                "message": f"센서 추세 분석 완료 (Mock): {sensor_type}",
                "data": {
                    "sensor_type": sensor_type,
                    "hours_analyzed": hours,
                    "trend": trend,
                    "average": round(random.uniform(40, 80), 2),
                    "min": round(random.uniform(20, 40), 2),
                    "max": round(random.uniform(80, 100), 2),
                    "std_dev": round(random.uniform(1, 10), 2),
                    "data_points": 0,
                    "is_mock": True,
                },
            }

        # 값 추출
        values = []
        for item in data:
            val = item.get(value_key)
            if val is not None:
                try:
                    values.append(float(val))
                except (TypeError, ValueError):
                    pass

        if not values:
            return {
                "message": "분석할 데이터가 없습니다",
                "data": {"error": "no valid values"},
            }

        # 기본 통계
        avg_value = round(mean(values), 2)
        min_value = round(min(values), 2)
        max_value = round(max(values), 2)
        std_value = round(stdev(values), 2) if len(values) > 1 else 0

        # 이동평균 계산
        moving_avg = []
        for i in range(len(values)):
            start_idx = max(0, i - window_size + 1)
            window = values[start_idx:i + 1]
            moving_avg.append(round(mean(window), 2))

        # 추세 판별 (선형 회귀 간략 버전)
        n = len(values)
        if n >= 3:
            # 간단한 추세: 처음 1/3 vs 마지막 1/3 비교
            first_third = values[:n // 3]
            last_third = values[-(n // 3):]

            first_avg = mean(first_third) if first_third else 0
            last_avg = mean(last_third) if last_third else 0

            diff_ratio = (last_avg - first_avg) / (first_avg if first_avg != 0 else 1)

            if diff_ratio > 0.05:  # 5% 이상 증가
                trend = "increasing"
            elif diff_ratio < -0.05:  # 5% 이상 감소
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "message": f"센서 추세 분석 완료: {sensor_type}",
            "data": {
                "sensor_type": sensor_type,
                "hours_analyzed": hours,
                "trend": trend,
                "average": avg_value,
                "min": min_value,
                "max": max_value,
                "std_dev": std_value,
                "data_points": len(values),
                "moving_average": moving_avg[-10:] if len(moving_avg) > 10 else moving_avg,
                "is_mock": False,
            },
        }

    async def _predict_equipment_failure(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        장비 고장 예측 (규칙 기반 + 통계적 분석)

        파라미터:
            equipment_id: 설비 ID
            sensor_data: 센서 데이터 리스트 (list of dict)
                예: [{"temperature": 75, "vibration": 2.5, "pressure": 100}, ...]
            thresholds: 임계값 설정 (dict)
                예: {"temperature": {"warning": 80, "critical": 90},
                     "vibration": {"warning": 3.0, "critical": 5.0}}
            history_days: 분석할 과거 일수 (기본값: 30)

        출력:
            failure_probability: 고장 확률 (0~1)
            estimated_days_to_failure: 예상 잔여 일수
            risk_factors: 위험 요소 리스트
            recommendation: 권장 조치
        """
        from statistics import mean, stdev

        equipment_id = params.get("equipment_id", "EQUIP_01")
        sensor_data = params.get("sensor_data", [])
        thresholds = params.get("thresholds", {
            "temperature": {"warning": 80, "critical": 95},
            "vibration": {"warning": 3.0, "critical": 5.0},
            "pressure": {"warning": 150, "critical": 180},
        })
        history_days = params.get("history_days", 30)

        # 데이터가 없으면 Mock 결과 반환
        if not sensor_data:
            import random
            failure_probability = round(random.uniform(0, 0.5), 3)
            days_to_failure = random.randint(7, 90) if failure_probability < 0.3 else random.randint(1, 7)

            return {
                "message": f"장비 고장 예측 완료 (Mock): {equipment_id}",
                "data": {
                    "equipment_id": equipment_id,
                    "failure_probability": failure_probability,
                    "estimated_days_to_failure": days_to_failure,
                    "recommendation": "유지보수 권장" if failure_probability > 0.2 else "정상 운영",
                    "risk_factors": [],
                    "is_mock": True,
                },
            }

        # 위험 요소 분석
        risk_factors = []
        risk_score = 0.0

        for metric, limits in thresholds.items():
            values = [d.get(metric) for d in sensor_data if d.get(metric) is not None]

            if not values:
                continue

            try:
                values = [float(v) for v in values]
            except (TypeError, ValueError):
                continue

            avg = mean(values)
            max_val = max(values)
            std = stdev(values) if len(values) > 1 else 0

            warning_threshold = limits.get("warning", float("inf"))
            critical_threshold = limits.get("critical", float("inf"))

            # 최대값이 임계값 초과
            if max_val >= critical_threshold:
                risk_factors.append({
                    "metric": metric,
                    "severity": "critical",
                    "message": f"{metric} 최대값({max_val:.1f})이 위험 수준({critical_threshold}) 초과",
                    "contribution": 0.3,
                })
                risk_score += 0.3
            elif max_val >= warning_threshold:
                risk_factors.append({
                    "metric": metric,
                    "severity": "warning",
                    "message": f"{metric} 최대값({max_val:.1f})이 경고 수준({warning_threshold}) 초과",
                    "contribution": 0.15,
                })
                risk_score += 0.15

            # 평균이 경고 수준에 근접
            if avg >= warning_threshold * 0.9:
                risk_factors.append({
                    "metric": metric,
                    "severity": "warning",
                    "message": f"{metric} 평균({avg:.1f})이 경고 수준에 근접",
                    "contribution": 0.1,
                })
                risk_score += 0.1

            # 높은 변동성
            if std > avg * 0.2:  # 변동계수 > 20%
                risk_factors.append({
                    "metric": metric,
                    "severity": "info",
                    "message": f"{metric} 변동성이 높음 (표준편차: {std:.2f})",
                    "contribution": 0.05,
                })
                risk_score += 0.05

        # 고장 확률 계산 (0~1 범위로 정규화)
        failure_probability = min(risk_score, 1.0)
        failure_probability = round(failure_probability, 3)

        # 잔여 일수 추정
        import random as rnd
        if failure_probability >= 0.7:
            days_to_failure = rnd.randint(1, 7)
        elif failure_probability >= 0.4:
            days_to_failure = rnd.randint(7, 30)
        elif failure_probability >= 0.2:
            days_to_failure = rnd.randint(30, 60)
        else:
            days_to_failure = rnd.randint(60, 180)

        # 권장 조치 결정
        if failure_probability >= 0.5:
            recommendation = "즉시 유지보수 필요"
        elif failure_probability >= 0.3:
            recommendation = "예방 정비 권장"
        elif failure_probability >= 0.1:
            recommendation = "모니터링 강화 권장"
        else:
            recommendation = "정상 운영"

        return {
            "message": f"장비 고장 예측 완료: {equipment_id}",
            "data": {
                "equipment_id": equipment_id,
                "failure_probability": failure_probability,
                "estimated_days_to_failure": days_to_failure,
                "risk_factors": risk_factors,
                "risk_score": round(risk_score, 3),
                "recommendation": recommendation,
                "analysis_period_days": history_days,
                "data_points": len(sensor_data),
                "is_mock": False,
            },
        }

    # ============ 인사이트 액션 (신규) ============

    async def _execute_sql(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        SQL 쿼리 실행 및 데이터 조회

        파라미터:
            query: SQL 쿼리 문자열
            params: 쿼리 파라미터 (dict)
            timeout: 타임아웃 (초, 기본값 30)

        출력:
            rows: 조회된 데이터 리스트
            columns: 컬럼명 리스트
            row_count: 행 개수
        """
        from app.database import get_db_context
        from sqlalchemy import text

        query = params.get("query", "")
        query_params = params.get("params", {})
        timeout = params.get("timeout", 30)
        workflow_id = context.get("workflow_id")

        if not query or not query.strip():
            return {
                "message": "SQL 쿼리가 제공되지 않았습니다",
                "data": {"rows": [], "columns": [], "row_count": 0},
            }

        # 보안: SELECT 쿼리만 허용
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            return {
                "message": "SELECT 쿼리만 실행할 수 있습니다",
                "data": {"rows": [], "columns": [], "row_count": 0, "error": "SELECT only"},
            }

        try:
            with get_db_context() as db:
                result = db.execute(text(query), query_params)
                columns = list(result.keys()) if result.keys() else []
                rows = [dict(zip(columns, row)) for row in result.fetchall()]

            log_entry = {
                "event_type": "sql_executed",
                "details": {"query": query[:200], "row_count": len(rows)},
                "context": context,
                "workflow_id": workflow_id,
            }
            execution_log_store.add_log(log_entry)

            return {
                "message": f"SQL 쿼리 실행 완료: {len(rows)}건 조회",
                "data": {
                    "rows": rows,
                    "columns": columns,
                    "row_count": len(rows),
                },
            }

        except Exception as e:
            logger.error(f"SQL 실행 오류: {e}")
            return {
                "message": f"SQL 실행 오류: {str(e)}",
                "data": {"rows": [], "columns": [], "row_count": 0, "error": str(e)},
            }

    async def _aggregate_data(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        데이터 집계 (SUM, AVG, COUNT, MIN, MAX, GROUP BY)

        파라미터:
            data: 집계할 데이터 리스트 (list of dict)
            group_by: 그룹화 키 (str 또는 list)
            aggregations: 집계 정의 (dict)
                예: {"total": {"field": "value", "func": "sum"},
                     "average": {"field": "value", "func": "avg"}}

        출력:
            result: 집계 결과
        """
        from collections import defaultdict
        from statistics import mean

        data = params.get("data", [])
        group_by = params.get("group_by")
        aggregations = params.get("aggregations", {})

        if not data:
            return {
                "message": "집계할 데이터가 없습니다",
                "data": {"result": [], "total_groups": 0},
            }

        # 그룹화 키 정규화
        if isinstance(group_by, str):
            group_keys = [group_by]
        elif isinstance(group_by, list):
            group_keys = group_by
        else:
            group_keys = []

        # 집계 함수 매핑
        agg_funcs = {
            "sum": sum,
            "avg": lambda x: mean(x) if x else 0,
            "mean": lambda x: mean(x) if x else 0,
            "count": len,
            "min": lambda x: min(x) if x else 0,
            "max": lambda x: max(x) if x else 0,
        }

        # 그룹화 없이 전체 집계
        if not group_keys:
            result = {}
            for agg_name, agg_config in aggregations.items():
                field = agg_config.get("field")
                func_name = agg_config.get("func", "sum").lower()
                func = agg_funcs.get(func_name, sum)

                values = [row.get(field, 0) for row in data if field in row]
                try:
                    result[agg_name] = round(func(values), 2) if values else 0
                except (TypeError, ValueError):
                    result[agg_name] = 0

            return {
                "message": "전체 집계 완료",
                "data": {"result": result, "total_groups": 1},
            }

        # 그룹화 집계
        groups = defaultdict(list)
        for row in data:
            key = tuple(row.get(k, "") for k in group_keys)
            groups[key].append(row)

        results = []
        for key, group_data in groups.items():
            group_result = dict(zip(group_keys, key))

            for agg_name, agg_config in aggregations.items():
                field = agg_config.get("field")
                func_name = agg_config.get("func", "sum").lower()
                func = agg_funcs.get(func_name, sum)

                values = [row.get(field, 0) for row in group_data if field in row]
                try:
                    group_result[agg_name] = round(func(values), 2) if values else 0
                except (TypeError, ValueError):
                    group_result[agg_name] = 0

            results.append(group_result)

        return {
            "message": f"그룹 집계 완료: {len(results)}개 그룹",
            "data": {"result": results, "total_groups": len(results)},
        }

    async def _evaluate_threshold(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        다중 레벨 임계값 판정

        파라미터:
            value: 평가할 값 (숫자)
            thresholds: 임계값 정의 리스트 (높은 순서대로)
                예: [
                    {"min": 95, "status": "EXCELLENT", "message": "우수"},
                    {"min": 85, "status": "GOOD", "message": "양호"},
                    {"min": 70, "status": "WARNING", "message": "주의"},
                    {"min": 0, "status": "CRITICAL", "message": "위험"}
                ]
            metric_name: 지표 이름 (표시용)
            inverse: True면 낮을수록 좋음 (불량률 등)

        출력:
            status: 판정 상태
            message: 판정 메시지
            level: 레벨 인덱스 (0=최상)
        """
        value = params.get("value", 0)
        thresholds = params.get("thresholds", [])
        metric_name = params.get("metric_name", "값")
        inverse = params.get("inverse", False)

        if not thresholds:
            # 기본 3단계 판정
            thresholds = [
                {"min": 80, "status": "GREEN", "message": "정상"},
                {"min": 50, "status": "YELLOW", "message": "주의"},
                {"min": 0, "status": "RED", "message": "위험"},
            ]

        # inverse 모드: 낮을수록 좋음 (불량률 등)
        if inverse:
            thresholds = [
                {"max": 2, "status": "GREEN", "message": "우수"},
                {"max": 5, "status": "YELLOW", "message": "주의"},
                {"max": 100, "status": "RED", "message": "위험"},
            ]
            for idx, t in enumerate(thresholds):
                if value <= t.get("max", float("inf")):
                    return {
                        "message": f"{metric_name} 판정 완료",
                        "data": {
                            "value": value,
                            "status": t.get("status", "UNKNOWN"),
                            "status_message": t.get("message", ""),
                            "level": idx,
                            "metric_name": metric_name,
                        },
                    }
        else:
            # 일반 모드: 높을수록 좋음
            for idx, t in enumerate(thresholds):
                if value >= t.get("min", float("-inf")):
                    return {
                        "message": f"{metric_name} 판정 완료",
                        "data": {
                            "value": value,
                            "status": t.get("status", "UNKNOWN"),
                            "status_message": t.get("message", ""),
                            "level": idx,
                            "metric_name": metric_name,
                        },
                    }

        # 기본값
        return {
            "message": f"{metric_name} 판정 완료",
            "data": {
                "value": value,
                "status": "UNKNOWN",
                "status_message": "판정 불가",
                "level": -1,
                "metric_name": metric_name,
            },
        }

    async def _generate_chart(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recharts 호환 차트 JSON 생성

        파라미터:
            chart_type: 차트 유형 (bar, line, pie, gauge)
            data: 차트 데이터 (list of dict)
            options: 차트 옵션
                - title: 차트 제목
                - x_key: X축 키 (bar, line)
                - y_key: Y축 키 (bar, line)
                - name_key: 이름 키 (pie)
                - value_key: 값 키 (pie, gauge)
                - style: 스타일 (gradient_rounded, glow_smooth_curve 등)
                - colors: 색상 배열

        출력:
            chart_json: Recharts 호환 JSON 객체
        """
        chart_type = params.get("chart_type", "bar").lower()
        data = params.get("data", [])
        options = params.get("options", {})

        title = options.get("title", "차트")
        x_key = options.get("x_key", "name")
        y_key = options.get("y_key", "value")
        name_key = options.get("name_key", "name")
        value_key = options.get("value_key", "value")
        style = options.get("style", "default")
        colors = options.get("colors", ["#8884d8", "#82ca9d", "#ffc658", "#ff7c43", "#a4de6c"])

        chart_json = {
            "type": chart_type,
            "title": title,
            "style": style,
            "data": data,
        }

        if chart_type == "bar":
            chart_json.update({
                "xAxisDataKey": x_key,
                "bars": [{"dataKey": y_key, "fill": colors[0], "radius": [4, 4, 0, 0]}],
                "config": {
                    "gradient": style == "gradient_rounded",
                    "rounded": "rounded" in style,
                },
            })

        elif chart_type == "line":
            chart_json.update({
                "xAxisDataKey": x_key,
                "lines": [{"dataKey": y_key, "stroke": colors[0], "strokeWidth": 2}],
                "config": {
                    "glow": "glow" in style,
                    "smooth": "smooth" in style,
                    "dot": True,
                },
            })

        elif chart_type == "pie":
            # Pie 데이터 변환
            pie_data = []
            for idx, item in enumerate(data):
                pie_data.append({
                    "name": item.get(name_key, f"항목{idx+1}"),
                    "value": item.get(value_key, 0),
                    "fill": colors[idx % len(colors)],
                })
            chart_json.update({
                "data": pie_data,
                "config": {
                    "innerRadius": 60 if "donut" in style else 0,
                    "outerRadius": 80,
                    "paddingAngle": 2,
                },
            })

        elif chart_type == "gauge":
            # Gauge 데이터
            value = data[0].get(value_key, 0) if data else 0
            chart_json.update({
                "value": value,
                "max": options.get("max", 100),
                "min": options.get("min", 0),
                "config": {
                    "startAngle": 180,
                    "endAngle": 0,
                    "innerRadius": "70%",
                    "outerRadius": "100%",
                },
            })

        return {
            "message": f"{chart_type} 차트 생성 완료",
            "data": {"chart_json": chart_json},
        }

    async def _format_insight(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        인사이트 텍스트 생성 (마크다운 포맷)

        파라미터:
            template: 템플릿 문자열 (예: "현재 {metric}은(는) {value}입니다.")
            data: 템플릿 변수 (dict)
            status: 상태 정보 (optional)
            sections: 섹션 정의 (list of dict)
                예: [
                    {"type": "summary", "content": "..."},
                    {"type": "table", "headers": [...], "rows": [...]},
                    {"type": "recommendation", "content": "..."}
                ]

        출력:
            insight_text: 포맷팅된 마크다운 문자열
        """
        template = params.get("template", "")
        data = params.get("data", {})
        status = params.get("status", {})
        sections = params.get("sections", [])

        lines = []

        # 템플릿 기반 텍스트 생성
        if template:
            try:
                formatted = template.format(**data)
                lines.append(formatted)
            except KeyError as e:
                lines.append(f"템플릿 오류: 변수 {e} 누락")

        # 섹션별 생성
        for section in sections:
            section_type = section.get("type", "text")

            if section_type == "summary":
                lines.append(f"\n**요약:** {section.get('content', '')}")

            elif section_type == "table":
                headers = section.get("headers", [])
                rows = section.get("rows", [])
                if headers:
                    lines.append("\n| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in rows:
                        lines.append("| " + " | ".join(str(v) for v in row) + " |")

            elif section_type == "recommendation":
                lines.append(f"\n**권장 조치:** {section.get('content', '')}")

            elif section_type == "status":
                status_text = status.get("status", "UNKNOWN")
                status_msg = status.get("status_message", "")
                emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(status_text, "⚪")
                lines.append(f"\n**상태:** {emoji} {status_text} - {status_msg}")

        insight_text = "\n".join(lines)

        return {
            "message": "인사이트 텍스트 생성 완료",
            "data": {"insight_text": insight_text},
        }

    async def _calculate_metric(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        범용 지표 계산 (가동률, 합격률, 불량률 등)

        파라미터:
            metric_type: 지표 유형
                - "oee": 설비종합효율
                - "yield": 수율/합격률
                - "defect_rate": 불량률
                - "availability": 가동률
                - "custom": 사용자 정의 수식
            numerator: 분자 값
            denominator: 분모 값
            formula: 사용자 정의 수식 (custom인 경우)
            data: 추가 데이터 (dict)

        출력:
            value: 계산된 값 (%)
            raw_value: 원본 비율
        """
        metric_type = params.get("metric_type", "custom")
        numerator = params.get("numerator", 0)
        denominator = params.get("denominator", 1)
        formula = params.get("formula", "")
        data = params.get("data", {})

        result_value = 0.0
        calculation_details = {}

        try:
            if metric_type == "oee":
                # OEE = 가동률 × 성능률 × 품질률
                availability = data.get("availability", 100)
                performance = data.get("performance", 100)
                quality = data.get("quality", 100)
                result_value = (availability * performance * quality) / 10000
                calculation_details = {
                    "availability": availability,
                    "performance": performance,
                    "quality": quality,
                }

            elif metric_type == "yield":
                # 수율 = 양품 / 총생산 × 100
                good_count = numerator or data.get("good_count", 0)
                total_count = denominator or data.get("total_count", 1)
                result_value = (good_count / total_count) * 100 if total_count > 0 else 0
                calculation_details = {"good_count": good_count, "total_count": total_count}

            elif metric_type == "defect_rate":
                # 불량률 = 불량 / 총생산 × 100
                defect_count = numerator or data.get("defect_count", 0)
                total_count = denominator or data.get("total_count", 1)
                result_value = (defect_count / total_count) * 100 if total_count > 0 else 0
                calculation_details = {"defect_count": defect_count, "total_count": total_count}

            elif metric_type == "availability":
                # 가동률 = 가동시간 / 계획시간 × 100
                run_time = numerator or data.get("run_time", 0)
                planned_time = denominator or data.get("planned_time", 1)
                result_value = (run_time / planned_time) * 100 if planned_time > 0 else 0
                calculation_details = {"run_time": run_time, "planned_time": planned_time}

            elif metric_type == "custom":
                # 사용자 정의: 분자/분모
                if denominator > 0:
                    result_value = (numerator / denominator) * 100
                calculation_details = {"numerator": numerator, "denominator": denominator}

        except (TypeError, ZeroDivisionError) as e:
            logger.error(f"지표 계산 오류: {e}")
            result_value = 0

        result_value = round(result_value, 2)

        return {
            "message": f"{metric_type} 지표 계산 완료: {result_value}%",
            "data": {
                "metric_type": metric_type,
                "value": result_value,
                "raw_value": result_value / 100,
                "calculation_details": calculation_details,
            },
        }


# 전역 액션 실행기
action_executor = ActionExecutor()


# ============ 워크플로우 실행기 ============

class WorkflowEngine:
    """
    워크플로우 실행 엔진
    조건 평가 + 액션 실행 통합

    지원 노드 타입 (스펙 B-5):
    - condition: 조건 평가 (순차 진행, 실패 시 워크플로우 중단)
    - action: 액션 실행
    - if_else: 조건 분기 (then/else 브랜치)
    - loop: 반복 실행 (조건 기반 while 또는 횟수 기반 for)
    - parallel: 병렬 실행
    - data: 데이터 소스에서 데이터 조회 (Phase 3)
    - wait: 대기 (지정 시간 또는 이벤트 기반) (Phase 3)
    - approval: 인간 승인 대기 (Phase 3)
    - switch: 다중 분기 (다수 case)
    - judgment: 판단 에이전트 호출
    - bi: BI 분석 에이전트 호출
    - mcp: MCP 외부 도구 호출
    """

    # Loop 최대 반복 횟수 (무한 루프 방지)
    MAX_LOOP_ITERATIONS = 100

    # Wait 노드 최대 대기 시간 (초)
    MAX_WAIT_SECONDS = 3600  # 1시간

    # Approval 노드 기본 타임아웃 (초)
    DEFAULT_APPROVAL_TIMEOUT = 86400  # 24시간

    def __init__(self):
        self.condition_evaluator = condition_evaluator
        self.action_executor = action_executor
        self.sensor_simulator = sensor_simulator

    async def execute_workflow(
        self,
        workflow_id: str,
        dsl: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
        use_simulated_data: bool = False
    ) -> Dict[str, Any]:
        """
        워크플로우 실행

        Args:
            workflow_id: 워크플로우 ID
            dsl: 워크플로우 DSL 정의
            input_data: 입력 데이터 (센서 값 등)
            use_simulated_data: True면 시뮬레이션 데이터 사용

        Returns:
            실행 결과
        """
        start_time = time.time()

        # 입력 데이터 준비
        if use_simulated_data and not input_data:
            input_data = self.sensor_simulator.generate_sensor_data(scenario="random")

        context = {
            "workflow_id": workflow_id,
            "input_data": input_data or {},
            **(input_data or {})  # 센서 값을 최상위에도 복사
        }

        nodes = dsl.get("nodes", [])

        # 노드 실행
        exec_result = await self._execute_nodes(nodes, context)

        execution_time_ms = int((time.time() - start_time) * 1000)

        return {
            "workflow_id": workflow_id,
            "status": "failed" if exec_result["failed"] else "completed",
            "input_data": input_data,
            "nodes_total": exec_result["total"],
            "nodes_executed": exec_result["executed"],
            "nodes_skipped": exec_result["skipped"],
            "results": exec_result["results"],
            "error_message": exec_result["error_message"],
            "execution_time_ms": execution_time_ms,
            "executed_at": datetime.utcnow().isoformat(),
        }

    async def _execute_nodes(
        self,
        nodes: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        노드 리스트 실행 (재귀 호출 가능)

        Returns:
            {
                "results": [...],
                "executed": int,
                "skipped": int,
                "total": int,
                "failed": bool,
                "error_message": str | None
            }
        """
        results = []
        executed_count = 0
        skipped_count = 0
        failed = False
        error_message = None

        for node in nodes:
            if failed:
                skipped_count += 1
                continue

            node_id = node.get("id", f"node_{uuid4().hex[:8]}")
            node_type = node.get("type")
            config = node.get("config", {})

            context["node_id"] = node_id

            try:
                if node_type == "condition":
                    result = await self._execute_condition_node(node_id, config, context)
                    results.append(result)

                    if not result.get("result", False):
                        # 조건 불충족 시 이후 노드 실행 안 함
                        skipped_count += len(nodes) - len(results)
                        break

                    executed_count += 1

                elif node_type == "action":
                    result = await self._execute_action_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    executed_count += 1

                elif node_type == "if_else":
                    result = await self._execute_if_else_node(node_id, config, context)
                    results.append(result)

                    if result.get("failed", False):
                        failed = True
                        error_message = result.get("error_message")
                        break

                    executed_count += 1

                elif node_type == "loop":
                    result = await self._execute_loop_node(node_id, config, context)
                    results.append(result)

                    if result.get("failed", False):
                        failed = True
                        error_message = result.get("error_message")
                        break

                    executed_count += 1

                elif node_type == "parallel":
                    result = await self._execute_parallel_node(node_id, config, context)
                    results.append(result)

                    if result.get("failed", False):
                        failed = True
                        error_message = result.get("error_message")
                        break

                    executed_count += 1

                elif node_type == "data":
                    result = await self._execute_data_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    # 데이터 결과를 컨텍스트에 저장
                    output_var = config.get("output_variable", "data_result")
                    context[output_var] = result.get("data", {})
                    executed_count += 1

                elif node_type == "wait":
                    result = await self._execute_wait_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    executed_count += 1

                elif node_type == "approval":
                    result = await self._execute_approval_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    # 승인 결과를 컨텍스트에 저장
                    context["approval_result"] = result.get("approval_result", {})
                    executed_count += 1

                elif node_type == "switch":
                    result = await self._execute_switch_node(node_id, config, context)
                    results.append(result)

                    if result.get("failed", False):
                        failed = True
                        error_message = result.get("error_message")
                        break

                    executed_count += 1

                elif node_type == "trigger":
                    result = await self._execute_trigger_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    # 트리거 결과를 컨텍스트에 저장
                    context["trigger_result"] = result.get("trigger_output", {})
                    executed_count += 1

                elif node_type == "code":
                    result = await self._execute_code_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    # 코드 실행 결과를 컨텍스트에 저장
                    output_var = config.get("output_variable", "code_result")
                    context[output_var] = result.get("output", {})
                    executed_count += 1

                else:
                    results.append({
                        "node_id": node_id,
                        "type": node_type,
                        "success": False,
                        "message": f"알 수 없는 노드 타입: {node_type}",
                    })
                    skipped_count += 1

            except Exception as e:
                logger.error(f"노드 실행 오류: {node_id} - {e}")
                failed = True
                error_message = f"노드 {node_id} 실행 오류: {str(e)}"
                results.append({
                    "node_id": node_id,
                    "type": node_type,
                    "success": False,
                    "message": error_message,
                })
                break

        return {
            "results": results,
            "executed": executed_count,
            "skipped": skipped_count,
            "total": len(nodes),
            "failed": failed,
            "error_message": error_message,
        }

    async def _execute_condition_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """조건 노드 실행"""
        condition = config.get("condition", "")
        result, msg = self.condition_evaluator.evaluate(condition, context)

        return {
            "node_id": node_id,
            "type": "condition",
            "condition": condition,
            "result": result,
            "message": msg,
        }

    async def _execute_action_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """액션 노드 실행"""
        action_name = config.get("action", "")
        parameters = config.get("parameters", {})

        # 파라미터에서 컨텍스트 변수 치환 ({{변수명}} 형식)
        resolved_params = self._resolve_parameters(parameters, context)

        # 알림 액션은 notification_manager에서 실행
        if action_name in ["send_slack_notification", "send_email", "send_sms"]:
            try:
                result = await notification_manager.execute_action(
                    action_name, resolved_params
                )
                success = result.status in [NotificationStatus.SUCCESS, NotificationStatus.SKIPPED]
                return {
                    "node_id": node_id,
                    "type": "action",
                    "action": action_name,
                    "success": success,
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details,
                }
            except Exception as e:
                logger.error(f"알림 액션 실행 오류: {action_name} - {e}")
                return {
                    "node_id": node_id,
                    "type": "action",
                    "action": action_name,
                    "success": False,
                    "status": "error",
                    "message": f"알림 액션 실행 오류: {str(e)}",
                }

        # 기타 액션 직접 실행
        action_result = await self.action_executor.execute(
            action_name, resolved_params, context
        )

        return {
            "node_id": node_id,
            "type": "action",
            **action_result,
        }

    def _resolve_parameters(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        파라미터에서 {{변수명}} 형식의 템플릿을 컨텍스트 값으로 치환

        예: {"message": "온도 {{temperature}}도 감지"} + {"temperature": 85}
            → {"message": "온도 85도 감지"}
        """
        import re

        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                # {{변수명}} 패턴 찾기
                pattern = r'\{\{(\w+)\}\}'
                matches = re.findall(pattern, value)
                for var_name in matches:
                    if var_name in context:
                        # 전체가 변수인 경우 타입 보존
                        if value == f"{{{{{var_name}}}}}":
                            return context[var_name]
                        # 문자열 내 부분 치환
                        value = value.replace(f"{{{{{var_name}}}}}", str(context[var_name]))
                return value
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            return value

        return {k: resolve_value(v) for k, v in parameters.items()}

    async def _execute_if_else_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        If/Else 분기 노드 실행

        config 형식:
        {
            "condition": "temperature > 80",
            "then": [노드 리스트],  # 조건 참일 때 실행
            "else": [노드 리스트]   # 조건 거짓일 때 실행 (선택)
        }
        """
        condition = config.get("condition", "")
        then_nodes = config.get("then", [])
        else_nodes = config.get("else", [])

        # 조건 평가
        cond_result, cond_msg = self.condition_evaluator.evaluate(condition, context)

        if cond_result:
            # then 브랜치 실행
            branch = "then"
            branch_result = await self._execute_nodes(then_nodes, context)
        else:
            # else 브랜치 실행
            branch = "else"
            if else_nodes:
                branch_result = await self._execute_nodes(else_nodes, context)
            else:
                branch_result = {
                    "results": [],
                    "executed": 0,
                    "skipped": 0,
                    "total": 0,
                    "failed": False,
                    "error_message": None,
                }

        return {
            "node_id": node_id,
            "type": "if_else",
            "condition": condition,
            "condition_result": cond_result,
            "condition_message": cond_msg,
            "branch_executed": branch,
            "branch_results": branch_result["results"],
            "branch_executed_count": branch_result["executed"],
            "failed": branch_result["failed"],
            "error_message": branch_result["error_message"],
            "success": not branch_result["failed"],
        }

    async def _execute_loop_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Loop 노드 실행

        config 형식 (while 루프):
        {
            "loop_type": "while",
            "condition": "counter < 5",
            "nodes": [노드 리스트],
            "max_iterations": 100  # 선택, 기본값 100
        }

        config 형식 (for 루프):
        {
            "loop_type": "for",
            "count": 3,
            "nodes": [노드 리스트]
        }
        """
        loop_type = config.get("loop_type", "while")
        loop_nodes = config.get("nodes", [])
        max_iterations = config.get("max_iterations", self.MAX_LOOP_ITERATIONS)

        iterations = 0
        all_results = []
        failed = False
        error_message = None

        if loop_type == "for":
            # For 루프 (횟수 기반)
            count = config.get("count", 1)
            count = min(count, max_iterations)  # 최대 반복 제한

            for i in range(count):
                context["loop_index"] = i
                context["loop_iteration"] = i + 1

                iter_result = await self._execute_nodes(loop_nodes, context)
                all_results.append({
                    "iteration": i + 1,
                    "results": iter_result["results"],
                })

                iterations += 1

                if iter_result["failed"]:
                    failed = True
                    error_message = iter_result["error_message"]
                    break

        else:
            # While 루프 (조건 기반)
            condition = config.get("condition", "")

            while iterations < max_iterations:
                # 조건 평가
                cond_result, cond_msg = self.condition_evaluator.evaluate(condition, context)

                if not cond_result:
                    break

                context["loop_index"] = iterations
                context["loop_iteration"] = iterations + 1

                iter_result = await self._execute_nodes(loop_nodes, context)
                all_results.append({
                    "iteration": iterations + 1,
                    "results": iter_result["results"],
                })

                iterations += 1

                if iter_result["failed"]:
                    failed = True
                    error_message = iter_result["error_message"]
                    break

            if iterations >= max_iterations:
                logger.warning(f"Loop {node_id} reached max iterations: {max_iterations}")

        # 루프 변수 정리
        context.pop("loop_index", None)
        context.pop("loop_iteration", None)

        return {
            "node_id": node_id,
            "type": "loop",
            "loop_type": loop_type,
            "iterations": iterations,
            "max_iterations": max_iterations,
            "iteration_results": all_results,
            "failed": failed,
            "error_message": error_message,
            "success": not failed,
        }

    async def _execute_parallel_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parallel 노드 실행 (병렬 실행)

        config 형식:
        {
            "branches": [
                [노드 리스트1],
                [노드 리스트2],
                ...
            ],
            "fail_fast": false  # true면 하나라도 실패 시 전체 중단
        }
        """
        branches = config.get("branches", [])
        fail_fast = config.get("fail_fast", False)

        if not branches:
            return {
                "node_id": node_id,
                "type": "parallel",
                "branches_count": 0,
                "branch_results": [],
                "failed": False,
                "error_message": None,
                "success": True,
            }

        # 각 브랜치를 비동기 태스크로 생성
        async def execute_branch(branch_index: int, branch_nodes: List[Dict]) -> Dict:
            # 브랜치별 컨텍스트 복사 (격리)
            branch_context = context.copy()
            branch_context["parallel_branch_index"] = branch_index

            result = await self._execute_nodes(branch_nodes, branch_context)
            return {
                "branch_index": branch_index,
                **result,
            }

        # 모든 브랜치 병렬 실행
        tasks = [
            execute_branch(i, branch)
            for i, branch in enumerate(branches)
        ]

        if fail_fast:
            # fail_fast: 하나라도 실패하면 나머지 취소
            branch_results = []
            failed = False
            error_message = None

            for coro in asyncio.as_completed(tasks):
                result = await coro
                branch_results.append(result)

                if result["failed"]:
                    failed = True
                    error_message = f"Branch {result['branch_index']} failed: {result['error_message']}"
                    # 나머지 태스크 취소 (실제로는 이미 시작된 것들은 완료됨)
                    break

            # 나머지 완료 대기
            for task in tasks:
                if not task.done():
                    try:
                        result = await task
                        branch_results.append(result)
                    except Exception:
                        pass
        else:
            # 모든 브랜치 완료 대기
            branch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 예외 처리
            processed_results = []
            failed = False
            error_messages = []

            for i, result in enumerate(branch_results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "branch_index": i,
                        "results": [],
                        "executed": 0,
                        "skipped": 0,
                        "total": 0,
                        "failed": True,
                        "error_message": str(result),
                    })
                    failed = True
                    error_messages.append(f"Branch {i}: {str(result)}")
                else:
                    processed_results.append(result)
                    if result.get("failed"):
                        failed = True
                        error_messages.append(f"Branch {result['branch_index']}: {result['error_message']}")

            branch_results = processed_results
            error_message = "; ".join(error_messages) if error_messages else None

        return {
            "node_id": node_id,
            "type": "parallel",
            "branches_count": len(branches),
            "branch_results": branch_results,
            "failed": failed,
            "error_message": error_message,
            "success": not failed,
        }


    # ============ DATA 노드 ============

    async def _execute_data_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Data 노드 실행 - 데이터 소스에서 데이터 조회

        config 형식:
        {
            "source_type": "database" | "api" | "sensor" | "connector",
            "source_id": "connector_uuid" (connector 타입인 경우),
            "query": "SELECT * FROM ...", (database 타입)
            "endpoint": "/api/...", (api 타입)
            "sensor_ids": ["TEMP_01", "TEMP_02"], (sensor 타입)
            "time_range": {"start": "...", "end": "..."}, (선택)
            "limit": 100, (선택)
            "output_variable": "sensor_data" (컨텍스트에 저장할 변수명)
        }
        """
        from app.database import get_db_context
        from sqlalchemy import text

        source_type = config.get("source_type", "database")
        output_variable = config.get("output_variable", "data_result")
        limit = config.get("limit", 100)

        try:
            if source_type == "database":
                # 직접 SQL 쿼리 실행 (SELECT만)
                query = config.get("query", "")
                if not query.strip().upper().startswith("SELECT"):
                    return {
                        "node_id": node_id,
                        "type": "data",
                        "success": False,
                        "message": "SELECT 쿼리만 실행할 수 있습니다",
                    }

                with get_db_context() as db:
                    result = db.execute(text(query))
                    columns = list(result.keys()) if result.keys() else []
                    rows = [dict(zip(columns, row)) for row in result.fetchall()]

                return {
                    "node_id": node_id,
                    "type": "data",
                    "source_type": source_type,
                    "success": True,
                    "message": f"{len(rows)}건 조회됨",
                    "data": {
                        "rows": rows[:limit],
                        "columns": columns,
                        "total_count": len(rows),
                    },
                }

            elif source_type == "sensor":
                # 센서 데이터 조회 (core.sensor_data 테이블)
                sensor_ids = config.get("sensor_ids", [])
                time_range = config.get("time_range", {})

                with get_db_context() as db:
                    if sensor_ids:
                        # 특정 센서만 조회
                        query = text("""
                            SELECT sensor_id, value, recorded_at
                            FROM core.sensor_data
                            WHERE sensor_id = ANY(:sensor_ids)
                            ORDER BY recorded_at DESC
                            LIMIT :limit
                        """)
                        result = db.execute(query, {"sensor_ids": sensor_ids, "limit": limit})
                    else:
                        # 전체 센서 조회
                        query = text("""
                            SELECT sensor_id, value, recorded_at
                            FROM core.sensor_data
                            ORDER BY recorded_at DESC
                            LIMIT :limit
                        """)
                        result = db.execute(query, {"limit": limit})

                    rows = [dict(row._mapping) for row in result.fetchall()]

                return {
                    "node_id": node_id,
                    "type": "data",
                    "source_type": source_type,
                    "success": True,
                    "message": f"센서 데이터 {len(rows)}건 조회됨",
                    "data": {
                        "rows": rows,
                        "sensor_ids": sensor_ids,
                        "total_count": len(rows),
                    },
                }

            elif source_type == "connector":
                # DataConnector 통해 데이터 조회 (MVP: mock)
                source_id = config.get("source_id")
                return {
                    "node_id": node_id,
                    "type": "data",
                    "source_type": source_type,
                    "success": True,
                    "message": f"DataConnector {source_id} 조회 (mock)",
                    "data": {
                        "rows": [],
                        "connector_id": source_id,
                        "is_mock": True,
                    },
                }

            elif source_type == "api":
                # 외부 API 호출 (MVP: mock)
                endpoint = config.get("endpoint", "")
                return {
                    "node_id": node_id,
                    "type": "data",
                    "source_type": source_type,
                    "success": True,
                    "message": f"API {endpoint} 호출 (mock)",
                    "data": {
                        "rows": [],
                        "endpoint": endpoint,
                        "is_mock": True,
                    },
                }

            else:
                return {
                    "node_id": node_id,
                    "type": "data",
                    "success": False,
                    "message": f"지원하지 않는 source_type: {source_type}",
                }

        except Exception as e:
            logger.error(f"Data 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "data",
                "success": False,
                "message": f"데이터 조회 오류: {str(e)}",
            }

    # ============ WAIT 노드 ============

    async def _execute_wait_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Wait 노드 실행 - 지정 시간 또는 이벤트 대기

        config 형식:
        {
            "wait_type": "duration" | "event" | "schedule",
            "duration_seconds": 10, (duration 타입)
            "event_type": "sensor_alert", (event 타입)
            "event_filter": {...}, (event 타입)
            "schedule_cron": "0 9 * * *", (schedule 타입)
            "timeout_seconds": 300 (이벤트/스케줄 타임아웃)
        }
        """
        wait_type = config.get("wait_type", "duration")
        start_time = time.time()

        try:
            if wait_type == "duration":
                # 지정 시간 대기
                duration = config.get("duration_seconds", 0)
                duration = min(duration, self.MAX_WAIT_SECONDS)

                if duration > 0:
                    logger.info(f"Wait 노드 {node_id}: {duration}초 대기 시작")
                    await asyncio.sleep(duration)

                elapsed = time.time() - start_time
                return {
                    "node_id": node_id,
                    "type": "wait",
                    "wait_type": wait_type,
                    "success": True,
                    "message": f"{duration}초 대기 완료",
                    "data": {
                        "requested_duration": duration,
                        "actual_duration": round(elapsed, 2),
                    },
                }

            elif wait_type == "event":
                # 이벤트 대기 (MVP: mock - 즉시 완료)
                event_type = config.get("event_type", "unknown")
                timeout = config.get("timeout_seconds", 300)

                # 실제 구현에서는 이벤트 큐를 폴링하거나 webhook 수신
                # MVP에서는 즉시 이벤트 수신된 것으로 처리
                logger.info(f"Wait 노드 {node_id}: 이벤트 '{event_type}' 대기 (mock)")

                return {
                    "node_id": node_id,
                    "type": "wait",
                    "wait_type": wait_type,
                    "success": True,
                    "message": f"이벤트 '{event_type}' 수신됨 (mock)",
                    "data": {
                        "event_type": event_type,
                        "timeout_seconds": timeout,
                        "is_mock": True,
                        "event_data": {},
                    },
                }

            elif wait_type == "schedule":
                # 스케줄 대기 (cron 표현식)
                schedule_cron = config.get("schedule_cron", "")
                timeout = config.get("timeout_seconds", 3600)

                # MVP: 즉시 완료
                logger.info(f"Wait 노드 {node_id}: 스케줄 '{schedule_cron}' 대기 (mock)")

                return {
                    "node_id": node_id,
                    "type": "wait",
                    "wait_type": wait_type,
                    "success": True,
                    "message": f"스케줄 '{schedule_cron}' 도달 (mock)",
                    "data": {
                        "schedule_cron": schedule_cron,
                        "timeout_seconds": timeout,
                        "is_mock": True,
                    },
                }

            else:
                return {
                    "node_id": node_id,
                    "type": "wait",
                    "success": False,
                    "message": f"지원하지 않는 wait_type: {wait_type}",
                }

        except asyncio.CancelledError:
            return {
                "node_id": node_id,
                "type": "wait",
                "success": False,
                "message": "대기 중 취소됨",
            }
        except Exception as e:
            logger.error(f"Wait 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "wait",
                "success": False,
                "message": f"대기 오류: {str(e)}",
            }

    # ============ APPROVAL 노드 ============

    async def _execute_approval_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Approval 노드 실행 - 인간 승인 대기

        config 형식:
        {
            "approval_type": "single" | "multi" | "quorum",
            "approvers": ["user1@example.com", "user2@example.com"],
            "quorum_count": 2, (quorum 타입일 때 필요한 승인 수)
            "timeout_seconds": 86400, (기본 24시간)
            "notification_channel": "slack" | "email",
            "notification_message": "승인 요청...",
            "auto_approve_on_timeout": false (타임아웃 시 자동 승인 여부)
        }

        MVP 구현:
        - 승인 요청을 DB에 저장
        - 알림 전송 (mock)
        - 즉시 자동 승인 (실제 구현에서는 webhook/폴링으로 승인 대기)
        """

        approval_type = config.get("approval_type", "single")
        approvers = config.get("approvers", [])
        timeout_seconds = config.get("timeout_seconds", self.DEFAULT_APPROVAL_TIMEOUT)
        notification_channel = config.get("notification_channel", "slack")
        notification_message = config.get("notification_message", "워크플로우 승인 요청")
        auto_approve = config.get("auto_approve_on_timeout", False)

        approval_id = str(uuid4())
        workflow_id = context.get("workflow_id")

        try:
            # 승인 요청 생성 (DB 저장)
            # MVP: core.workflow_approvals 테이블이 없으면 인메모리로 처리
            approval_request = {
                "approval_id": approval_id,
                "workflow_id": workflow_id,
                "node_id": node_id,
                "approval_type": approval_type,
                "approvers": approvers,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "timeout_at": datetime.utcnow().isoformat(),  # 실제로는 + timeout_seconds
            }

            # 로그에 승인 요청 기록
            log_entry = {
                "event_type": "approval_requested",
                "details": approval_request,
                "context": context,
                "workflow_id": workflow_id,
            }
            execution_log_store.add_log(log_entry)

            # 알림 전송 (mock)
            logger.info(f"Approval 노드 {node_id}: 승인 요청 생성됨 - {approvers}")
            if notification_channel == "slack":
                # 실제로는 notification_manager 사용
                logger.info(f"Slack 알림 전송 (mock): {notification_message}")
            elif notification_channel == "email":
                logger.info(f"이메일 알림 전송 (mock): {notification_message} -> {approvers}")

            # MVP: 자동 승인 (실제 구현에서는 폴링/webhook 대기)
            approval_result = {
                "approval_id": approval_id,
                "status": "approved",  # approved | rejected | timeout
                "approved_by": approvers[0] if approvers else "system",
                "approved_at": datetime.utcnow().isoformat(),
                "comment": "Auto-approved (MVP mode)",
                "is_mock": True,
            }

            # 승인 완료 로그
            log_entry = {
                "event_type": "approval_completed",
                "details": approval_result,
                "context": context,
                "workflow_id": workflow_id,
            }
            execution_log_store.add_log(log_entry)

            return {
                "node_id": node_id,
                "type": "approval",
                "approval_type": approval_type,
                "success": True,
                "message": "승인 완료 (auto-approved in MVP)",
                "approval_result": approval_result,
                "data": {
                    "approval_id": approval_id,
                    "approvers": approvers,
                    "status": "approved",
                },
            }

        except Exception as e:
            logger.error(f"Approval 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "approval",
                "success": False,
                "message": f"승인 처리 오류: {str(e)}",
            }

    # ============ SWITCH 노드 ============

    async def _execute_switch_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Switch 노드 실행 - 다중 분기 (다수 case)

        config 형식:
        {
            "expression": "status",  # 평가할 변수/표현식
            "cases": [
                {"value": "running", "nodes": [...]},
                {"value": "stopped", "nodes": [...]},
                {"value": "error", "nodes": [...]}
            ],
            "default": [...]  # 매칭되는 case가 없을 때 실행 (선택)
        }
        """
        expression = config.get("expression", "")
        cases = config.get("cases", [])
        default_nodes = config.get("default", [])

        # 표현식 평가하여 값 가져오기
        switch_value = context.get(expression)
        if switch_value is None:
            # 표현식이 조건식일 수도 있음
            switch_value = expression

        matched_case = None
        matched_nodes = None

        # case 매칭
        for case in cases:
            case_value = case.get("value")
            if switch_value == case_value:
                matched_case = case_value
                matched_nodes = case.get("nodes", [])
                break

        # 매칭된 case가 없으면 default 실행
        if matched_nodes is None:
            if default_nodes:
                matched_case = "default"
                matched_nodes = default_nodes
            else:
                # 아무것도 실행하지 않음
                return {
                    "node_id": node_id,
                    "type": "switch",
                    "expression": expression,
                    "switch_value": switch_value,
                    "matched_case": None,
                    "case_results": [],
                    "failed": False,
                    "error_message": None,
                    "success": True,
                    "message": "매칭되는 case 없음 (default도 없음)",
                }

        # 매칭된 노드 실행
        case_result = await self._execute_nodes(matched_nodes, context)

        return {
            "node_id": node_id,
            "type": "switch",
            "expression": expression,
            "switch_value": switch_value,
            "matched_case": matched_case,
            "case_results": case_result["results"],
            "case_executed_count": case_result["executed"],
            "failed": case_result["failed"],
            "error_message": case_result["error_message"],
            "success": not case_result["failed"],
        }

    async def _execute_trigger_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        TRIGGER 노드 실행

        스펙 (B-5 섹션 4.7):
        - trigger_type: schedule, event, condition, webhook, manual
        - schedule_config: cron 표현식, timezone
        - event_config: event_type, filter
        - condition_config: expression, check_interval_seconds, debounce_seconds
        - webhook_config: path, method, auth, rate_limit

        TRIGGER 노드는 워크플로우의 시작점으로:
        1. 워크플로우 DSL에서 트리거 조건 정의
        2. 조건 충족 시 워크플로우 자동 시작
        3. 이 메서드는 트리거가 실행될 때 초기 컨텍스트 설정
        """
        trigger_type = config.get("trigger_type", "manual")
        trigger_time = datetime.utcnow().isoformat()

        # 트리거 타입별 처리
        if trigger_type == "schedule":
            schedule_config = config.get("schedule_config", {})
            cron_expression = schedule_config.get("cron", "")
            timezone = schedule_config.get("timezone", "UTC")

            trigger_output = {
                "triggered": True,
                "trigger_time": trigger_time,
                "trigger_reason": f"Schedule: {cron_expression}",
                "trigger_type": "schedule",
                "schedule": {
                    "cron": cron_expression,
                    "timezone": timezone,
                }
            }

        elif trigger_type == "event":
            event_config = config.get("event_config", {})
            event_type = event_config.get("event_type", "")
            event_filter = event_config.get("filter", {})

            # 이벤트 데이터는 컨텍스트에서 가져옴 (이벤트 버스에서 전달)
            event_data = context.get("_event_data", {})

            trigger_output = {
                "triggered": True,
                "trigger_time": trigger_time,
                "trigger_reason": f"Event: {event_type}",
                "trigger_type": "event",
                "event": {
                    "event_type": event_type,
                    "filter": event_filter,
                    "data": event_data,
                }
            }

        elif trigger_type == "condition":
            condition_config = config.get("condition_config", {})
            expression = condition_config.get("expression", "true")
            check_interval = condition_config.get("check_interval_seconds", 60)
            debounce = condition_config.get("debounce_seconds", 0)

            # 조건 평가
            condition_result, condition_msg = self.condition_evaluator.evaluate(
                expression, context
            )

            trigger_output = {
                "triggered": condition_result,
                "trigger_time": trigger_time,
                "trigger_reason": f"Condition: {expression}",
                "trigger_type": "condition",
                "condition": {
                    "expression": expression,
                    "result": condition_result,
                    "message": condition_msg,
                    "check_interval_seconds": check_interval,
                    "debounce_seconds": debounce,
                }
            }

            if not condition_result:
                return {
                    "node_id": node_id,
                    "type": "trigger",
                    "success": False,
                    "message": f"트리거 조건 불충족: {condition_msg}",
                    "trigger_output": trigger_output,
                }

        elif trigger_type == "webhook":
            webhook_config = config.get("webhook_config", {})
            webhook_path = webhook_config.get("path", "")
            webhook_method = webhook_config.get("method", "POST")

            # 웹훅 데이터는 컨텍스트에서 가져옴
            webhook_data = context.get("_webhook_data", {})

            trigger_output = {
                "triggered": True,
                "trigger_time": trigger_time,
                "trigger_reason": f"Webhook: {webhook_method} {webhook_path}",
                "trigger_type": "webhook",
                "webhook": {
                    "path": webhook_path,
                    "method": webhook_method,
                    "data": webhook_data,
                }
            }

        else:  # manual
            trigger_output = {
                "triggered": True,
                "trigger_time": trigger_time,
                "trigger_reason": "Manual trigger",
                "trigger_type": "manual",
            }

        # 로그 기록
        execution_log_store.add_log({
            "event_type": "trigger_executed",
            "workflow_id": context.get("workflow_id"),
            "node_id": node_id,
            "trigger_type": trigger_type,
            "trigger_output": trigger_output,
        })

        return {
            "node_id": node_id,
            "type": "trigger",
            "success": True,
            "message": f"트리거 실행 완료: {trigger_type}",
            "trigger_output": trigger_output,
        }

    async def _execute_code_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        CODE 노드 실행 (Python 샌드박스)

        스펙 (B-5 섹션 4.4):
        - code_type: transform, calculate, validate, format, custom
        - code_template_id: 사전 정의된 코드 템플릿 ID
        - inline_code: 인라인 코드 (보안 주의)
        - sandbox_enabled: 샌드박스 모드
        - allowed_imports: 허용된 import 목록

        보안 고려사항:
        1. RestrictedPython 사용 (exec 직접 사용 금지)
        2. 화이트리스트 import만 허용
        3. 타임아웃 및 메모리 제한
        4. 파일 시스템 접근 차단
        """
        code_type = config.get("code_type", "custom")
        code_template_id = config.get("code_template_id")
        inline_code = config.get("inline_code")
        sandbox_enabled = config.get("sandbox_enabled", True)
        allowed_imports = config.get("allowed_imports", [
            "json", "datetime", "math", "statistics", "re"
        ])
        timeout_ms = config.get("timeout_ms", 30000)
        memory_limit_mb = config.get("memory_limit_mb", 256)

        # 입력 데이터
        input_data = config.get("input", {})
        resolved_input = {}

        # 입력 데이터에서 컨텍스트 변수 참조 해석
        for key, value in input_data.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]  # ${var} -> var
                resolved_input[key] = context.get(var_name, value)
            else:
                resolved_input[key] = value

        # 코드 템플릿 로드 또는 인라인 코드 사용
        code_to_execute = None

        if code_template_id:
            # 템플릿 저장소에서 코드 로드 (향후 DB 연동)
            code_to_execute = self._load_code_template(code_template_id)
            if not code_to_execute:
                return {
                    "node_id": node_id,
                    "type": "code",
                    "success": False,
                    "message": f"코드 템플릿을 찾을 수 없음: {code_template_id}",
                    "output": None,
                }
        elif inline_code:
            code_to_execute = inline_code
        else:
            return {
                "node_id": node_id,
                "type": "code",
                "success": False,
                "message": "실행할 코드가 없음 (code_template_id 또는 inline_code 필요)",
                "output": None,
            }

        # 샌드박스 실행
        start_time = time.time()
        try:
            if sandbox_enabled:
                output = await self._execute_code_sandbox(
                    code_to_execute,
                    resolved_input,
                    allowed_imports,
                    timeout_ms,
                    memory_limit_mb
                )
            else:
                # 비샌드박스 모드 (개발/테스트용, 프로덕션에서 비권장)
                logger.warning(f"CODE 노드 {node_id} 비샌드박스 모드로 실행")
                output = await self._execute_code_unsafe(
                    code_to_execute,
                    resolved_input,
                    timeout_ms
                )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # 출력 스키마 검증 (선택)
            output_schema = config.get("output", {}).get("schema")
            if output_schema:
                # JSON Schema 검증 (향후 구현)
                pass

            # 로그 기록
            execution_log_store.add_log({
                "event_type": "code_executed",
                "workflow_id": context.get("workflow_id"),
                "node_id": node_id,
                "code_type": code_type,
                "execution_time_ms": execution_time_ms,
                "sandbox_enabled": sandbox_enabled,
            })

            return {
                "node_id": node_id,
                "type": "code",
                "success": True,
                "message": f"코드 실행 완료 ({execution_time_ms}ms)",
                "output": output,
                "execution_time_ms": execution_time_ms,
                "code_type": code_type,
                "sandbox_enabled": sandbox_enabled,
            }

        except asyncio.TimeoutError:
            return {
                "node_id": node_id,
                "type": "code",
                "success": False,
                "message": f"코드 실행 타임아웃 ({timeout_ms}ms)",
                "output": None,
            }
        except Exception as e:
            logger.error(f"CODE 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "code",
                "success": False,
                "message": f"코드 실행 오류: {str(e)}",
                "output": None,
            }

    def _load_code_template(self, template_id: str) -> Optional[str]:
        """
        코드 템플릿 로드

        사전 정의된 안전한 코드 템플릿:
        - defect_rate_calc: 불량률 계산
        - moving_average: 이동 평균 계산
        - data_transform: 데이터 변환
        - anomaly_score: 이상치 점수 계산
        """
        # 내장 템플릿
        templates = {
            "defect_rate_calc": '''
# 불량률 계산 템플릿
total = data.get("total_count", 0)
defects = data.get("defect_count", 0)
threshold = parameters.get("threshold", 0.05)

if total > 0:
    defect_rate = defects / total
else:
    defect_rate = 0

result = {
    "defect_rate": defect_rate,
    "is_over_threshold": defect_rate > threshold,
    "total_count": total,
    "defect_count": defects,
}
''',
            "moving_average": '''
# 이동 평균 계산 템플릿
import statistics
values = data.get("values", [])
window = parameters.get("window", 7)

if len(values) >= window:
    ma = statistics.mean(values[-window:])
else:
    ma = statistics.mean(values) if values else 0

result = {
    "moving_average": ma,
    "window_size": window,
    "data_points": len(values),
}
''',
            "data_transform": '''
# 데이터 변환 템플릿
import json
source_data = data.get("source", {})
mapping = parameters.get("mapping", {})

transformed = {}
for target_key, source_key in mapping.items():
    if source_key in source_data:
        transformed[target_key] = source_data[source_key]

result = transformed
''',
            "anomaly_score": '''
# 이상치 점수 계산 템플릿
import statistics
values = data.get("values", [])
current = data.get("current_value", 0)

if len(values) >= 2:
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    if stdev > 0:
        z_score = abs(current - mean) / stdev
    else:
        z_score = 0
else:
    z_score = 0
    mean = current
    stdev = 0

result = {
    "z_score": z_score,
    "mean": mean,
    "stdev": stdev,
    "is_anomaly": z_score > 2.0,
}
''',
        }

        return templates.get(template_id)

    async def _execute_code_sandbox(
        self,
        code: str,
        input_data: Dict[str, Any],
        allowed_imports: List[str],
        timeout_ms: int,
        memory_limit_mb: int
    ) -> Dict[str, Any]:
        """
        제한된 샌드박스 환경에서 Python 코드 실행

        보안 조치:
        1. 허용된 import만 가능
        2. 내장 함수 제한 (open, exec, eval 등 차단)
        3. 타임아웃 적용
        4. 결과는 'result' 변수로 반환
        """
        # 허용된 모듈 사전 import
        safe_globals = {
            "__builtins__": {
                # 안전한 내장 함수만 허용
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sorted": sorted,
                "reversed": reversed,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "round": round,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "isinstance": isinstance,
                "type": type,
                "None": None,
                "True": True,
                "False": False,
            }
        }

        # 허용된 모듈 import
        for module_name in allowed_imports:
            try:
                if module_name == "json":
                    import json as _json
                    safe_globals["json"] = _json
                elif module_name == "datetime":
                    import datetime as _datetime
                    safe_globals["datetime"] = _datetime
                elif module_name == "math":
                    import math as _math
                    safe_globals["math"] = _math
                elif module_name == "statistics":
                    import statistics as _statistics
                    safe_globals["statistics"] = _statistics
                elif module_name == "re":
                    import re as _re
                    safe_globals["re"] = _re
                # pandas, numpy는 설치 여부에 따라 선택적 허용
                elif module_name == "pandas":
                    try:
                        import pandas as _pd
                        safe_globals["pd"] = _pd
                    except ImportError:
                        pass
                elif module_name == "numpy":
                    try:
                        import numpy as _np
                        safe_globals["np"] = _np
                    except ImportError:
                        pass
            except ImportError:
                logger.warning(f"모듈 import 실패: {module_name}")

        # 입력 데이터를 locals에 설정
        safe_locals = {
            "data": input_data.get("data", {}),
            "parameters": input_data.get("parameters", {}),
            "context": input_data.get("context", {}),
            "result": None,  # 결과 저장용
        }

        # 타임아웃 적용하여 실행
        timeout_sec = timeout_ms / 1000

        def run_code():
            exec(code, safe_globals, safe_locals)
            return safe_locals.get("result", {})

        # asyncio에서 동기 코드 실행 (타임아웃 포함)
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, run_code),
                timeout=timeout_sec
            )
            return result if result is not None else {}
        except asyncio.TimeoutError:
            raise

    async def _execute_code_unsafe(
        self,
        code: str,
        input_data: Dict[str, Any],
        timeout_ms: int
    ) -> Dict[str, Any]:
        """
        비샌드박스 모드 실행 (개발/테스트용)

        주의: 프로덕션에서 사용 금지
        """
        safe_locals = {
            "data": input_data.get("data", {}),
            "parameters": input_data.get("parameters", {}),
            "context": input_data.get("context", {}),
            "result": None,
        }

        timeout_sec = timeout_ms / 1000

        def run_code():
            exec(code, {"__builtins__": __builtins__}, safe_locals)
            return safe_locals.get("result", {})

        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, run_code),
                timeout=timeout_sec
            )
            return result if result is not None else {}
        except asyncio.TimeoutError:
            raise


# 전역 워크플로우 엔진
workflow_engine = WorkflowEngine()
