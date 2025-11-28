"""
워크플로우 실행 엔진
조건 평가 및 액션 실행
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


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
        """데이터베이스 저장 (Mock)"""
        table = params.get("table", "default")
        data = params.get("data", {})

        # MVP: 실제 저장 없이 로그만 기록
        log_entry = {
            "event_type": "database_save",
            "details": {"table": table, "data": data},
            "context": context,
            "workflow_id": context.get("workflow_id"),
        }
        execution_log_store.add_log(log_entry)

        return {
            "message": f"데이터 저장됨 (Mock): {table}",
            "data": {"table": table, "rows_affected": 1},
        }

    async def _export_to_csv(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """CSV 내보내기 (Mock)"""
        filename = params.get("filename", "export.csv")
        data = params.get("data", [])

        return {
            "message": f"CSV 파일 생성됨 (Mock): {filename}",
            "data": {"filename": filename, "rows": len(data) if isinstance(data, list) else 0},
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
    """

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
        results = []
        executed_count = 0
        skipped_count = 0
        failed = False
        error_message = None

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_type = node.get("type")
            config = node.get("config", {})

            context["node_id"] = node_id

            if node_type == "condition":
                # 조건 평가
                condition = config.get("condition", "")
                result, msg = self.condition_evaluator.evaluate(condition, context)

                results.append({
                    "node_id": node_id,
                    "type": "condition",
                    "condition": condition,
                    "result": result,
                    "message": msg,
                })

                if not result:
                    # 조건 불충족 시 이후 노드 실행 안 함
                    skipped_count += len(nodes) - len(results)
                    break

                executed_count += 1

            elif node_type == "action":
                # 액션 실행
                action_name = config.get("action", "")
                parameters = config.get("parameters", {})

                # 알림 액션은 별도 처리 (notifications.py에서 처리)
                if action_name in ["send_slack_notification", "send_email", "send_sms"]:
                    results.append({
                        "node_id": node_id,
                        "type": "action",
                        "action": action_name,
                        "status": "delegated",
                        "message": "알림 액션은 notification_manager에서 처리",
                    })
                else:
                    # 기타 액션 직접 실행
                    action_result = await self.action_executor.execute(
                        action_name, parameters, context
                    )

                    results.append({
                        "node_id": node_id,
                        "type": "action",
                        **action_result,
                    })

                    if not action_result.get("success", False):
                        failed = True
                        error_message = action_result.get("message")
                        break

                executed_count += 1

        execution_time_ms = int((time.time() - start_time) * 1000)

        return {
            "workflow_id": workflow_id,
            "status": "failed" if failed else "completed",
            "input_data": input_data,
            "nodes_total": len(nodes),
            "nodes_executed": executed_count,
            "nodes_skipped": skipped_count,
            "results": results,
            "error_message": error_message,
            "execution_time_ms": execution_time_ms,
            "executed_at": datetime.utcnow().isoformat(),
        }


# 전역 워크플로우 엔진
workflow_engine = WorkflowEngine()
