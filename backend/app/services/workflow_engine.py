"""
워크플로우 실행 엔진
조건 평가 및 액션 실행

지원 노드 타입:
- condition: 조건 평가 (순차 진행)
- action: 액션 실행
- if_else: 조건 분기 (then/else 브랜치)
- loop: 반복 실행 (조건 기반 또는 횟수 기반)
- parallel: 병렬 실행
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
            # 분석 액션 (Mock)
            "calculate_defect_rate": self._calculate_defect_rate,
            "analyze_sensor_trend": self._analyze_sensor_trend,
            "predict_equipment_failure": self._predict_equipment_failure,
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
        """센서 추세 분석 (Mock)"""
        sensor_type = params.get("sensor_type", "temperature")
        hours = params.get("hours", 24)

        import random
        trend = random.choice(["increasing", "decreasing", "stable"])

        return {
            "message": f"센서 추세 분석 완료: {sensor_type}",
            "data": {
                "sensor_type": sensor_type,
                "hours_analyzed": hours,
                "trend": trend,
                "average": round(random.uniform(40, 80), 2),
                "min": round(random.uniform(20, 40), 2),
                "max": round(random.uniform(80, 100), 2),
            },
        }

    async def _predict_equipment_failure(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """장비 고장 예측 (Mock)"""
        equipment_id = params.get("equipment_id", "EQUIP_01")

        import random
        failure_probability = round(random.uniform(0, 0.5), 3)
        days_to_failure = random.randint(7, 90) if failure_probability < 0.3 else random.randint(1, 7)

        return {
            "message": f"장비 고장 예측 완료: {equipment_id}",
            "data": {
                "equipment_id": equipment_id,
                "failure_probability": failure_probability,
                "estimated_days_to_failure": days_to_failure,
                "recommendation": "유지보수 권장" if failure_probability > 0.2 else "정상 운영",
            },
        }


# 전역 액션 실행기
action_executor = ActionExecutor()


# ============ 워크플로우 실행기 ============

class WorkflowEngine:
    """
    워크플로우 실행 엔진
    조건 평가 + 액션 실행 통합

    지원 노드 타입:
    - condition: 조건 평가 (순차 진행, 실패 시 워크플로우 중단)
    - action: 액션 실행
    - if_else: 조건 분기 (then/else 브랜치)
    - loop: 반복 실행 (조건 기반 while 또는 횟수 기반 for)
    - parallel: 병렬 실행
    """

    # Loop 최대 반복 횟수 (무한 루프 방지)
    MAX_LOOP_ITERATIONS = 100

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


# 전역 워크플로우 엔진
workflow_engine = WorkflowEngine()
