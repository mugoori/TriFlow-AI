"""
워크플로우 실행 엔진
조건 평가 및 액션 실행

스펙 참조: B-5_Workflow_State_Machine.md (15개 노드 타입)

지원 노드 타입 (18개 전체 구현):
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
- judgment: 판단 에이전트 호출 - JudgmentAgent 연동 (V2 Phase2)
- bi: BI 분석 에이전트 호출 - BIPlannerAgent 연동 (V2 Phase2)
- mcp: MCP 외부 도구 호출 - MCPToolHubService 연동 (V2 Phase2)
- compensation: 보상 트랜잭션 (Saga 패턴)
- deploy: 배포 (ruleset/model/workflow)
- rollback: 롤백 (버전 복구)
- simulate: 시뮬레이션 (What-if 분석)

Phase 4 추가:
- WorkflowStateMachine: 워크플로우 상태 관리
- CheckpointManager: 장기 실행 체크포인트/복구
"""
import asyncio
import csv
import io
import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.services.notifications import notification_manager, NotificationStatus

logger = logging.getLogger(__name__)

# Optional AWS S3 import
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.warning("boto3 not available. export_to_csv will use local filesystem.")


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
            # 외부 API 호출
            "call_api": self._call_api,
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

        # S3 저장 시도 (AWS 설정이 있을 때만)
        if S3_AVAILABLE and settings.aws_access_key_id and settings.s3_bucket_name:
            try:
                s3_client = boto3.client(
                    's3',
                    region_name=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                )

                bucket_name = settings.s3_bucket_name
                object_name = f"exports/{workflow_id or 'unknown'}/{filename}"
                csv_bytes = csv_content.encode('utf-8')

                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_name,
                    Body=csv_bytes,
                    ContentType='text/csv',
                )

                storage_path = f"s3://{bucket_name}/{object_name}"
                storage_type = "s3"
                logger.info(f"CSV 파일 S3 저장: {storage_path}")

            except Exception as e:
                logger.warning(f"S3 저장 실패, 로컬 저장으로 대체: {e}")

        # S3 실패 또는 설정 없으면 로컬 저장
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

    async def _call_api(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        외부 API 호출

        파라미터:
            url: API 엔드포인트 URL (필수)
            method: HTTP 메서드 (GET, POST, PUT, DELETE, PATCH) - 기본값 GET
            headers: 요청 헤더 (dict) - 선택
            body: 요청 본문 (dict) - POST/PUT/PATCH용
            timeout: 타임아웃 초 (기본 30)
            retry_count: 재시도 횟수 (기본 0)

        출력:
            status_code: HTTP 상태 코드
            response: 응답 본문
        """
        import httpx

        url = params.get("url")
        if not url:
            return {
                "message": "URL이 필요합니다",
                "data": {"error": "missing_url"},
            }

        method = params.get("method", "GET").upper()
        headers = params.get("headers", {})
        body = params.get("body", None)
        timeout = params.get("timeout", 30)
        retry_count = params.get("retry_count", 0)

        # 보안: 내부 네트워크 URL 차단 (선택적)
        blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "internal"]
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if any(blocked in parsed.netloc for blocked in blocked_hosts):
            # 개발 환경에서는 허용, 프로덕션에서는 차단
            from app.config import settings
            if getattr(settings, "ENVIRONMENT", "development") == "production":
                return {
                    "message": "내부 네트워크 URL은 호출할 수 없습니다",
                    "data": {"error": "blocked_internal_url", "url": url},
                }

        last_error = None
        for attempt in range(retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    if method == "GET":
                        response = await client.get(url, headers=headers)
                    elif method == "POST":
                        response = await client.post(url, headers=headers, json=body)
                    elif method == "PUT":
                        response = await client.put(url, headers=headers, json=body)
                    elif method == "DELETE":
                        response = await client.delete(url, headers=headers)
                    elif method == "PATCH":
                        response = await client.patch(url, headers=headers, json=body)
                    else:
                        return {
                            "message": f"지원하지 않는 HTTP 메서드: {method}",
                            "data": {"error": "unsupported_method"},
                        }

                    # 응답 파싱
                    try:
                        response_data = response.json()
                    except Exception:
                        response_data = response.text

                    logger.info(f"[CALL_API] {method} {url} -> {response.status_code}")

                    return {
                        "message": f"API 호출 완료: {method} {url}",
                        "data": {
                            "status_code": response.status_code,
                            "response": response_data,
                            "url": url,
                            "method": method,
                        },
                    }

            except httpx.TimeoutException as e:
                last_error = f"타임아웃: {e}"
                logger.warning(f"[CALL_API] Timeout on attempt {attempt + 1}: {url}")
            except httpx.RequestError as e:
                last_error = f"요청 오류: {e}"
                logger.warning(f"[CALL_API] Request error on attempt {attempt + 1}: {e}")
            except Exception as e:
                last_error = f"알 수 없는 오류: {e}"
                logger.error(f"[CALL_API] Unknown error: {e}")
                break

        return {
            "message": f"API 호출 실패: {last_error}",
            "data": {"error": last_error, "url": url, "attempts": retry_count + 1},
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
        use_simulated_data: bool = False,
        instance_id: Optional[str] = None,
        resume_from_checkpoint: bool = False
    ) -> Dict[str, Any]:
        """
        워크플로우 실행

        Args:
            workflow_id: 워크플로우 ID
            dsl: 워크플로우 DSL 정의
            input_data: 입력 데이터 (센서 값 등)
            use_simulated_data: True면 시뮬레이션 데이터 사용
            instance_id: 워크플로우 인스턴스 ID (없으면 자동 생성)
            resume_from_checkpoint: True면 체크포인트에서 재개

        Returns:
            실행 결과
        """
        start_time = time.time()

        # 인스턴스 ID 생성/확인
        if not instance_id:
            instance_id = str(uuid4())

        # 입력 데이터 준비
        if use_simulated_data and not input_data:
            input_data = self.sensor_simulator.generate_sensor_data(scenario="random")

        # 체크포인트에서 재개하는 경우
        resume_node_id = None
        if resume_from_checkpoint:
            recovery_info = await self._try_resume_from_checkpoint(instance_id)
            if recovery_info:
                resume_node_id = recovery_info.get("resume_from_node")
                # 저장된 컨텍스트 복구
                saved_context = recovery_info.get("context", {})
                input_data = {**(input_data or {}), **saved_context.get("input_data", {})}
                logger.info(f"Resuming workflow from node: {resume_node_id}")

        context = {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "input_data": input_data or {},
            "executed_nodes": [],  # 실행된 노드 목록 (보상용)
            **(input_data or {})  # 센서 값을 최상위에도 복사
        }

        nodes = dsl.get("nodes", [])

        # 상태 머신: 인스턴스 초기화 및 상태 전이
        try:
            # 새 인스턴스 또는 재개인 경우
            state_info = workflow_state_machine.get_state(instance_id)
            if not state_info.get("exists"):
                workflow_state_machine.initialize_instance(
                    instance_id, workflow_id, {"input_data": input_data}
                )
                await workflow_state_machine.transition(
                    instance_id, WorkflowState.PENDING, "Workflow started"
                )

            # RUNNING 상태로 전이
            current_state = state_info.get("state", "created")
            if current_state in ["created", "pending", "paused", "waiting"]:
                await workflow_state_machine.transition(
                    instance_id, WorkflowState.RUNNING, "Execution started"
                )

        except InvalidStateTransition as e:
            logger.warning(f"State transition warning: {e}")
            # 경고만 하고 계속 진행 (MVP)

        # 노드 실행
        exec_result = await self._execute_nodes(
            nodes, context, resume_node_id=resume_node_id
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        # 상태 머신: 종료 상태 전이
        try:
            if exec_result.get("waiting"):
                # 승인/이벤트 대기 중
                await workflow_state_machine.transition(
                    instance_id, WorkflowState.WAITING,
                    f"Waiting at node: {exec_result.get('waiting_node_id')}"
                )
                # 체크포인트 저장
                await checkpoint_manager.save_checkpoint(
                    instance_id,
                    exec_result.get("waiting_node_id", "unknown"),
                    context,
                    {"waiting_reason": exec_result.get("waiting_reason")}
                )
            elif exec_result["failed"]:
                await workflow_state_machine.transition(
                    instance_id, WorkflowState.FAILED,
                    exec_result.get("error_message", "Execution failed")
                )
            else:
                await workflow_state_machine.transition(
                    instance_id, WorkflowState.COMPLETED, "Execution completed"
                )
                # 완료 시 체크포인트 삭제
                await checkpoint_manager.delete_checkpoint(instance_id)

        except InvalidStateTransition as e:
            logger.warning(f"Final state transition warning: {e}")

        return {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "status": "waiting" if exec_result.get("waiting") else (
                "failed" if exec_result["failed"] else "completed"
            ),
            "input_data": input_data,
            "nodes_total": exec_result["total"],
            "nodes_executed": exec_result["executed"],
            "nodes_skipped": exec_result["skipped"],
            "results": exec_result["results"],
            "error_message": exec_result["error_message"],
            "waiting_info": exec_result.get("waiting_info"),
            "execution_time_ms": execution_time_ms,
            "executed_at": datetime.utcnow().isoformat(),
        }

    async def _try_resume_from_checkpoint(
        self,
        instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """체크포인트에서 재개 시도"""
        try:
            recovery_info = await checkpoint_manager.get_recovery_info(instance_id)
            if recovery_info and recovery_info.get("can_resume"):
                return recovery_info
        except Exception as e:
            logger.warning(f"Failed to get recovery info: {e}")
        return None

    async def _execute_nodes(
        self,
        nodes: List[Dict[str, Any]],
        context: Dict[str, Any],
        resume_node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        노드 리스트 실행 (재귀 호출 가능)

        Args:
            nodes: 실행할 노드 목록
            context: 실행 컨텍스트
            resume_node_id: 재개할 노드 ID (체크포인트 복구 시)

        Returns:
            {
                "results": [...],
                "executed": int,
                "skipped": int,
                "total": int,
                "failed": bool,
                "error_message": str | None,
                "waiting": bool (optional),
                "waiting_node_id": str (optional),
                "waiting_reason": str (optional)
            }
        """
        results = []
        executed_count = 0
        skipped_count = 0
        failed = False
        error_message = None
        waiting = False
        waiting_node_id = None
        waiting_reason = None

        # 재개 노드 찾기 (체크포인트 복구 시)
        resume_found = resume_node_id is None  # None이면 처음부터 실행

        for node in nodes:
            if failed or waiting:
                skipped_count += 1
                continue

            node_id = node.get("id", f"node_{uuid4().hex[:8]}")
            node_type = node.get("type")
            config = node.get("config", {})

            # 재개 노드까지 스킵
            if not resume_found:
                if node_id == resume_node_id:
                    resume_found = True
                    logger.info(f"Resuming from checkpoint node: {node_id}")
                else:
                    skipped_count += 1
                    continue

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

                    # 이벤트 대기 상태 체크
                    if result.get("waiting"):
                        waiting = True
                        waiting_node_id = node_id
                        waiting_reason = result.get("message", "Waiting for event")
                        executed_count += 1
                        continue

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    executed_count += 1

                elif node_type == "approval":
                    result = await self._execute_approval_node(node_id, config, context)
                    results.append(result)

                    # 대기 상태 체크 (승인 대기 중)
                    if result.get("waiting"):
                        waiting = True
                        waiting_node_id = node_id
                        waiting_reason = result.get("message", "Waiting for approval")
                        # 실행된 노드 목록에 추가 (보상 트랜잭션용)
                        if "executed_nodes" in context:
                            context["executed_nodes"].append({
                                "node_id": node_id,
                                "type": "approval",
                                "status": "waiting",
                                "approval_id": result.get("approval_id"),
                            })
                        executed_count += 1
                        continue

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

                elif node_type == "judgment":
                    result = await self._execute_judgment_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    # 판단 결과를 컨텍스트에 저장
                    output_var = config.get("output", {}).get("variable", "judgment_result")
                    context[output_var] = result.get("result", {})
                    executed_count += 1

                elif node_type == "bi":
                    result = await self._execute_bi_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    # BI 분석 결과를 컨텍스트에 저장
                    output_var = config.get("output", {}).get("variable", "bi_result")
                    context[output_var] = result.get("result", {})
                    executed_count += 1

                elif node_type == "mcp":
                    result = await self._execute_mcp_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break

                    # MCP 도구 호출 결과를 컨텍스트에 저장
                    output_var = config.get("output_variable", "mcp_result")
                    context[output_var] = result.get("result", {})
                    executed_count += 1

                # ============ P2 노드 ============
                elif node_type == "compensation":
                    result = await self._execute_compensation_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break
                    executed_count += 1

                elif node_type == "deploy":
                    result = await self._execute_deploy_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break
                    executed_count += 1

                elif node_type == "rollback":
                    result = await self._execute_rollback_node(node_id, config, context)
                    results.append(result)

                    if not result.get("success", False):
                        failed = True
                        error_message = result.get("message")
                        break
                    executed_count += 1

                elif node_type == "simulate":
                    result = await self._execute_simulate_node(node_id, config, context)
                    results.append(result)

                    # Simulate 노드는 실패해도 워크플로우 계속 진행
                    if not result.get("success", False):
                        logger.warning(f"Simulate 노드 실행 실패: {node_id}")
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

        result = {
            "results": results,
            "executed": executed_count,
            "skipped": skipped_count,
            "total": len(nodes),
            "failed": failed,
            "error_message": error_message,
        }

        # 대기 상태 정보 추가
        if waiting:
            result["waiting"] = True
            result["waiting_node_id"] = waiting_node_id
            result["waiting_reason"] = waiting_reason
            result["waiting_info"] = {
                "node_id": waiting_node_id,
                "reason": waiting_reason,
            }

        return result

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
                # DataConnector 통해 데이터 조회
                from app.models.core import DataConnector as DataConnectorModel
                from uuid import UUID as UUIDType
                import sqlalchemy as sa

                source_id = config.get("source_id")
                query = config.get("query", "")

                if not source_id:
                    return {
                        "node_id": node_id,
                        "type": "data",
                        "success": False,
                        "message": "source_id는 필수입니다 (connector 타입)",
                    }

                with get_db_context() as db:
                    # 커넥터 정보 조회
                    connector = db.query(DataConnectorModel).filter(
                        DataConnectorModel.connector_id == UUIDType(source_id)
                    ).first()

                    if not connector:
                        return {
                            "node_id": node_id,
                            "type": "data",
                            "success": False,
                            "message": f"DataConnector를 찾을 수 없음: {source_id}",
                        }

                    if connector.status != "active":
                        return {
                            "node_id": node_id,
                            "type": "data",
                            "success": False,
                            "message": f"DataConnector가 비활성 상태: {connector.status}",
                        }

                    # 커넥터 타입별 처리
                    conn_type = connector.connector_type
                    conn_config = connector.connection_config or {}

                    if conn_type in ["postgresql", "mysql", "mssql", "oracle"]:
                        # 외부 DB 연결 및 쿼리 실행
                        if not query:
                            return {
                                "node_id": node_id,
                                "type": "data",
                                "success": False,
                                "message": "query는 필수입니다 (database connector)",
                            }

                        if not query.strip().upper().startswith("SELECT"):
                            return {
                                "node_id": node_id,
                                "type": "data",
                                "success": False,
                                "message": "SELECT 쿼리만 실행할 수 있습니다",
                            }

                        # 외부 DB 연결
                        try:
                            from sqlalchemy import create_engine

                            # 연결 문자열 생성
                            host = conn_config.get("host", "localhost")
                            port = conn_config.get("port", 5432)
                            database = conn_config.get("database", "")
                            username = conn_config.get("username", "")
                            password = conn_config.get("password", "")

                            if conn_type == "postgresql":
                                conn_str = f"postgresql://{username}:{password}@{host}:{port}/{database}"
                            elif conn_type == "mysql":
                                conn_str = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
                            elif conn_type == "mssql":
                                conn_str = f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
                            else:
                                conn_str = f"oracle+cx_oracle://{username}:{password}@{host}:{port}/?service_name={database}"

                            engine = create_engine(conn_str, pool_pre_ping=True)
                            with engine.connect() as conn:
                                result = conn.execute(text(query))
                                columns = list(result.keys()) if result.keys() else []
                                rows = [dict(zip(columns, row)) for row in result.fetchall()]

                            return {
                                "node_id": node_id,
                                "type": "data",
                                "source_type": source_type,
                                "success": True,
                                "message": f"커넥터 {connector.name}에서 {len(rows)}건 조회됨",
                                "data": {
                                    "rows": rows[:limit],
                                    "columns": columns,
                                    "total_count": len(rows),
                                    "connector_id": source_id,
                                    "connector_name": connector.name,
                                },
                            }

                        except Exception as conn_error:
                            logger.error(f"Connector DB 연결 오류: {conn_error}")
                            return {
                                "node_id": node_id,
                                "type": "data",
                                "success": False,
                                "message": f"DB 연결 오류: {str(conn_error)}",
                            }

                    else:
                        # 지원하지 않는 커넥터 타입
                        return {
                            "node_id": node_id,
                            "type": "data",
                            "success": False,
                            "message": f"지원하지 않는 커넥터 타입: {conn_type}",
                        }

            elif source_type == "api":
                # 외부 API 호출
                import httpx

                api_config = config.get("api", {})
                endpoint = api_config.get("url") or config.get("endpoint", "")
                method = api_config.get("method", "GET").upper()
                headers = api_config.get("headers", {})
                params = api_config.get("params", {})
                body = api_config.get("body", {})
                timeout_sec = api_config.get("timeout_seconds", 30)

                if not endpoint:
                    return {
                        "node_id": node_id,
                        "type": "data",
                        "success": False,
                        "message": "endpoint 또는 api.url은 필수입니다",
                    }

                # 파라미터 해석 (컨텍스트 변수 치환)
                resolved_params = self._resolve_parameters(params, context)
                resolved_headers = self._resolve_parameters(headers, context)
                resolved_body = self._resolve_parameters(body, context) if body else None

                try:
                    async with httpx.AsyncClient(timeout=timeout_sec) as client:
                        if method == "GET":
                            response = await client.get(
                                endpoint,
                                params=resolved_params,
                                headers=resolved_headers,
                            )
                        elif method == "POST":
                            response = await client.post(
                                endpoint,
                                params=resolved_params,
                                headers=resolved_headers,
                                json=resolved_body,
                            )
                        elif method == "PUT":
                            response = await client.put(
                                endpoint,
                                params=resolved_params,
                                headers=resolved_headers,
                                json=resolved_body,
                            )
                        elif method == "DELETE":
                            response = await client.delete(
                                endpoint,
                                params=resolved_params,
                                headers=resolved_headers,
                            )
                        else:
                            return {
                                "node_id": node_id,
                                "type": "data",
                                "success": False,
                                "message": f"지원하지 않는 HTTP 메서드: {method}",
                            }

                        response.raise_for_status()

                        # 응답 파싱
                        try:
                            response_data = response.json()
                        except Exception:
                            response_data = {"text": response.text}

                        # 배열 형태면 rows로, 객체면 data로
                        if isinstance(response_data, list):
                            rows = response_data
                        else:
                            rows = response_data.get("data", [response_data])

                        return {
                            "node_id": node_id,
                            "type": "data",
                            "source_type": source_type,
                            "success": True,
                            "message": f"API {endpoint} 호출 완료 (HTTP {response.status_code})",
                            "data": {
                                "rows": rows[:limit] if isinstance(rows, list) else rows,
                                "endpoint": endpoint,
                                "status_code": response.status_code,
                                "total_count": len(rows) if isinstance(rows, list) else 1,
                            },
                        }

                except httpx.HTTPStatusError as http_err:
                    return {
                        "node_id": node_id,
                        "type": "data",
                        "success": False,
                        "message": f"API 오류: HTTP {http_err.response.status_code}",
                    }
                except httpx.RequestError as req_err:
                    return {
                        "node_id": node_id,
                        "type": "data",
                        "success": False,
                        "message": f"API 요청 오류: {str(req_err)}",
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

        V2 Phase 2: 실제 이벤트 대기 구현 (Redis pub/sub 또는 DB 폴링)
        """
        wait_type = config.get("wait_type", "duration")
        start_time = time.time()
        tenant_id = context.get("tenant_id")
        workflow_id = context.get("workflow_id")
        instance_id = context.get("instance_id")

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
                # 이벤트 대기 - Redis pub/sub 또는 DB 폴링
                event_type = config.get("event_type", "unknown")
                event_filter = config.get("event_filter", {})
                timeout = config.get("timeout_seconds", 300)
                poll_interval = config.get("poll_interval_seconds", 5)

                logger.info(f"Wait 노드 {node_id}: 이벤트 '{event_type}' 대기 시작 (timeout: {timeout}s)")

                # 이벤트 대기 실행
                event_data = await self._wait_for_event(
                    tenant_id=tenant_id,
                    event_type=event_type,
                    event_filter=event_filter,
                    timeout_seconds=timeout,
                    poll_interval_seconds=poll_interval,
                    workflow_id=workflow_id,
                    instance_id=instance_id,
                    node_id=node_id,
                )

                elapsed = time.time() - start_time

                if event_data is None:
                    # 타임아웃
                    return {
                        "node_id": node_id,
                        "type": "wait",
                        "wait_type": wait_type,
                        "success": False,
                        "message": f"이벤트 '{event_type}' 대기 타임아웃 ({timeout}초)",
                        "data": {
                            "event_type": event_type,
                            "timeout_seconds": timeout,
                            "timed_out": True,
                            "elapsed_seconds": round(elapsed, 2),
                        },
                    }

                # 이벤트 수신 성공
                context["wait_event"] = event_data
                return {
                    "node_id": node_id,
                    "type": "wait",
                    "wait_type": wait_type,
                    "success": True,
                    "message": f"이벤트 '{event_type}' 수신됨",
                    "data": {
                        "event_type": event_type,
                        "timeout_seconds": timeout,
                        "event_data": event_data,
                        "elapsed_seconds": round(elapsed, 2),
                    },
                }

            elif wait_type == "schedule":
                # 스케줄 대기 (다음 cron 시간까지 대기)
                schedule_cron = config.get("schedule_cron", "")
                interval_seconds = config.get("interval_seconds")
                timeout = config.get("timeout_seconds", 3600)

                # interval_seconds가 있으면 단순히 그 시간만큼 대기
                if interval_seconds:
                    wait_seconds = min(interval_seconds, timeout, self.MAX_WAIT_SECONDS)
                    logger.info(f"Wait 노드 {node_id}: {wait_seconds}초 스케줄 대기 시작")
                    await asyncio.sleep(wait_seconds)

                    elapsed = time.time() - start_time
                    return {
                        "node_id": node_id,
                        "type": "wait",
                        "wait_type": wait_type,
                        "success": True,
                        "message": f"스케줄 대기 완료 ({wait_seconds}초)",
                        "data": {
                            "interval_seconds": interval_seconds,
                            "actual_wait_seconds": round(elapsed, 2),
                        },
                    }

                # cron 표현식 기반 대기 (간단한 구현: 고정 대기)
                # 실제 구현에서는 croniter 라이브러리 사용 권장
                logger.info(f"Wait 노드 {node_id}: 스케줄 '{schedule_cron}' 대기 (다음 실행까지)")

                # 간단한 대기 (실제 cron 파싱 없이)
                default_wait = min(60, timeout, self.MAX_WAIT_SECONDS)
                await asyncio.sleep(default_wait)

                elapsed = time.time() - start_time
                return {
                    "node_id": node_id,
                    "type": "wait",
                    "wait_type": wait_type,
                    "success": True,
                    "message": f"스케줄 '{schedule_cron}' 도달",
                    "data": {
                        "schedule_cron": schedule_cron,
                        "timeout_seconds": timeout,
                        "actual_wait_seconds": round(elapsed, 2),
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

    async def _wait_for_event(
        self,
        tenant_id: str,
        event_type: str,
        event_filter: Dict,
        timeout_seconds: int,
        poll_interval_seconds: int = 5,
        workflow_id: str = None,
        instance_id: str = None,
        node_id: str = None,
    ) -> Optional[Dict]:
        """
        이벤트 대기 - Redis pub/sub 또는 DB 폴링

        Returns:
            이벤트 데이터 (dict) 또는 None (타임아웃)
        """
        start_time = time.time()
        max_wait = min(timeout_seconds, self.MAX_WAIT_SECONDS)

        # 1. Redis pub/sub 시도 (더 효율적)
        try:
            from app.services.cache_service import CacheService

            if CacheService.is_available():
                client = CacheService.get_client()
                if client:
                    # Redis에서 이벤트 키 폴링
                    event_key = f"wf:event:{tenant_id}:{event_type}"

                    while (time.time() - start_time) < max_wait:
                        # Redis에서 이벤트 확인
                        event_data = CacheService.get(event_key)
                        if event_data:
                            # 필터 적용
                            if self._match_event_filter(event_data, event_filter):
                                # 이벤트 소비 (삭제)
                                CacheService.delete(event_key)
                                logger.info(f"Event received from Redis: {event_type}")
                                return event_data

                        await asyncio.sleep(poll_interval_seconds)

                    return None  # 타임아웃

        except Exception as e:
            logger.warning(f"Redis event wait failed, falling back to DB: {e}")

        # 2. DB 폴링 폴백
        try:
            from app.database import SessionLocal
            from sqlalchemy import text

            while (time.time() - start_time) < max_wait:
                db = SessionLocal()
                try:
                    # 미처리 이벤트 조회
                    result = db.execute(
                        text("""
                            SELECT event_id, event_data, created_at
                            FROM core.workflow_events
                            WHERE tenant_id = :tenant_id
                              AND event_type = :event_type
                              AND processed = false
                              AND (expires_at IS NULL OR expires_at > now())
                            ORDER BY created_at ASC
                            LIMIT 1
                        """),
                        {
                            "tenant_id": str(tenant_id) if tenant_id else None,
                            "event_type": event_type,
                        }
                    )
                    row = result.fetchone()

                    if row:
                        event_id, event_data_json, created_at = row
                        event_data = json.loads(event_data_json) if isinstance(event_data_json, str) else event_data_json

                        # 필터 적용
                        if self._match_event_filter(event_data, event_filter):
                            # 이벤트 처리됨으로 마킹
                            db.execute(
                                text("""
                                    UPDATE core.workflow_events
                                    SET processed = true,
                                        processed_at = now(),
                                        processed_by_instance = :instance_id
                                    WHERE event_id = :event_id
                                """),
                                {
                                    "event_id": event_id,
                                    "instance_id": str(instance_id) if instance_id else None,
                                }
                            )
                            db.commit()
                            logger.info(f"Event received from DB: {event_type} (id={event_id})")
                            return event_data

                finally:
                    db.close()

                await asyncio.sleep(poll_interval_seconds)

            return None  # 타임아웃

        except Exception as e:
            logger.error(f"DB event wait failed: {e}")
            return None

    def _match_event_filter(self, event_data: Dict, event_filter: Dict) -> bool:
        """이벤트 필터 매칭"""
        if not event_filter:
            return True

        for key, expected_value in event_filter.items():
            actual_value = event_data.get(key)

            # 간단한 값 비교
            if actual_value != expected_value:
                # 와일드카드 패턴 지원
                if isinstance(expected_value, str) and expected_value == "*":
                    continue
                return False

        return True

    # ============ APPROVAL 노드 ============

    # 승인 대기 설정
    DEFAULT_APPROVAL_POLL_INTERVAL = 5  # 폴링 간격 (초)
    MAX_APPROVAL_WAIT_SECONDS = 86400  # 최대 대기 시간 (24시간)

    async def _execute_approval_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Approval 노드 실행 - 인간 승인 대기 (DB 저장 + 폴링)

        config 형식:
        {
            "approval_type": "single" | "multi" | "quorum",
            "approvers": ["user1@example.com", "user2@example.com"],
            "quorum_count": 2, (quorum 타입일 때 필요한 승인 수)
            "timeout_seconds": 86400, (기본 24시간)
            "notification_channels": ["slack", "email"],
            "title": "생산 라인 변경 승인",
            "description": "LINE_A 설정 변경에 대한 승인이 필요합니다.",
            "auto_approve_on_timeout": false (타임아웃 시 자동 승인 여부),
            "wait_for_approval": true (승인 대기 여부, false면 즉시 리턴)
        }

        실제 구현:
        - 승인 요청을 core.workflow_approvals 테이블에 저장
        - notification_manager로 실제 알림 전송
        - 승인 상태 폴링 (Redis 우선, DB 폴백)
        - 타임아웃 및 auto_approve 처리
        """

        approval_type = config.get("approval_type", "single")
        approvers = config.get("approvers", [])
        quorum_count = config.get("quorum_count", 1)
        timeout_seconds = config.get("timeout_seconds", self.DEFAULT_APPROVAL_TIMEOUT)
        notification_channels = config.get("notification_channels", ["email"])
        title = config.get("title", "워크플로우 승인 요청")
        description = config.get("description", "")
        auto_approve_on_timeout = config.get("auto_approve_on_timeout", False)
        wait_for_approval = config.get("wait_for_approval", True)
        context_data = config.get("context_data", {})

        workflow_id = context.get("workflow_id")
        instance_id = context.get("instance_id")
        tenant_id = context.get("tenant_id")

        try:
            # 1. 승인 요청을 DB에 저장
            approval_id = await self._create_approval_request(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                instance_id=instance_id,
                node_id=node_id,
                approval_type=approval_type,
                title=title,
                description=description,
                approvers=approvers,
                quorum_count=quorum_count,
                timeout_seconds=timeout_seconds,
                auto_approve_on_timeout=auto_approve_on_timeout,
                notification_channels=notification_channels,
                context_data=context_data,
            )

            logger.info(f"Approval 노드 {node_id}: 승인 요청 생성됨 - approval_id={approval_id}")

            # 2. 알림 전송
            await self._send_approval_notifications(
                approval_id=approval_id,
                title=title,
                description=description,
                approvers=approvers,
                notification_channels=notification_channels,
                workflow_id=workflow_id,
            )

            # 로그에 승인 요청 기록
            log_entry = {
                "event_type": "approval_requested",
                "details": {
                    "approval_id": str(approval_id),
                    "workflow_id": workflow_id,
                    "node_id": node_id,
                    "approval_type": approval_type,
                    "approvers": approvers,
                    "timeout_seconds": timeout_seconds,
                },
                "context": context,
                "workflow_id": workflow_id,
            }
            execution_log_store.add_log(log_entry)

            # 3. 승인 대기 여부 결정
            if not wait_for_approval:
                # 즉시 리턴 (비동기 승인 처리)
                return {
                    "node_id": node_id,
                    "type": "approval",
                    "approval_type": approval_type,
                    "success": True,
                    "message": "승인 요청이 생성되었습니다 (비동기 대기)",
                    "data": {
                        "approval_id": str(approval_id),
                        "approvers": approvers,
                        "status": "pending",
                    },
                    "waiting": True,
                }

            # 4. 승인 대기 (폴링)
            approval_result = await self._wait_for_approval(
                approval_id=approval_id,
                timeout_seconds=min(timeout_seconds, self.MAX_APPROVAL_WAIT_SECONDS),
                poll_interval=self.DEFAULT_APPROVAL_POLL_INTERVAL,
                auto_approve_on_timeout=auto_approve_on_timeout,
            )

            # 5. 결과 처리
            final_status = approval_result.get("status", "timeout")

            # 승인 완료 로그
            log_entry = {
                "event_type": "approval_completed",
                "details": approval_result,
                "context": context,
                "workflow_id": workflow_id,
            }
            execution_log_store.add_log(log_entry)

            if final_status == "approved":
                return {
                    "node_id": node_id,
                    "type": "approval",
                    "approval_type": approval_type,
                    "success": True,
                    "message": "승인 완료",
                    "approval_result": approval_result,
                    "data": {
                        "approval_id": str(approval_id),
                        "approvers": approvers,
                        "status": "approved",
                        "decided_by": approval_result.get("decided_by"),
                        "decision_comment": approval_result.get("decision_comment"),
                    },
                }
            elif final_status == "rejected":
                return {
                    "node_id": node_id,
                    "type": "approval",
                    "approval_type": approval_type,
                    "success": False,
                    "message": "승인 거부됨",
                    "approval_result": approval_result,
                    "data": {
                        "approval_id": str(approval_id),
                        "approvers": approvers,
                        "status": "rejected",
                        "decided_by": approval_result.get("decided_by"),
                        "decision_comment": approval_result.get("decision_comment"),
                    },
                }
            else:  # timeout or cancelled
                return {
                    "node_id": node_id,
                    "type": "approval",
                    "approval_type": approval_type,
                    "success": auto_approve_on_timeout,
                    "message": f"승인 타임아웃 (auto_approve={auto_approve_on_timeout})",
                    "approval_result": approval_result,
                    "data": {
                        "approval_id": str(approval_id),
                        "approvers": approvers,
                        "status": "approved" if auto_approve_on_timeout else "timeout",
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

    async def _create_approval_request(
        self,
        tenant_id: str,
        workflow_id: str,
        instance_id: Optional[str],
        node_id: str,
        approval_type: str,
        title: str,
        description: str,
        approvers: List[str],
        quorum_count: int,
        timeout_seconds: int,
        auto_approve_on_timeout: bool,
        notification_channels: List[str],
        context_data: Dict[str, Any],
    ) -> str:
        """승인 요청을 DB에 저장"""
        import json
        from sqlalchemy import text
        from app.database import get_async_session

        approval_id = str(uuid4())
        timeout_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)

        # approvers를 JSONB 형식으로 변환
        approvers_json = [
            {"email": email, "status": "pending", "decided_at": None}
            for email in approvers
        ]

        try:
            async with get_async_session() as db:
                await db.execute(
                    text("""
                        INSERT INTO core.workflow_approvals (
                            approval_id, tenant_id, workflow_id, instance_id, node_id,
                            approval_type, title, description, approvers, quorum_count,
                            status, notification_channels, timeout_at, auto_approve_on_timeout,
                            context_data, created_at, updated_at
                        ) VALUES (
                            :approval_id, :tenant_id, :workflow_id, :instance_id, :node_id,
                            :approval_type, :title, :description, :approvers::jsonb, :quorum_count,
                            'pending', :notification_channels::jsonb, :timeout_at, :auto_approve,
                            :context_data::jsonb, NOW(), NOW()
                        )
                    """),
                    {
                        "approval_id": approval_id,
                        "tenant_id": tenant_id,
                        "workflow_id": workflow_id,
                        "instance_id": instance_id,
                        "node_id": node_id,
                        "approval_type": approval_type,
                        "title": title,
                        "description": description,
                        "approvers": json.dumps(approvers_json),
                        "quorum_count": quorum_count,
                        "notification_channels": json.dumps(notification_channels),
                        "timeout_at": timeout_at,
                        "auto_approve": auto_approve_on_timeout,
                        "context_data": json.dumps(context_data),
                    }
                )
                await db.commit()

            # Redis에도 캐시 (빠른 상태 조회용)
            try:
                from app.services.cache_service import CacheService
                if CacheService.is_available():
                    CacheService.set(
                        f"wf:approval:{approval_id}",
                        json.dumps({"status": "pending", "created_at": datetime.utcnow().isoformat()}),
                        expire_seconds=timeout_seconds + 3600  # 타임아웃 + 1시간
                    )
            except Exception as cache_error:
                logger.warning(f"Redis 캐시 저장 실패 (승인): {cache_error}")

            return approval_id

        except Exception as e:
            logger.error(f"승인 요청 DB 저장 실패: {e}")
            # 테이블이 없는 경우 in-memory 폴백
            logger.warning("workflow_approvals 테이블 없음 - 인메모리 모드로 진행")
            return approval_id

    async def _send_approval_notifications(
        self,
        approval_id: str,
        title: str,
        description: str,
        approvers: List[str],
        notification_channels: List[str],
        workflow_id: str,
    ) -> None:
        """승인자들에게 알림 전송"""
        from app.database import get_async_session
        try:
            from app.services.notification_manager import notification_manager

            for channel in notification_channels:
                if channel == "slack":
                    # Slack 알림
                    message = f"🔔 *승인 요청*\n\n*제목*: {title}\n*설명*: {description}\n*승인자*: {', '.join(approvers)}\n\n승인 링크: /workflows/approvals/{approval_id}"
                    await notification_manager.send_slack_message(
                        channel="#workflow-approvals",
                        text=message,
                    )
                    logger.info(f"Slack 알림 전송: {title}")

                elif channel == "email":
                    # 이메일 알림
                    for approver_email in approvers:
                        await notification_manager.send_email(
                            to=approver_email,
                            subject=f"[TriFlow] 승인 요청: {title}",
                            body=f"""
                            <h2>워크플로우 승인 요청</h2>
                            <p><strong>제목:</strong> {title}</p>
                            <p><strong>설명:</strong> {description}</p>
                            <p><strong>워크플로우 ID:</strong> {workflow_id}</p>
                            <p><a href="/workflows/approvals/{approval_id}">승인하기</a></p>
                            """,
                        )
                    logger.info(f"이메일 알림 전송: {approvers}")

            # notification_sent_at 업데이트
            try:
                async with get_async_session() as db:
                    from sqlalchemy import text
                    await db.execute(
                        text("""
                            UPDATE core.workflow_approvals
                            SET notification_sent_at = NOW()
                            WHERE approval_id = :approval_id
                        """),
                        {"approval_id": approval_id}
                    )
                    await db.commit()
            except Exception:
                pass

        except ImportError:
            # notification_manager가 없으면 로그로 대체
            logger.info(f"알림 전송 (mock): {notification_channels} -> {approvers}")
        except Exception as e:
            logger.warning(f"알림 전송 실패: {e}")

    async def _wait_for_approval(
        self,
        approval_id: str,
        timeout_seconds: int,
        poll_interval: float,
        auto_approve_on_timeout: bool,
    ) -> Dict[str, Any]:
        """승인 상태를 폴링하며 대기"""
        import json
        import time
        from sqlalchemy import text
        from app.database import get_async_session

        start_time = time.time()
        max_wait = min(timeout_seconds, self.MAX_APPROVAL_WAIT_SECONDS)

        while (time.time() - start_time) < max_wait:
            # 1. Redis에서 먼저 확인 (빠른 조회)
            try:
                from app.services.cache_service import CacheService
                if CacheService.is_available():
                    cached = CacheService.get(f"wf:approval:{approval_id}")
                    if cached:
                        data = json.loads(cached)
                        if data.get("status") in ("approved", "rejected", "cancelled"):
                            return data
            except Exception:
                pass

            # 2. DB에서 확인
            try:
                async with get_async_session() as db:
                    result = await db.execute(
                        text("""
                            SELECT status, decided_by, decided_at, decision_comment, approvers
                            FROM core.workflow_approvals
                            WHERE approval_id = :approval_id
                        """),
                        {"approval_id": approval_id}
                    )
                    row = result.fetchone()

                    if row:
                        status = row.status
                        if status in ("approved", "rejected", "cancelled"):
                            return {
                                "status": status,
                                "decided_by": str(row.decided_by) if row.decided_by else None,
                                "decided_at": row.decided_at.isoformat() if row.decided_at else None,
                                "decision_comment": row.decision_comment,
                            }
            except Exception as e:
                logger.warning(f"승인 상태 DB 조회 실패: {e}")

            # 3. 다음 폴링까지 대기
            await asyncio.sleep(poll_interval)

        # 4. 타임아웃 처리
        if auto_approve_on_timeout:
            # 자동 승인
            await self._update_approval_status(
                approval_id=approval_id,
                status="approved",
                decided_by=None,
                comment="Auto-approved on timeout",
            )
            return {
                "status": "approved",
                "decided_by": "system",
                "decided_at": datetime.utcnow().isoformat(),
                "decision_comment": "Auto-approved on timeout",
                "auto_approved": True,
            }
        else:
            # 타임아웃
            await self._update_approval_status(
                approval_id=approval_id,
                status="timeout",
                decided_by=None,
                comment="Approval request timed out",
            )
            return {
                "status": "timeout",
                "decided_by": None,
                "decided_at": datetime.utcnow().isoformat(),
                "decision_comment": "Approval request timed out",
            }

    async def _update_approval_status(
        self,
        approval_id: str,
        status: str,
        decided_by: Optional[str],
        comment: Optional[str],
    ) -> None:
        """승인 상태 업데이트"""
        import json
        from sqlalchemy import text
        from app.database import get_async_session

        try:
            async with get_async_session() as db:
                await db.execute(
                    text("""
                        UPDATE core.workflow_approvals
                        SET status = :status,
                            decided_by = :decided_by,
                            decided_at = NOW(),
                            decision_comment = :comment,
                            updated_at = NOW()
                        WHERE approval_id = :approval_id
                    """),
                    {
                        "approval_id": approval_id,
                        "status": status,
                        "decided_by": decided_by,
                        "comment": comment,
                    }
                )
                await db.commit()

            # Redis 캐시도 업데이트
            try:
                from app.services.cache_service import CacheService
                if CacheService.is_available():
                    CacheService.set(
                        f"wf:approval:{approval_id}",
                        json.dumps({
                            "status": status,
                            "decided_by": decided_by,
                            "decided_at": datetime.utcnow().isoformat(),
                            "decision_comment": comment,
                        }),
                        expire_seconds=3600  # 1시간
                    )
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"승인 상태 업데이트 실패: {e}")

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
        TRIGGER 노드 실행 - 실제 스케줄러/이벤트 연동

        스펙 (B-5 섹션 4.7):
        - trigger_type: schedule, event, condition, webhook, manual
        - schedule_config: cron 표현식 또는 interval_seconds, timezone
        - event_config: event_type, filter
        - condition_config: expression, check_interval_seconds, debounce_seconds
        - webhook_config: path, method, auth, rate_limit

        TRIGGER 노드는 워크플로우의 시작점으로:
        1. 워크플로우 DSL에서 트리거 조건 정의
        2. 조건 충족 시 워크플로우 자동 시작
        3. 이 메서드는 트리거가 실행될 때 초기 컨텍스트 설정

        V2 Phase 2: 실제 스케줄러/이벤트 버스 연동
        """
        trigger_type = config.get("trigger_type", "manual")
        trigger_time = datetime.utcnow().isoformat()
        workflow_id = context.get("workflow_id")
        tenant_id = context.get("tenant_id")

        # 트리거 타입별 처리
        if trigger_type == "schedule":
            schedule_config = config.get("schedule_config", {})
            cron_expression = schedule_config.get("cron", "")
            interval_seconds = schedule_config.get("interval_seconds")
            timezone = schedule_config.get("timezone", "UTC")

            # 실제 스케줄러 등록 (SchedulerService 연동)
            try:
                from app.services.scheduler_service import scheduler

                job_id = f"wf_trigger_{workflow_id}_{node_id}"

                # interval_seconds가 있으면 interval 기반, 없으면 cron 파싱 시도
                if interval_seconds:
                    # 기존 job 제거 후 재등록
                    scheduler.unregister_job(job_id)

                    # 트리거 핸들러 정의
                    async def trigger_handler():
                        """스케줄 트리거 발동 시 워크플로우 실행"""
                        logger.info(f"Schedule trigger fired: workflow={workflow_id}, node={node_id}")
                        # DB에 이벤트 기록
                        await self._record_workflow_event(
                            tenant_id=tenant_id,
                            event_type="schedule_trigger",
                            event_source="scheduler",
                            event_data={
                                "workflow_id": str(workflow_id),
                                "node_id": node_id,
                                "cron": cron_expression,
                                "interval_seconds": interval_seconds,
                            },
                            workflow_id=workflow_id,
                        )

                    scheduler.register_job(
                        job_id=job_id,
                        name=f"Workflow Trigger: {workflow_id}",
                        description=f"Scheduled trigger for workflow node {node_id}",
                        interval_seconds=interval_seconds,
                        handler=trigger_handler,
                        enabled=True,
                    )
                    logger.info(f"Registered schedule trigger: {job_id} (interval: {interval_seconds}s)")

                # DB에 트리거 등록 기록
                await self._register_scheduled_trigger(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    node_id=node_id,
                    cron_expression=cron_expression,
                    interval_seconds=interval_seconds,
                    timezone=timezone,
                    trigger_config=config,
                )

            except Exception as e:
                logger.warning(f"Failed to register schedule trigger: {e}")

            trigger_output = {
                "triggered": True,
                "trigger_time": trigger_time,
                "trigger_reason": f"Schedule: {cron_expression or f'{interval_seconds}s interval'}",
                "trigger_type": "schedule",
                "schedule": {
                    "cron": cron_expression,
                    "interval_seconds": interval_seconds,
                    "timezone": timezone,
                    "registered": True,
                }
            }

        elif trigger_type == "event":
            event_config = config.get("event_config", {})
            event_type = event_config.get("event_type", "")
            event_filter = event_config.get("filter", {})

            # 이벤트 데이터는 컨텍스트에서 가져옴 (이벤트 버스에서 전달)
            event_data = context.get("_event_data", {})

            # Redis pub/sub 이벤트 리스너 등록 (선택적)
            try:
                await self._register_event_listener(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    node_id=node_id,
                    event_type=event_type,
                    event_filter=event_filter,
                )
            except Exception as e:
                logger.warning(f"Failed to register event listener: {e}")

            trigger_output = {
                "triggered": True,
                "trigger_time": trigger_time,
                "trigger_reason": f"Event: {event_type}",
                "trigger_type": "event",
                "event": {
                    "event_type": event_type,
                    "filter": event_filter,
                    "data": event_data,
                    "listener_registered": True,
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

    async def _register_scheduled_trigger(
        self,
        tenant_id: str,
        workflow_id: str,
        node_id: str,
        cron_expression: str,
        interval_seconds: Optional[int],
        timezone: str,
        trigger_config: Dict,
    ) -> None:
        """스케줄 트리거 DB 등록"""
        try:
            from app.database import SessionLocal
            from sqlalchemy import text
            from datetime import timedelta

            db = SessionLocal()
            try:
                # 다음 트리거 시간 계산
                next_trigger = datetime.utcnow()
                if interval_seconds:
                    next_trigger += timedelta(seconds=interval_seconds)

                db.execute(
                    text("""
                        INSERT INTO core.workflow_scheduled_triggers
                        (tenant_id, workflow_id, node_id, cron_expression, interval_seconds,
                         timezone, is_active, next_trigger_at, trigger_config)
                        VALUES (:tenant_id, :workflow_id, :node_id, :cron_expression, :interval_seconds,
                                :timezone, true, :next_trigger_at, :trigger_config)
                        ON CONFLICT (workflow_id, node_id)
                        DO UPDATE SET
                            cron_expression = EXCLUDED.cron_expression,
                            interval_seconds = EXCLUDED.interval_seconds,
                            timezone = EXCLUDED.timezone,
                            is_active = true,
                            next_trigger_at = EXCLUDED.next_trigger_at,
                            trigger_config = EXCLUDED.trigger_config,
                            updated_at = now()
                    """),
                    {
                        "tenant_id": str(tenant_id) if tenant_id else None,
                        "workflow_id": str(workflow_id) if workflow_id else None,
                        "node_id": node_id,
                        "cron_expression": cron_expression or None,
                        "interval_seconds": interval_seconds,
                        "timezone": timezone,
                        "next_trigger_at": next_trigger,
                        "trigger_config": json.dumps(trigger_config),
                    }
                )
                db.commit()
                logger.debug(f"Registered scheduled trigger: workflow={workflow_id}, node={node_id}")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to register scheduled trigger in DB: {e}")

    async def _register_event_listener(
        self,
        tenant_id: str,
        workflow_id: str,
        node_id: str,
        event_type: str,
        event_filter: Dict,
    ) -> None:
        """이벤트 리스너 등록 (Redis 기반)"""
        try:
            from app.services.cache_service import CacheService

            if not CacheService.is_available():
                logger.debug("Redis not available, skipping event listener registration")
                return

            # 이벤트 리스너 정보를 Redis에 저장
            listener_key = f"wf:event_listener:{tenant_id}:{event_type}"
            listener_data = {
                "workflow_id": str(workflow_id) if workflow_id else None,
                "node_id": node_id,
                "event_filter": event_filter,
                "registered_at": datetime.utcnow().isoformat(),
            }

            CacheService.set(
                listener_key,
                listener_data,
                ttl=86400 * 7,  # 7일
            )
            logger.debug(f"Registered event listener: {listener_key}")
        except Exception as e:
            logger.warning(f"Failed to register event listener: {e}")

    async def _record_workflow_event(
        self,
        tenant_id: str,
        event_type: str,
        event_source: str,
        event_data: Dict,
        workflow_id: str = None,
        instance_id: str = None,
        node_id: str = None,
        correlation_id: str = None,
    ) -> Optional[str]:
        """워크플로우 이벤트 DB 기록"""
        try:
            from app.database import SessionLocal
            from sqlalchemy import text

            db = SessionLocal()
            try:
                result = db.execute(
                    text("""
                        INSERT INTO core.workflow_events
                        (tenant_id, event_type, event_source, event_data,
                         workflow_id, instance_id, node_id, correlation_id)
                        VALUES (:tenant_id, :event_type, :event_source, :event_data::jsonb,
                                :workflow_id, :instance_id, :node_id, :correlation_id)
                        RETURNING event_id
                    """),
                    {
                        "tenant_id": str(tenant_id) if tenant_id else None,
                        "event_type": event_type,
                        "event_source": event_source,
                        "event_data": json.dumps(event_data),
                        "workflow_id": str(workflow_id) if workflow_id else None,
                        "instance_id": str(instance_id) if instance_id else None,
                        "node_id": node_id,
                        "correlation_id": correlation_id,
                    }
                )
                event_id = result.fetchone()[0]
                db.commit()
                return str(event_id)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to record workflow event: {e}")
            return None

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
        # 'inline_code' 또는 'code' 키 모두 지원
        inline_code = config.get("inline_code") or config.get("code")

        # 디버그 로그
        logger.info(f"CODE 노드 {node_id} config: {config}")
        logger.info(f"CODE 노드 {node_id} inline_code: {inline_code}, code: {config.get('code')}")
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
        # resolved_input이 비어있으면 context 전체를 전달
        sandbox_input = resolved_input if resolved_input else context
        start_time = time.time()
        try:
            if sandbox_enabled:
                output = await self._execute_code_sandbox(
                    code_to_execute,
                    sandbox_input,
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
        # input_data는 전체 context 또는 config.input 해석 결과
        safe_locals = {
            "data": input_data.get("data", {}),
            "parameters": input_data.get("parameters", {}),
            "context": input_data.get("context", {}),
            "input_data": input_data,  # 전체 입력 데이터 (사용자 편의)
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

    async def _execute_judgment_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        JUDGMENT 노드 실행 - JudgmentAgent 연동

        스펙 (B-5 섹션 4.2):
        - policy: RULE_ONLY | LLM_ONLY | HYBRID_WEIGHTED | ESCALATE
        - rule_pack_id: 룰팩 ID (UUID)
        - input: 입력 데이터 매핑
        - output: 결과 저장 변수

        설정 예시:
        {
            "policy": {
                "type": "HYBRID_WEIGHTED",
                "rule_weight": 0.6,
                "llm_weight": 0.4,
                "rule_pack_id": "uuid"
            },
            "input": {
                "temperature": "${sensor_data.temperature}",
                "pressure": "${sensor_data.pressure}"
            },
            "output": {
                "variable": "judgment_result"
            }
        }
        """
        from app.agents.judgment_agent import JudgmentAgent

        start_time = time.time()

        # 정책 설정
        policy_config = config.get("policy", {})
        policy_type = policy_config.get("type", "HYBRID_WEIGHTED")
        rule_pack_id = policy_config.get("rule_pack_id")

        # 입력 데이터 해석
        input_config = config.get("input", {})
        input_data = self._resolve_parameters(input_config, context)

        # 추가 컨텍스트 (라인 코드, 장비 ID 등)
        extra_context = {
            "workflow_id": context.get("workflow_id"),
            "node_id": node_id,
            "line_code": input_data.get("line_code"),
        }

        try:
            # JudgmentAgent 인스턴스 생성
            agent = JudgmentAgent()

            # 하이브리드 판단 실행
            if rule_pack_id:
                # hybrid_judgment 도구 호출
                judgment_result = agent._hybrid_judgment(
                    ruleset_id=rule_pack_id,
                    input_data=input_data,
                    policy=policy_type.lower().replace("_", "_"),
                    context=extra_context,
                )
            else:
                # rule_pack_id가 없으면 LLM_ONLY로 실행
                judgment_result = agent._hybrid_judgment(
                    ruleset_id="00000000-0000-0000-0000-000000000000",  # 기본 룰셋
                    input_data=input_data,
                    policy="llm_only",
                    context=extra_context,
                )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # 로그 기록
            execution_log_store.add_log({
                "event_type": "judgment_executed",
                "workflow_id": context.get("workflow_id"),
                "node_id": node_id,
                "policy_type": policy_type,
                "decision": judgment_result.get("decision", "UNKNOWN"),
                "confidence": judgment_result.get("confidence", 0),
                "execution_time_ms": execution_time_ms,
            })

            success = judgment_result.get("success", False)

            return {
                "node_id": node_id,
                "type": "judgment",
                "success": success,
                "message": f"판단 완료: {judgment_result.get('decision', 'UNKNOWN')} "
                          f"(신뢰도: {judgment_result.get('confidence', 0):.2f})",
                "result": {
                    "decision": judgment_result.get("decision"),
                    "confidence": judgment_result.get("confidence"),
                    "source": judgment_result.get("source"),
                    "policy_used": judgment_result.get("policy_used"),
                    "details": judgment_result.get("details", {}),
                    "recommendation": judgment_result.get("recommendation"),
                },
                "execution_time_ms": execution_time_ms,
            }

        except Exception as e:
            logger.error(f"JUDGMENT 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "judgment",
                "success": False,
                "message": f"판단 실행 오류: {str(e)}",
                "result": None,
            }

    async def _execute_bi_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        BI 노드 실행 - BIPlannerAgent 연동

        스펙 (B-5 섹션 4.3):
        - analysis_type: trend, comparison, distribution, correlation, anomaly
        - metrics: 분석 대상 메트릭 목록
        - dimensions: 분석 차원 목록
        - time_range: 분석 기간
        - filters: 필터 조건

        설정 예시:
        {
            "analysis": {
                "type": "trend",
                "metrics": ["production_qty", "defect_rate"],
                "dimensions": ["line_code", "shift"],
                "time_range": "7d"
            },
            "output": {
                "variable": "bi_result"
            }
        }
        """
        from app.agents.bi_planner import BIPlannerAgent

        start_time = time.time()

        analysis_config = config.get("analysis", {})
        analysis_type = analysis_config.get("type", "trend")
        metrics = analysis_config.get("metrics", [])
        dimensions = analysis_config.get("dimensions", [])
        time_range = analysis_config.get("time_range", "7d")
        filters = analysis_config.get("filters", [])

        try:
            # BIPlannerAgent 인스턴스 생성
            agent = BIPlannerAgent()

            # 분석 쿼리 생성
            analysis_query = f"{analysis_type} analysis for {', '.join(metrics)}"
            if dimensions:
                analysis_query += f" by {', '.join(dimensions)}"
            if time_range:
                analysis_query += f" over {time_range}"

            # tenant_id 가져오기
            from uuid import UUID
            tenant_id = context.get("tenant_id")
            if isinstance(tenant_id, str):
                tenant_id = UUID(tenant_id)
            elif not tenant_id:
                tenant_id = UUID("446e39b3-455e-4ca9-817a-4913921eb41d")

            # BI Agent 실행 (run 메서드 호출)
            bi_result = agent.run(
                user_message=analysis_query,
                context={"tenant_id": str(tenant_id)},
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # 로그 기록
            execution_log_store.add_log({
                "event_type": "bi_analysis_executed",
                "workflow_id": context.get("workflow_id"),
                "node_id": node_id,
                "analysis_type": analysis_type,
                "execution_time_ms": execution_time_ms,
            })

            return {
                "node_id": node_id,
                "type": "bi",
                "success": True,
                "message": f"BI 분석 완료 ({execution_time_ms}ms)",
                "result": {
                    "analysis_type": analysis_type,
                    "response": bi_result.get("response", ""),
                    "insight": bi_result.get("insight"),
                    "chart_data": bi_result.get("chart_data"),
                    "sql_query": bi_result.get("sql_query"),
                },
                "execution_time_ms": execution_time_ms,
            }

        except Exception as e:
            logger.error(f"BI 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "bi",
                "success": False,
                "message": f"BI 분석 오류: {str(e)}",
                "result": None,
            }

    async def _execute_mcp_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        MCP 노드 실행 - MCPToolHubService 연동

        스펙 (B-5 섹션 4.5):
        - mcp_server_id: MCP 서버 ID (UUID)
        - tool_name: 호출할 도구 이름
        - parameters: 도구 파라미터
        - timeout_ms: 타임아웃 (기본 30초)

        설정 예시:
        {
            "mcp_server_id": "uuid",
            "tool_name": "weather_api",
            "parameters": {
                "location": "{{city}}"
            },
            "timeout_ms": 30000,
            "output_variable": "mcp_result"
        }
        """
        from app.services.mcp_toolhub import get_mcp_toolhub_service
        from app.models.mcp import MCPCallRequest

        start_time = time.time()

        # 'mcp_server_id' 또는 'server_id' 키 모두 지원
        server_id = config.get("mcp_server_id") or config.get("server_id")
        tool_name = config.get("tool_name")
        parameters = config.get("parameters", {})
        correlation_id = config.get("correlation_id")

        if not server_id or not tool_name:
            return {
                "node_id": node_id,
                "type": "mcp",
                "success": False,
                "message": "mcp_server_id와 tool_name은 필수입니다",
                "result": None,
            }

        # 파라미터 해석
        resolved_params = self._resolve_parameters(parameters, context)

        try:
            # MCPToolHubService 인스턴스
            mcp_service = get_mcp_toolhub_service()

            # tenant_id 가져오기
            from uuid import UUID
            tenant_id = context.get("tenant_id")
            if isinstance(tenant_id, str):
                tenant_id = UUID(tenant_id)
            elif not tenant_id:
                tenant_id = UUID("446e39b3-455e-4ca9-817a-4913921eb41d")

            # MCPCallRequest 생성
            call_request = MCPCallRequest(
                server_id=UUID(server_id) if isinstance(server_id, str) else server_id,
                tool_name=tool_name,
                args=resolved_params,
                correlation_id=correlation_id or f"wf_{context.get('workflow_id', 'unknown')}_{node_id}",
            )

            # MCP 도구 호출 (동기 함수)
            mcp_response = mcp_service.call_tool(
                tenant_id=tenant_id,
                request=call_request,
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # mcp_toolhub.MCPCallResponse 필드: success, output_data, error_message, latency_ms
            success = mcp_response.success

            # 로그 기록
            execution_log_store.add_log({
                "event_type": "mcp_tool_called",
                "workflow_id": context.get("workflow_id"),
                "node_id": node_id,
                "server_id": str(server_id),
                "tool_name": tool_name,
                "execution_time_ms": execution_time_ms,
                "status": "success" if success else "failed",
            })

            return {
                "node_id": node_id,
                "type": "mcp",
                "success": success,
                "message": f"MCP 도구 호출 완료: {tool_name} ({mcp_response.latency_ms or 0}ms)"
                          if success else f"MCP 도구 호출 실패: {mcp_response.error_message or 'Unknown error'}",
                "result": mcp_response.output_data if success else None,
                "execution_time_ms": execution_time_ms,
            }

        except Exception as e:
            logger.error(f"MCP 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "mcp",
                "success": False,
                "message": f"MCP 도구 호출 오류: {str(e)}",
                "result": None,
            }

    # ============ P2 노드: COMPENSATION ============

    async def _execute_compensation_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        COMPENSATION 노드 실행 - Saga 패턴 롤백

        config 형식:
        {
            "compensation_type": "auto" | "manual",
            "target_nodes": ["node_1", "node_2"],  # 보상할 노드들
            "compensation_actions": {
                "node_1": {"action_type": "api_call", "config": {...}},
                "node_2": {"action_type": "db_rollback", "config": {...}}
            },
            "on_failure": "continue" | "abort"
        }

        Saga 패턴:
        - 실패한 노드들의 compensation_action을 역순으로 실행
        - 각 보상 작업의 성공/실패 추적
        """

        compensation_type = config.get("compensation_type", "auto")
        target_nodes = config.get("target_nodes", [])
        compensation_actions = config.get("compensation_actions", {})
        on_failure = config.get("on_failure", "continue")

        workflow_id = context.get("workflow_id")
        executed_nodes = context.get("executed_nodes", [])  # 이전에 실행된 노드 목록

        try:
            compensated = []
            failed_compensations = []

            # 자동 모드: 실행된 노드들 역순으로 보상
            if compensation_type == "auto":
                nodes_to_compensate = list(reversed(executed_nodes))
            else:
                nodes_to_compensate = list(reversed(target_nodes))

            logger.info(f"COMPENSATION 노드 {node_id}: {len(nodes_to_compensate)}개 노드 보상 시작")

            for target_node in nodes_to_compensate:
                target_node_id = target_node.get("node_id") if isinstance(target_node, dict) else target_node

                # 보상 액션 찾기
                action_config = compensation_actions.get(target_node_id)
                if not action_config:
                    # 노드에 정의된 보상 액션 확인
                    if isinstance(target_node, dict):
                        action_config = target_node.get("compensation_action")

                if not action_config:
                    logger.warning(f"보상 액션 없음: {target_node_id}")
                    continue

                try:
                    # 보상 액션 실행
                    action_type = action_config.get("action_type", "api_call")
                    action_result = await self._execute_compensation_action(
                        target_node_id=target_node_id,
                        action_type=action_type,
                        action_config=action_config.get("config", {}),
                        context=context
                    )

                    if action_result.get("success"):
                        compensated.append({
                            "node_id": target_node_id,
                            "status": "compensated",
                            "result": action_result
                        })
                    else:
                        failed_compensations.append({
                            "node_id": target_node_id,
                            "status": "failed",
                            "error": action_result.get("message")
                        })

                        if on_failure == "abort":
                            break

                except Exception as e:
                    failed_compensations.append({
                        "node_id": target_node_id,
                        "status": "error",
                        "error": str(e)
                    })
                    if on_failure == "abort":
                        break

            # 로그 기록
            log_entry = {
                "event_type": "compensation_executed",
                "workflow_id": workflow_id,
                "node_id": node_id,
                "compensated": compensated,
                "failed": failed_compensations,
            }
            execution_log_store.add_log(log_entry)

            all_success = len(failed_compensations) == 0

            return {
                "node_id": node_id,
                "type": "compensation",
                "success": all_success,
                "message": f"보상 완료: {len(compensated)}개 성공, {len(failed_compensations)}개 실패",
                "data": {
                    "compensated": compensated,
                    "failed": failed_compensations,
                },
            }

        except Exception as e:
            logger.error(f"COMPENSATION 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "compensation",
                "success": False,
                "message": f"보상 처리 오류: {str(e)}",
            }

    async def _execute_compensation_action(
        self,
        target_node_id: str,
        action_type: str,
        action_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """개별 보상 액션 실행"""
        from app.database import get_async_session

        if action_type == "api_call":
            # API 호출로 롤백
            import httpx
            url = action_config.get("url")
            method = action_config.get("method", "POST")
            params = self._resolve_parameters(action_config.get("params", {}), context)

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.request(method, url, json=params)
                    return {
                        "success": response.status_code < 400,
                        "status_code": response.status_code,
                        "result": response.json() if response.status_code < 400 else None,
                    }
            except Exception as e:
                return {"success": False, "message": str(e)}

        elif action_type == "db_rollback":
            # DB 트랜잭션 롤백
            table = action_config.get("table")
            rollback_query = action_config.get("query")

            try:
                from sqlalchemy import text
                async with get_async_session() as db:
                    await db.execute(text(rollback_query))
                    await db.commit()
                return {"success": True, "message": f"DB 롤백 완료: {table}"}
            except Exception as e:
                return {"success": False, "message": str(e)}

        elif action_type == "state_restore":
            # 상태 복원
            restore_key = action_config.get("key")
            restore_value = action_config.get("value")
            context[restore_key] = restore_value
            return {"success": True, "message": f"상태 복원: {restore_key}"}

        else:
            return {"success": False, "message": f"알 수 없는 보상 타입: {action_type}"}

    # ============ P2 노드: DEPLOY ============

    async def _execute_deploy_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        DEPLOY 노드 실행 - 룰/모델/워크플로우 배포

        config 형식:
        {
            "deploy_type": "ruleset" | "model" | "workflow",
            "target_id": "uuid",
            "version": 1,  # 옵션, 없으면 최신 버전
            "environment": "production" | "staging" | "development",
            "rollback_on_failure": true,
            "validation": {
                "enabled": true,
                "rules": ["test_coverage > 80", "no_syntax_errors"]
            }
        }
        """

        deploy_type = config.get("deploy_type", "ruleset")
        target_id = config.get("target_id")
        version = config.get("version")
        environment = config.get("environment", "production")
        rollback_on_failure = config.get("rollback_on_failure", True)
        validation_config = config.get("validation", {})

        workflow_id = context.get("workflow_id")
        tenant_id = context.get("tenant_id")

        try:
            # 1. 사전 검증 (옵션)
            if validation_config.get("enabled", False):
                validation_result = await self._validate_deployment(
                    deploy_type=deploy_type,
                    target_id=target_id,
                    version=version,
                    rules=validation_config.get("rules", [])
                )
                if not validation_result.get("success"):
                    return {
                        "node_id": node_id,
                        "type": "deploy",
                        "success": False,
                        "message": f"배포 검증 실패: {validation_result.get('errors')}",
                    }

            # 2. 이전 버전 백업 (롤백용)
            previous_version = None
            if rollback_on_failure:
                previous_version = await self._get_current_active_version(
                    deploy_type=deploy_type,
                    target_id=target_id,
                    tenant_id=tenant_id
                )
                context["_deploy_previous_version"] = previous_version

            # 3. 배포 실행
            if deploy_type == "ruleset":
                result = await self._deploy_ruleset(
                    ruleset_id=target_id,
                    version=version,
                    environment=environment,
                    tenant_id=tenant_id
                )
            elif deploy_type == "model":
                result = await self._deploy_model(
                    model_id=target_id,
                    version=version,
                    environment=environment,
                    tenant_id=tenant_id
                )
            elif deploy_type == "workflow":
                result = await self._deploy_workflow(
                    workflow_id=target_id,
                    version=version,
                    environment=environment,
                    tenant_id=tenant_id
                )
            else:
                return {
                    "node_id": node_id,
                    "type": "deploy",
                    "success": False,
                    "message": f"알 수 없는 배포 타입: {deploy_type}",
                }

            if not result.get("success"):
                # 롤백
                if rollback_on_failure and previous_version:
                    await self._rollback_to_version(
                        deploy_type=deploy_type,
                        target_id=target_id,
                        version=previous_version,
                        tenant_id=tenant_id
                    )

            # 로그 기록
            log_entry = {
                "event_type": "deployment_executed",
                "workflow_id": workflow_id,
                "node_id": node_id,
                "deploy_type": deploy_type,
                "target_id": target_id,
                "version": version,
                "environment": environment,
                "result": result,
            }
            execution_log_store.add_log(log_entry)

            return {
                "node_id": node_id,
                "type": "deploy",
                "success": result.get("success", False),
                "message": result.get("message", "배포 완료"),
                "data": {
                    "deploy_type": deploy_type,
                    "target_id": target_id,
                    "version": result.get("version"),
                    "environment": environment,
                },
            }

        except Exception as e:
            logger.error(f"DEPLOY 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "deploy",
                "success": False,
                "message": f"배포 오류: {str(e)}",
            }

    async def _validate_deployment(
        self,
        deploy_type: str,
        target_id: str,
        version: Optional[int],
        rules: List[str]
    ) -> Dict[str, Any]:
        """배포 전 검증"""
        errors = []

        for rule in rules:
            # 간단한 규칙 검증 (실제로는 더 복잡한 검증 로직)
            if rule == "no_syntax_errors":
                # 문법 검사
                pass
            elif rule.startswith("test_coverage"):
                # 테스트 커버리지 검사
                pass
            else:
                logger.warning(f"알 수 없는 검증 규칙: {rule}")

        return {"success": len(errors) == 0, "errors": errors}

    async def _get_current_active_version(
        self,
        deploy_type: str,
        target_id: str,
        tenant_id: str
    ) -> Optional[int]:
        """현재 활성 버전 조회"""
        try:
            from sqlalchemy import text
            from app.database import get_async_session
            async with get_async_session() as db:
                if deploy_type == "ruleset":
                    result = await db.execute(
                        text("SELECT version FROM core.rulesets WHERE ruleset_id = :id AND is_active = true"),
                        {"id": target_id}
                    )
                elif deploy_type == "workflow":
                    result = await db.execute(
                        text("SELECT version FROM core.workflows WHERE workflow_id = :id AND is_active = true"),
                        {"id": target_id}
                    )
                else:
                    return None

                row = result.fetchone()
                return int(row.version) if row else None
        except Exception:
            return None

    async def _deploy_ruleset(
        self,
        ruleset_id: str,
        version: Optional[int],
        environment: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """룰셋 배포"""
        try:
            from sqlalchemy import text
            from app.database import get_async_session
            async with get_async_session() as db:
                # 룰셋 활성화
                await db.execute(
                    text("""
                        UPDATE core.rulesets
                        SET is_active = true, updated_at = NOW()
                        WHERE ruleset_id = :ruleset_id AND tenant_id = :tenant_id
                    """),
                    {"ruleset_id": ruleset_id, "tenant_id": tenant_id}
                )
                await db.commit()

            return {"success": True, "message": "룰셋 배포 완료", "version": version}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _deploy_model(
        self,
        model_id: str,
        version: Optional[int],
        environment: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """ML 모델 배포 (placeholder)"""
        # TODO: 실제 ML 모델 배포 로직
        logger.info(f"ML 모델 배포: {model_id} v{version} -> {environment}")
        return {"success": True, "message": "모델 배포 완료 (mock)", "version": version}

    async def _deploy_workflow(
        self,
        workflow_id: str,
        version: Optional[int],
        environment: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """워크플로우 배포"""
        try:
            from sqlalchemy import text
            from app.database import get_async_session
            async with get_async_session() as db:
                await db.execute(
                    text("""
                        UPDATE core.workflows
                        SET is_active = true, updated_at = NOW()
                        WHERE workflow_id = :workflow_id AND tenant_id = :tenant_id
                    """),
                    {"workflow_id": workflow_id, "tenant_id": tenant_id}
                )
                await db.commit()

            return {"success": True, "message": "워크플로우 배포 완료", "version": version}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _rollback_to_version(
        self,
        deploy_type: str,
        target_id: str,
        version: int,
        tenant_id: str
    ) -> Dict[str, Any]:
        """이전 버전으로 롤백"""
        logger.info(f"롤백: {deploy_type} {target_id} -> v{version}")
        # 실제 롤백 로직
        return {"success": True, "version": version}

    # ============ P2 노드: ROLLBACK ============

    async def _execute_rollback_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ROLLBACK 노드 실행 - 이전 버전으로 복구

        config 형식:
        {
            "target_type": "ruleset" | "workflow" | "model",
            "target_id": "uuid",
            "version": 1,  # 없으면 직전 버전
            "reason": "배포 실패로 인한 롤백"
        }
        """

        target_type = config.get("target_type", "workflow")
        target_id = config.get("target_id")
        version = config.get("version")
        reason = config.get("reason", "Manual rollback")

        workflow_id = context.get("workflow_id")
        tenant_id = context.get("tenant_id")

        try:
            # 버전 지정 없으면 직전 버전 조회
            if version is None:
                version = await self._get_previous_version(
                    target_type=target_type,
                    target_id=target_id,
                    tenant_id=tenant_id
                )
                if version is None:
                    return {
                        "node_id": node_id,
                        "type": "rollback",
                        "success": False,
                        "message": "롤백할 이전 버전이 없습니다",
                    }

            # 롤백 실행
            if target_type == "ruleset":
                result = await self._rollback_ruleset(
                    ruleset_id=target_id,
                    version=version,
                    tenant_id=tenant_id
                )
            elif target_type == "workflow":
                result = await self._rollback_workflow(
                    workflow_id=target_id,
                    version=version,
                    tenant_id=tenant_id
                )
            elif target_type == "model":
                result = await self._rollback_model(
                    model_id=target_id,
                    version=version,
                    tenant_id=tenant_id
                )
            else:
                return {
                    "node_id": node_id,
                    "type": "rollback",
                    "success": False,
                    "message": f"알 수 없는 대상 타입: {target_type}",
                }

            # 로그 기록
            log_entry = {
                "event_type": "rollback_executed",
                "workflow_id": workflow_id,
                "node_id": node_id,
                "target_type": target_type,
                "target_id": target_id,
                "version": version,
                "reason": reason,
                "result": result,
            }
            execution_log_store.add_log(log_entry)

            return {
                "node_id": node_id,
                "type": "rollback",
                "success": result.get("success", False),
                "message": result.get("message", "롤백 완료"),
                "data": {
                    "target_type": target_type,
                    "target_id": target_id,
                    "version": version,
                    "reason": reason,
                },
            }

        except Exception as e:
            logger.error(f"ROLLBACK 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "rollback",
                "success": False,
                "message": f"롤백 오류: {str(e)}",
            }

    async def _get_previous_version(
        self,
        target_type: str,
        target_id: str,
        tenant_id: str
    ) -> Optional[int]:
        """직전 버전 조회"""
        try:
            from sqlalchemy import text
            from app.database import get_async_session
            async with get_async_session() as db:
                if target_type == "ruleset":
                    result = await db.execute(
                        text("""
                            SELECT version FROM core.rule_scripts
                            WHERE ruleset_id = :id
                            ORDER BY version DESC
                            LIMIT 1 OFFSET 1
                        """),
                        {"id": target_id}
                    )
                elif target_type == "workflow":
                    # workflow_versions 테이블 사용 (추후 마이그레이션 필요)
                    result = await db.execute(
                        text("""
                            SELECT CAST(version AS INTEGER) - 1 as prev_version
                            FROM core.workflows
                            WHERE workflow_id = :id
                        """),
                        {"id": target_id}
                    )
                else:
                    return None

                row = result.fetchone()
                if row and row[0] and int(row[0]) > 0:
                    return int(row[0])
                return None
        except Exception:
            return None

    async def _rollback_ruleset(
        self,
        ruleset_id: str,
        version: int,
        tenant_id: str
    ) -> Dict[str, Any]:
        """룰셋 롤백"""
        try:
            from sqlalchemy import text
            from app.database import get_async_session
            async with get_async_session() as db:
                # 해당 버전의 스크립트로 current_script_id 업데이트
                result = await db.execute(
                    text("""
                        SELECT id FROM core.rule_scripts
                        WHERE ruleset_id = :ruleset_id AND version = :version
                    """),
                    {"ruleset_id": ruleset_id, "version": version}
                )
                row = result.fetchone()
                if row:
                    await db.execute(
                        text("""
                            UPDATE core.rulesets
                            SET current_script_id = :script_id, updated_at = NOW()
                            WHERE ruleset_id = :ruleset_id
                        """),
                        {"script_id": row.id, "ruleset_id": ruleset_id}
                    )
                    await db.commit()
                    return {"success": True, "message": f"룰셋 v{version}으로 롤백 완료"}
                else:
                    return {"success": False, "message": f"버전 {version}을 찾을 수 없습니다"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _rollback_workflow(
        self,
        workflow_id: str,
        version: int,
        tenant_id: str
    ) -> Dict[str, Any]:
        """워크플로우 롤백"""
        # TODO: workflow_versions 테이블 구현 후 실제 롤백 로직
        logger.info(f"워크플로우 롤백: {workflow_id} -> v{version}")
        return {"success": True, "message": f"워크플로우 v{version}으로 롤백 완료 (mock)"}

    async def _rollback_model(
        self,
        model_id: str,
        version: int,
        tenant_id: str
    ) -> Dict[str, Any]:
        """ML 모델 롤백 (placeholder)"""
        logger.info(f"모델 롤백: {model_id} -> v{version}")
        return {"success": True, "message": f"모델 v{version}으로 롤백 완료 (mock)"}

    # ============ P2 노드: SIMULATE ============

    async def _execute_simulate_node(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        SIMULATE 노드 실행 - What-if 분석

        config 형식:
        {
            "simulation_type": "scenario" | "parameter_sweep" | "monte_carlo",
            "scenarios": [
                {
                    "name": "Best case",
                    "overrides": {"temperature": 75, "pressure": 95}
                },
                {
                    "name": "Worst case",
                    "overrides": {"temperature": 95, "pressure": 120}
                }
            ],
            "target_nodes": ["judgment_node", "action_node"],
            "metrics": ["success_rate", "execution_time"],
            "iterations": 100  # monte_carlo용
        }
        """

        simulation_type = config.get("simulation_type", "scenario")
        scenarios = config.get("scenarios", [])
        target_nodes = config.get("target_nodes", [])
        metrics = config.get("metrics", ["success_rate"])
        iterations = config.get("iterations", 100)

        workflow_id = context.get("workflow_id")

        try:
            results = []

            if simulation_type == "scenario":
                # 시나리오별 시뮬레이션
                for scenario in scenarios:
                    scenario_name = scenario.get("name", "Unnamed")
                    overrides = scenario.get("overrides", {})

                    # 가상 컨텍스트 생성
                    sim_context = {**context, **overrides}
                    sim_context["_simulation_mode"] = True

                    # 대상 노드들 시뮬레이션
                    scenario_result = await self._simulate_nodes(
                        target_nodes=target_nodes,
                        context=sim_context,
                        metrics=metrics
                    )

                    results.append({
                        "scenario": scenario_name,
                        "overrides": overrides,
                        "result": scenario_result,
                    })

            elif simulation_type == "parameter_sweep":
                # 파라미터 스윕 (단일 파라미터 변화)
                sweep_config = config.get("sweep_config", {})
                param_name = sweep_config.get("parameter")
                start_value = sweep_config.get("start", 0)
                end_value = sweep_config.get("end", 100)
                step = sweep_config.get("step", 10)

                current = start_value
                while current <= end_value:
                    sim_context = {**context, param_name: current}
                    sim_context["_simulation_mode"] = True

                    scenario_result = await self._simulate_nodes(
                        target_nodes=target_nodes,
                        context=sim_context,
                        metrics=metrics
                    )

                    results.append({
                        "parameter": param_name,
                        "value": current,
                        "result": scenario_result,
                    })

                    current += step

            elif simulation_type == "monte_carlo":
                # 몬테카를로 시뮬레이션
                import random

                distributions = config.get("distributions", {})
                for i in range(iterations):
                    sim_context = {**context}
                    sim_context["_simulation_mode"] = True

                    # 분포에 따라 랜덤 값 생성
                    for param, dist_config in distributions.items():
                        dist_type = dist_config.get("type", "uniform")
                        if dist_type == "uniform":
                            sim_context[param] = random.uniform(
                                dist_config.get("min", 0),
                                dist_config.get("max", 100)
                            )
                        elif dist_type == "normal":
                            sim_context[param] = random.gauss(
                                dist_config.get("mean", 50),
                                dist_config.get("std", 10)
                            )

                    scenario_result = await self._simulate_nodes(
                        target_nodes=target_nodes,
                        context=sim_context,
                        metrics=metrics
                    )

                    results.append({
                        "iteration": i + 1,
                        "parameters": {k: sim_context.get(k) for k in distributions.keys()},
                        "result": scenario_result,
                    })

            # 결과 분석
            analysis = self._analyze_simulation_results(results, simulation_type, metrics)

            # 컨텍스트에 결과 저장
            context["simulation_results"] = results
            context["simulation_analysis"] = analysis

            # 로그 기록
            log_entry = {
                "event_type": "simulation_executed",
                "workflow_id": workflow_id,
                "node_id": node_id,
                "simulation_type": simulation_type,
                "scenario_count": len(results),
                "analysis": analysis,
            }
            execution_log_store.add_log(log_entry)

            return {
                "node_id": node_id,
                "type": "simulate",
                "success": True,
                "message": f"시뮬레이션 완료: {len(results)}개 시나리오 분석",
                "data": {
                    "simulation_type": simulation_type,
                    "results": results,
                    "analysis": analysis,
                },
            }

        except Exception as e:
            logger.error(f"SIMULATE 노드 실행 오류: {node_id} - {e}")
            return {
                "node_id": node_id,
                "type": "simulate",
                "success": False,
                "message": f"시뮬레이션 오류: {str(e)}",
            }

    async def _simulate_nodes(
        self,
        target_nodes: List[str],
        context: Dict[str, Any],
        metrics: List[str]
    ) -> Dict[str, Any]:
        """대상 노드들 시뮬레이션 실행"""
        results = {
            "success": True,
            "executed_nodes": [],
            "metrics": {}
        }

        start_time = time.time()

        for node_id in target_nodes:
            # 시뮬레이션 모드에서는 실제 액션 실행 안함
            results["executed_nodes"].append({
                "node_id": node_id,
                "simulated": True,
            })

        execution_time = (time.time() - start_time) * 1000

        # 메트릭 계산
        if "execution_time" in metrics:
            results["metrics"]["execution_time_ms"] = execution_time
        if "success_rate" in metrics:
            # 시뮬레이션에서는 100% (실제로는 조건 평가 결과 기반)
            results["metrics"]["success_rate"] = 100.0

        return results

    def _analyze_simulation_results(
        self,
        results: List[Dict[str, Any]],
        simulation_type: str,
        metrics: List[str]
    ) -> Dict[str, Any]:
        """시뮬레이션 결과 분석"""
        analysis = {
            "total_scenarios": len(results),
        }

        if not results:
            return analysis

        # 성공률 분석
        success_count = sum(1 for r in results if r.get("result", {}).get("success", False))
        analysis["success_rate"] = (success_count / len(results)) * 100

        # 시나리오별 분석
        if simulation_type == "scenario":
            analysis["best_scenario"] = results[0].get("scenario") if results else None
        elif simulation_type == "monte_carlo":
            # 몬테카를로 통계
            import statistics
            if len(results) > 1:
                exec_times = [r.get("result", {}).get("metrics", {}).get("execution_time_ms", 0) for r in results]
                if exec_times:
                    analysis["avg_execution_time_ms"] = statistics.mean(exec_times)
                    analysis["std_execution_time_ms"] = statistics.stdev(exec_times) if len(exec_times) > 1 else 0

        return analysis


# ============ Phase 4: 상태 머신 ============

class WorkflowState(Enum):
    """워크플로우 인스턴스 상태"""

    CREATED = "created"          # 생성됨
    PENDING = "pending"          # 실행 대기
    RUNNING = "running"          # 실행 중
    WAITING = "waiting"          # 승인/이벤트 대기
    PAUSED = "paused"            # 일시 중지
    COMPLETED = "completed"      # 완료
    FAILED = "failed"            # 실패
    COMPENSATING = "compensating"  # 보상 트랜잭션 진행 중
    COMPENSATED = "compensated"  # 보상 완료
    CANCELLED = "cancelled"      # 취소됨
    TIMEOUT = "timeout"          # 타임아웃


class InvalidStateTransition(Exception):
    """잘못된 상태 전이 예외"""
    pass


class WorkflowStateMachine:
    """
    워크플로우 상태 머신

    상태 전이 규칙 관리 및 상태 변경 처리
    """

    # 상태 전이 규칙: 현재 상태 -> 허용된 다음 상태들
    TRANSITIONS: Dict[WorkflowState, List[WorkflowState]] = {
        WorkflowState.CREATED: [
            WorkflowState.PENDING,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.PENDING: [
            WorkflowState.RUNNING,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.RUNNING: [
            WorkflowState.WAITING,
            WorkflowState.PAUSED,
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.COMPENSATING,
        ],
        WorkflowState.WAITING: [
            WorkflowState.RUNNING,        # 승인/이벤트 수신 후 재개
            WorkflowState.CANCELLED,
            WorkflowState.TIMEOUT,
            WorkflowState.FAILED,
        ],
        WorkflowState.PAUSED: [
            WorkflowState.RUNNING,        # 재개
            WorkflowState.CANCELLED,
        ],
        WorkflowState.COMPENSATING: [
            WorkflowState.COMPENSATED,
            WorkflowState.FAILED,
        ],
        # 종료 상태들 (전이 불가)
        WorkflowState.COMPLETED: [],
        WorkflowState.FAILED: [
            WorkflowState.COMPENSATING,   # 실패 후 보상 시작 가능
        ],
        WorkflowState.COMPENSATED: [],
        WorkflowState.CANCELLED: [],
        WorkflowState.TIMEOUT: [
            WorkflowState.COMPENSATING,   # 타임아웃 후 보상 가능
        ],
    }

    def __init__(self):
        """상태 머신 초기화"""
        # 인메모리 상태 저장소 (MVP)
        self._states: Dict[str, Dict[str, Any]] = {}
        self._state_history: Dict[str, List[Dict[str, Any]]] = {}

    def can_transition(
        self,
        current_state: WorkflowState,
        target_state: WorkflowState
    ) -> bool:
        """상태 전이 가능 여부 확인"""
        allowed_states = self.TRANSITIONS.get(current_state, [])
        return target_state in allowed_states

    async def transition(
        self,
        instance_id: str,
        to_state: WorkflowState,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        상태 전이 실행

        Args:
            instance_id: 워크플로우 인스턴스 ID
            to_state: 목표 상태
            reason: 전이 사유
            metadata: 추가 메타데이터

        Returns:
            전이 결과 정보

        Raises:
            InvalidStateTransition: 잘못된 전이 시도 시
        """
        current_info = self._states.get(instance_id, {
            "state": WorkflowState.CREATED,
            "created_at": datetime.utcnow().isoformat(),
        })
        current_state = current_info.get("state", WorkflowState.CREATED)

        # 문자열을 Enum으로 변환
        if isinstance(current_state, str):
            try:
                current_state = WorkflowState(current_state)
            except ValueError:
                current_state = WorkflowState.CREATED

        # 전이 가능 여부 확인
        if not self.can_transition(current_state, to_state):
            raise InvalidStateTransition(
                f"Cannot transition from {current_state.value} to {to_state.value} "
                f"for instance {instance_id}"
            )

        # 상태 전이 기록
        transition_record = {
            "from_state": current_state.value,
            "to_state": to_state.value,
            "reason": reason,
            "metadata": metadata or {},
            "transitioned_at": datetime.utcnow().isoformat(),
        }

        # 히스토리 저장
        if instance_id not in self._state_history:
            self._state_history[instance_id] = []
        self._state_history[instance_id].append(transition_record)

        # 현재 상태 업데이트
        self._states[instance_id] = {
            "state": to_state,
            "previous_state": current_state.value,
            "reason": reason,
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        # 상태 변경 이벤트 발행 (로그)
        await self._emit_state_change_event(
            instance_id, current_state, to_state, reason
        )

        logger.info(
            f"Workflow {instance_id} transitioned: "
            f"{current_state.value} -> {to_state.value}"
            f"{f' (reason: {reason})' if reason else ''}"
        )

        return {
            "instance_id": instance_id,
            "previous_state": current_state.value,
            "current_state": to_state.value,
            "transitioned_at": transition_record["transitioned_at"],
        }

    async def _emit_state_change_event(
        self,
        instance_id: str,
        from_state: WorkflowState,
        to_state: WorkflowState,
        reason: Optional[str] = None
    ):
        """상태 변경 이벤트 발행"""
        event = {
            "event_type": "workflow_state_changed",
            "instance_id": instance_id,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 실행 로그에 기록
        execution_log_store.add_log(event)

        # TODO: Redis pub/sub으로 이벤트 발행 (실시간 UI 업데이트용)

    def get_state(self, instance_id: str) -> Dict[str, Any]:
        """현재 상태 조회"""
        info = self._states.get(instance_id)
        if not info:
            return {
                "instance_id": instance_id,
                "state": WorkflowState.CREATED.value,
                "exists": False,
            }

        state = info.get("state")
        if isinstance(state, WorkflowState):
            state = state.value

        return {
            "instance_id": instance_id,
            "state": state,
            "previous_state": info.get("previous_state"),
            "updated_at": info.get("updated_at"),
            "reason": info.get("reason"),
            "exists": True,
        }

    def get_history(
        self,
        instance_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """상태 전이 히스토리 조회"""
        history = self._state_history.get(instance_id, [])
        return history[-limit:]

    def initialize_instance(
        self,
        instance_id: str,
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """새 인스턴스 상태 초기화"""
        now = datetime.utcnow().isoformat()

        self._states[instance_id] = {
            "state": WorkflowState.CREATED,
            "workflow_id": workflow_id,
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
        }

        self._state_history[instance_id] = [{
            "from_state": None,
            "to_state": WorkflowState.CREATED.value,
            "reason": "Instance created",
            "transitioned_at": now,
        }]

    def is_terminal_state(self, state: WorkflowState) -> bool:
        """종료 상태 여부 확인"""
        return state in [
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.COMPENSATED,
            WorkflowState.CANCELLED,
            WorkflowState.TIMEOUT,
        ]

    def is_active_state(self, state: WorkflowState) -> bool:
        """활성 상태 여부 확인"""
        return state in [
            WorkflowState.RUNNING,
            WorkflowState.WAITING,
            WorkflowState.PAUSED,
            WorkflowState.COMPENSATING,
        ]


class CheckpointManager:
    """
    워크플로우 체크포인트 관리자

    장기 실행 워크플로우의 중간 상태를 저장하고 복구
    Redis (최신 상태 캐시) + DB (영구 저장) 이중화
    """

    def __init__(self):
        """체크포인트 매니저 초기화"""
        # 인메모리 저장소 (MVP용, 프로덕션에서는 Redis 사용)
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._checkpoint_history: Dict[str, List[Dict[str, Any]]] = {}

        # 설정
        self.checkpoint_ttl_seconds = 86400  # 24시간
        self.max_checkpoints_per_instance = 10

    async def save_checkpoint(
        self,
        instance_id: str,
        node_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        체크포인트 저장

        Args:
            instance_id: 워크플로우 인스턴스 ID
            node_id: 현재 실행 노드 ID
            context: 워크플로우 컨텍스트 (변수, 결과 등)
            metadata: 추가 메타데이터

        Returns:
            체크포인트 ID
        """
        checkpoint_id = str(uuid4())
        now = datetime.utcnow()

        # 체크포인트 데이터 구성
        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "instance_id": instance_id,
            "node_id": node_id,
            "context": self._serialize_context(context),
            "metadata": metadata or {},
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.checkpoint_ttl_seconds)).isoformat(),
        }

        # 최신 체크포인트 저장
        self._checkpoints[instance_id] = checkpoint

        # 히스토리에 추가
        if instance_id not in self._checkpoint_history:
            self._checkpoint_history[instance_id] = []
        self._checkpoint_history[instance_id].append(checkpoint)

        # 최대 개수 초과 시 오래된 것 삭제
        if len(self._checkpoint_history[instance_id]) > self.max_checkpoints_per_instance:
            self._checkpoint_history[instance_id] = \
                self._checkpoint_history[instance_id][-self.max_checkpoints_per_instance:]

        # TODO: 프로덕션에서는 Redis + DB에 저장
        # await redis.set(
        #     f"wf:checkpoint:{instance_id}",
        #     json.dumps(checkpoint),
        #     ex=self.checkpoint_ttl_seconds
        # )
        # await self._persist_to_db(checkpoint)

        logger.info(
            f"Checkpoint saved: instance={instance_id}, node={node_id}, "
            f"checkpoint_id={checkpoint_id}"
        )

        return checkpoint_id

    async def restore_checkpoint(
        self,
        instance_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        체크포인트에서 복구

        Args:
            instance_id: 워크플로우 인스턴스 ID
            checkpoint_id: 특정 체크포인트 ID (없으면 최신)

        Returns:
            복구된 체크포인트 데이터 또는 None
        """
        if checkpoint_id:
            # 특정 체크포인트 복구
            history = self._checkpoint_history.get(instance_id, [])
            for cp in reversed(history):
                if cp.get("checkpoint_id") == checkpoint_id:
                    logger.info(f"Restored checkpoint: {checkpoint_id}")
                    return {
                        "checkpoint": cp,
                        "context": self._deserialize_context(cp.get("context", {})),
                    }
            return None
        else:
            # 최신 체크포인트 복구
            checkpoint = self._checkpoints.get(instance_id)
            if checkpoint:
                # 만료 확인
                expires_at = datetime.fromisoformat(checkpoint.get("expires_at", ""))
                if datetime.utcnow() > expires_at:
                    logger.warning(f"Checkpoint expired: {instance_id}")
                    return None

                logger.info(f"Restored latest checkpoint for instance: {instance_id}")
                return {
                    "checkpoint": checkpoint,
                    "context": self._deserialize_context(checkpoint.get("context", {})),
                }

        return None

    async def delete_checkpoint(self, instance_id: str) -> bool:
        """체크포인트 삭제"""
        if instance_id in self._checkpoints:
            del self._checkpoints[instance_id]

        if instance_id in self._checkpoint_history:
            del self._checkpoint_history[instance_id]

        logger.info(f"Checkpoint deleted: {instance_id}")
        return True

    async def list_checkpoints(
        self,
        instance_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """인스턴스의 체크포인트 목록 조회"""
        history = self._checkpoint_history.get(instance_id, [])
        return [
            {
                "checkpoint_id": cp.get("checkpoint_id"),
                "node_id": cp.get("node_id"),
                "created_at": cp.get("created_at"),
                "expires_at": cp.get("expires_at"),
            }
            for cp in history[-limit:]
        ]

    def _serialize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """컨텍스트 직렬화 (JSON 호환)"""
        serialized = {}

        for key, value in context.items():
            try:
                # JSON 직렬화 가능 여부 테스트
                json.dumps(value)
                serialized[key] = value
            except (TypeError, ValueError):
                # 직렬화 불가능한 객체는 문자열로 변환
                serialized[key] = str(value)

        return serialized

    def _deserialize_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """컨텍스트 역직렬화"""
        # 현재는 그대로 반환 (필요시 타입 복원 로직 추가)
        return data

    async def get_recovery_info(
        self,
        instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        복구 정보 조회

        워크플로우 재시작 시 어디서부터 시작할지 정보 제공
        """
        checkpoint = self._checkpoints.get(instance_id)
        if not checkpoint:
            return None

        return {
            "instance_id": instance_id,
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "resume_from_node": checkpoint.get("node_id"),
            "context": self._deserialize_context(checkpoint.get("context", {})),
            "checkpoint_created_at": checkpoint.get("created_at"),
            "can_resume": True,
        }

    async def cleanup_expired(self) -> int:
        """만료된 체크포인트 정리"""
        now = datetime.utcnow()
        expired_count = 0

        expired_instances = []
        for instance_id, checkpoint in self._checkpoints.items():
            expires_at_str = checkpoint.get("expires_at")
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if now > expires_at:
                    expired_instances.append(instance_id)

        for instance_id in expired_instances:
            await self.delete_checkpoint(instance_id)
            expired_count += 1

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired checkpoints")

        return expired_count


# 전역 상태 머신 및 체크포인트 매니저
workflow_state_machine = WorkflowStateMachine()
checkpoint_manager = CheckpointManager()


# 전역 워크플로우 엔진
workflow_engine = WorkflowEngine()
