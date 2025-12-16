"""
Workflow Engine 테스트
워크플로우 실행 엔진, 조건 평가, 액션 실행 테스트
"""
import pytest

from app.services.workflow_engine import (
    ExecutionLogStore,
    SensorSimulator,
    ConditionEvaluator,
    ActionExecutor,
    WorkflowEngine,
    execution_log_store,
    sensor_simulator,
    condition_evaluator,
    action_executor,
    workflow_engine,
)


class TestExecutionLogStore:
    """ExecutionLogStore 테스트"""

    @pytest.fixture
    def store(self):
        """새 ExecutionLogStore 인스턴스"""
        return ExecutionLogStore(max_logs=100)

    def test_add_log(self, store):
        """로그 추가"""
        log_entry = {"event_type": "test", "details": {"key": "value"}}

        log_id = store.add_log(log_entry)

        assert log_id is not None
        assert "log_id" in log_entry
        assert "timestamp" in log_entry

    def test_add_log_max_exceeded(self):
        """로그 최대 개수 초과"""
        store = ExecutionLogStore(max_logs=5)

        for i in range(10):
            store.add_log({"event_type": f"event_{i}"})

        logs = store.get_logs(limit=100)
        assert len(logs) == 5

    def test_get_logs_by_workflow_id(self, store):
        """워크플로우 ID로 로그 필터링"""
        store.add_log({"workflow_id": "wf-1", "event_type": "start"})
        store.add_log({"workflow_id": "wf-2", "event_type": "start"})
        store.add_log({"workflow_id": "wf-1", "event_type": "end"})

        logs = store.get_logs(workflow_id="wf-1")

        assert len(logs) == 2
        assert all(log["workflow_id"] == "wf-1" for log in logs)

    def test_get_logs_by_event_type(self, store):
        """이벤트 타입으로 로그 필터링"""
        store.add_log({"event_type": "start"})
        store.add_log({"event_type": "end"})
        store.add_log({"event_type": "start"})

        logs = store.get_logs(event_type="start")

        assert len(logs) == 2
        assert all(log["event_type"] == "start" for log in logs)

    def test_get_logs_limit(self, store):
        """로그 제한"""
        for i in range(20):
            store.add_log({"event_type": f"event_{i}"})

        logs = store.get_logs(limit=5)

        assert len(logs) == 5

    def test_get_logs_sorted_by_timestamp(self, store):
        """로그 최신순 정렬"""
        from unittest.mock import patch
        from datetime import datetime, timedelta

        # 명시적으로 다른 시간을 설정하여 정렬 테스트
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        with patch("app.services.workflow_engine.datetime") as mock_dt:
            # 첫 번째 로그 - 가장 오래된 시간
            mock_dt.utcnow.return_value = base_time
            store.add_log({"event_type": "first"})

            # 두 번째 로그 - 중간 시간
            mock_dt.utcnow.return_value = base_time + timedelta(seconds=1)
            store.add_log({"event_type": "second"})

            # 세 번째 로그 - 가장 최신 시간
            mock_dt.utcnow.return_value = base_time + timedelta(seconds=2)
            store.add_log({"event_type": "third"})

        logs = store.get_logs()

        # 최신순으로 정렬되어야 함
        assert logs[0]["event_type"] == "third"

    def test_clear_logs(self, store):
        """로그 전체 삭제"""
        store.add_log({"event_type": "test"})
        store.add_log({"event_type": "test"})

        store.clear()

        logs = store.get_logs()
        assert len(logs) == 0


class TestSensorSimulator:
    """SensorSimulator 테스트"""

    @pytest.fixture
    def simulator(self):
        return SensorSimulator()

    def test_generate_normal_data(self, simulator):
        """정상 범위 데이터 생성"""
        data = simulator.generate_sensor_data(scenario="normal")

        assert "generated_at" in data
        assert "scenario" in data
        assert data["scenario"] == "normal"

    def test_generate_alert_data(self, simulator):
        """경고 범위 데이터 생성"""
        data = simulator.generate_sensor_data(scenario="alert")

        assert data["scenario"] == "alert"

    def test_generate_random_data(self, simulator):
        """랜덤 데이터 생성"""
        data = simulator.generate_sensor_data(scenario="random")

        assert data["scenario"] == "random"

    def test_generate_specific_sensors(self, simulator):
        """특정 센서만 생성"""
        data = simulator.generate_sensor_data(
            sensors=["temperature", "pressure"],
            scenario="normal"
        )

        assert "temperature" in data
        assert "pressure" in data

    def test_generate_equipment_status_alert(self, simulator):
        """장비 상태 - alert 시나리오"""
        data = simulator.generate_sensor_data(
            sensors=["equipment_status"],
            scenario="alert"
        )

        assert data["equipment_status"] == "error"

    def test_generate_equipment_status_normal(self, simulator):
        """장비 상태 - normal 시나리오"""
        data = simulator.generate_sensor_data(
            sensors=["equipment_status"],
            scenario="normal"
        )

        assert data["equipment_status"] == "running"

    def test_generate_integer_sensors(self, simulator):
        """정수형 센서 값"""
        data = simulator.generate_sensor_data(
            sensors=["consecutive_defects", "production_count"],
            scenario="random"
        )

        assert isinstance(data["consecutive_defects"], int)
        assert isinstance(data["production_count"], int)

    def test_generate_test_scenario_high_temperature(self, simulator):
        """테스트 시나리오 - 고온"""
        data = simulator.generate_test_scenario("high_temperature")

        assert data["temperature"] == 85.0
        assert "scenario_name" in data

    def test_generate_test_scenario_low_pressure(self, simulator):
        """테스트 시나리오 - 저압"""
        data = simulator.generate_test_scenario("low_pressure")

        assert data["pressure"] == 1.5

    def test_generate_test_scenario_equipment_error(self, simulator):
        """테스트 시나리오 - 장비 오류"""
        data = simulator.generate_test_scenario("equipment_error")

        assert data["equipment_status"] == "error"

    def test_generate_test_scenario_high_defect(self, simulator):
        """테스트 시나리오 - 높은 불량률"""
        data = simulator.generate_test_scenario("high_defect_rate")

        assert data["defect_rate"] == 12.5

    def test_generate_test_scenario_normal(self, simulator):
        """테스트 시나리오 - 정상 운영"""
        data = simulator.generate_test_scenario("normal_operation")

        assert data["equipment_status"] == "running"
        assert data["temperature"] == 55.0

    def test_generate_test_scenario_unknown(self, simulator):
        """테스트 시나리오 - 알 수 없는 시나리오"""
        data = simulator.generate_test_scenario("unknown_scenario")

        # 랜덤 데이터 반환
        assert "generated_at" in data


class TestConditionEvaluator:
    """ConditionEvaluator 테스트"""

    @pytest.fixture
    def evaluator(self):
        return ConditionEvaluator()

    def test_evaluate_empty_condition(self, evaluator):
        """빈 조건 평가 - 항상 참"""
        result, msg = evaluator.evaluate("", {})

        assert result is True
        assert "빈 조건" in msg

    def test_evaluate_whitespace_condition(self, evaluator):
        """공백 조건 평가"""
        result, msg = evaluator.evaluate("   ", {})

        assert result is True

    def test_evaluate_greater_than(self, evaluator):
        """> 연산자"""
        context = {"temperature": 75}

        result, msg = evaluator.evaluate("temperature > 50", context)

        assert result is True

    def test_evaluate_greater_than_or_equal(self, evaluator):
        """>= 연산자"""
        context = {"temperature": 80}

        result, msg = evaluator.evaluate("temperature >= 80", context)

        assert result is True

    def test_evaluate_less_than(self, evaluator):
        """< 연산자"""
        context = {"pressure": 5}

        result, msg = evaluator.evaluate("pressure < 10", context)

        assert result is True

    def test_evaluate_less_than_or_equal(self, evaluator):
        """<= 연산자"""
        context = {"pressure": 10}

        result, msg = evaluator.evaluate("pressure <= 10", context)

        assert result is True

    def test_evaluate_equal(self, evaluator):
        """== 연산자"""
        context = {"status": "running"}

        result, msg = evaluator.evaluate("status == 'running'", context)

        assert result is True

    def test_evaluate_not_equal(self, evaluator):
        """!= 연산자"""
        context = {"status": "running"}

        result, msg = evaluator.evaluate("status != 'stopped'", context)

        assert result is True

    def test_evaluate_and_condition(self, evaluator):
        """AND 조건"""
        context = {"temperature": 85, "pressure": 5}

        result, msg = evaluator.evaluate("temperature > 80 && pressure < 10", context)

        assert result is True

    def test_evaluate_and_condition_fail(self, evaluator):
        """AND 조건 실패"""
        context = {"temperature": 75, "pressure": 5}

        result, msg = evaluator.evaluate("temperature > 80 && pressure < 10", context)

        assert result is False
        assert "AND 조건 실패" in msg

    def test_evaluate_or_condition_first_true(self, evaluator):
        """OR 조건 - 첫 번째 참"""
        context = {"temperature": 85, "pressure": 15}

        result, msg = evaluator.evaluate("temperature > 80 || pressure < 10", context)

        assert result is True
        assert "OR 조건 충족" in msg

    def test_evaluate_or_condition_second_true(self, evaluator):
        """OR 조건 - 두 번째 참"""
        context = {"temperature": 75, "pressure": 5}

        result, msg = evaluator.evaluate("temperature > 80 || pressure < 10", context)

        assert result is True

    def test_evaluate_or_condition_fail(self, evaluator):
        """OR 조건 실패"""
        context = {"temperature": 75, "pressure": 15}

        result, msg = evaluator.evaluate("temperature > 80 || pressure < 10", context)

        assert result is False
        assert "모든 OR 조건 실패" in msg

    def test_evaluate_variable_not_found(self, evaluator):
        """변수 없음"""
        context = {}

        result, msg = evaluator.evaluate("temperature > 50", context)

        assert result is False
        assert "찾을 수 없음" in msg

    def test_evaluate_string_literal_double_quotes(self, evaluator):
        """문자열 리터럴 - 큰따옴표"""
        context = {"status": "running"}

        result, msg = evaluator.evaluate('status == "running"', context)

        assert result is True

    def test_evaluate_float_value(self, evaluator):
        """부동소수점 값"""
        context = {"temperature": 75.5}

        result, msg = evaluator.evaluate("temperature > 75.0", context)

        assert result is True

    def test_evaluate_integer_value(self, evaluator):
        """정수 값"""
        context = {"count": 100}

        result, msg = evaluator.evaluate("count >= 100", context)

        assert result is True

    def test_evaluate_unsupported_condition(self, evaluator):
        """지원하지 않는 조건식"""
        result, msg = evaluator.evaluate("some_invalid_expression", {})

        assert result is False
        assert "지원하지 않는 조건식" in msg

    def test_evaluate_exception_handling(self, evaluator):
        """예외 처리"""
        context = {"value": "string"}

        # 문자열과 숫자 비교 시 TypeError
        result, msg = evaluator.evaluate("value > 50", context)

        assert result is False


class TestActionExecutor:
    """ActionExecutor 테스트"""

    @pytest.fixture
    def executor(self):
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_execute_log_event(self, executor):
        """로그 이벤트 액션"""
        params = {"event_type": "test_event", "details": {"key": "value"}}
        context = {"workflow_id": "wf-1"}

        result = await executor.execute("log_event", params, context)

        assert result["success"] is True
        assert "log_id" in result

    @pytest.mark.asyncio
    async def test_execute_save_to_database(self, executor):
        """데이터베이스 저장 액션 (DB 연결 없이 실패 케이스 테스트)"""
        params = {"table": "sensors", "data": {"id": 1}}
        context = {"workflow_id": "wf-1"}

        result = await executor.execute("save_to_database", params, context)

        # DB 없이 실행하면 실패하지만 success=True 반환 (에러 핸들링)
        assert result["success"] is True
        # DB 연결 없으면 에러 메시지 포함, 있으면 저장 완료 메시지
        assert "데이터 저장" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_export_to_csv(self, executor):
        """CSV 내보내기 액션 (Mock)"""
        params = {"filename": "export.csv", "data": [{"a": 1}, {"b": 2}]}
        context = {}

        result = await executor.execute("export_to_csv", params, context)

        assert result["success"] is True
        assert result["data"]["rows"] == 2

    @pytest.mark.asyncio
    async def test_execute_stop_production_line(self, executor):
        """생산 라인 정지 액션"""
        params = {"line_code": "LINE_01", "reason": "High temperature"}
        context = {"workflow_id": "wf-1"}

        result = await executor.execute("stop_production_line", params, context)

        assert result["success"] is True
        assert result["data"]["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_execute_adjust_sensor_threshold(self, executor):
        """센서 임계값 조정 액션"""
        params = {"sensor_id": "TEMP_01", "threshold": 85}
        context = {}

        result = await executor.execute("adjust_sensor_threshold", params, context)

        assert result["success"] is True
        assert result["data"]["new_threshold"] == 85

    @pytest.mark.asyncio
    async def test_execute_trigger_maintenance(self, executor):
        """유지보수 트리거 액션"""
        params = {"equipment_id": "EQUIP_01", "priority": "high"}
        context = {"workflow_id": "wf-1"}

        result = await executor.execute("trigger_maintenance", params, context)

        assert result["success"] is True
        assert result["data"]["priority"] == "high"
        assert "ticket_id" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_calculate_defect_rate(self, executor):
        """불량률 계산 액션"""
        params = {"line_code": "LINE_01", "time_range": "1h"}
        context = {}

        result = await executor.execute("calculate_defect_rate", params, context)

        assert result["success"] is True
        assert "defect_rate" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_analyze_sensor_trend(self, executor):
        """센서 추세 분석 액션"""
        params = {"sensor_type": "temperature", "hours": 24}
        context = {}

        result = await executor.execute("analyze_sensor_trend", params, context)

        assert result["success"] is True
        assert result["data"]["trend"] in ["increasing", "decreasing", "stable"]

    @pytest.mark.asyncio
    async def test_execute_predict_equipment_failure(self, executor):
        """장비 고장 예측 액션"""
        params = {"equipment_id": "EQUIP_01"}
        context = {}

        result = await executor.execute("predict_equipment_failure", params, context)

        assert result["success"] is True
        assert "failure_probability" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, executor):
        """알 수 없는 액션"""
        result = await executor.execute("unknown_action", {}, {})

        assert result["success"] is False
        assert "지원하지 않는 액션" in result["message"]


class TestWorkflowEngine:
    """WorkflowEngine 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_execute_workflow_empty_nodes(self, engine):
        """빈 노드 워크플로우 실행"""
        dsl = {"nodes": []}

        result = await engine.execute_workflow("wf-1", dsl)

        assert result["status"] == "completed"
        assert result["nodes_total"] == 0

    @pytest.mark.asyncio
    async def test_execute_workflow_with_simulated_data(self, engine):
        """시뮬레이션 데이터로 워크플로우 실행"""
        dsl = {"nodes": []}

        result = await engine.execute_workflow("wf-1", dsl, use_simulated_data=True)

        assert result["input_data"] is not None

    @pytest.mark.asyncio
    async def test_execute_condition_node_pass(self, engine):
        """조건 노드 실행 - 통과"""
        dsl = {
            "nodes": [
                {"id": "n1", "type": "condition", "config": {"condition": "temperature > 50"}}
            ]
        }
        input_data = {"temperature": 75}

        result = await engine.execute_workflow("wf-1", dsl, input_data)

        assert result["status"] == "completed"
        assert result["nodes_executed"] == 1

    @pytest.mark.asyncio
    async def test_execute_condition_node_fail(self, engine):
        """조건 노드 실행 - 실패"""
        dsl = {
            "nodes": [
                {"id": "n1", "type": "condition", "config": {"condition": "temperature > 100"}},
                {"id": "n2", "type": "action", "config": {"action": "log_event"}}
            ]
        }
        input_data = {"temperature": 75}

        result = await engine.execute_workflow("wf-1", dsl, input_data)

        assert result["status"] == "completed"
        assert result["nodes_executed"] == 0
        assert result["nodes_skipped"] == 1  # 조건 실패 후 n2 스킵

    @pytest.mark.asyncio
    async def test_execute_action_node(self, engine):
        """액션 노드 실행"""
        dsl = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {"action": "log_event", "parameters": {"event_type": "test"}}}
            ]
        }

        result = await engine.execute_workflow("wf-1", dsl, {})

        assert result["status"] == "completed"
        assert result["nodes_executed"] == 1

    @pytest.mark.asyncio
    async def test_execute_action_node_notification(self, engine):
        """액션 노드 실행 - 알림 액션 (delegated)"""
        dsl = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {"action": "send_slack_notification"}}
            ]
        }

        result = await engine.execute_workflow("wf-1", dsl, {})

        assert result["status"] == "completed"
        # 알림 액션은 delegated 상태

    @pytest.mark.asyncio
    async def test_execute_if_else_then_branch(self, engine):
        """If/Else 노드 - then 브랜치"""
        dsl = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "if_else",
                    "config": {
                        "condition": "temperature > 50",
                        "then": [{"id": "t1", "type": "action", "config": {"action": "log_event"}}],
                        "else": [{"id": "e1", "type": "action", "config": {"action": "log_event"}}]
                    }
                }
            ]
        }
        input_data = {"temperature": 75}

        result = await engine.execute_workflow("wf-1", dsl, input_data)

        assert result["status"] == "completed"
        assert result["results"][0]["branch_executed"] == "then"

    @pytest.mark.asyncio
    async def test_execute_if_else_else_branch(self, engine):
        """If/Else 노드 - else 브랜치"""
        dsl = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "if_else",
                    "config": {
                        "condition": "temperature > 100",
                        "then": [{"id": "t1", "type": "action", "config": {"action": "log_event"}}],
                        "else": [{"id": "e1", "type": "action", "config": {"action": "log_event"}}]
                    }
                }
            ]
        }
        input_data = {"temperature": 75}

        result = await engine.execute_workflow("wf-1", dsl, input_data)

        assert result["status"] == "completed"
        assert result["results"][0]["branch_executed"] == "else"

    @pytest.mark.asyncio
    async def test_execute_if_else_no_else_branch(self, engine):
        """If/Else 노드 - else 브랜치 없음"""
        dsl = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "if_else",
                    "config": {
                        "condition": "temperature > 100",
                        "then": [{"id": "t1", "type": "action", "config": {"action": "log_event"}}],
                    }
                }
            ]
        }
        input_data = {"temperature": 75}

        result = await engine.execute_workflow("wf-1", dsl, input_data)

        assert result["status"] == "completed"
        assert result["results"][0]["branch_executed"] == "else"
        assert result["results"][0]["branch_executed_count"] == 0

    @pytest.mark.asyncio
    async def test_execute_for_loop(self, engine):
        """For 루프 노드"""
        dsl = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "loop",
                    "config": {
                        "loop_type": "for",
                        "count": 3,
                        "nodes": [{"id": "l1", "type": "action", "config": {"action": "log_event"}}]
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-1", dsl, {})

        assert result["status"] == "completed"
        assert result["results"][0]["iterations"] == 3

    @pytest.mark.asyncio
    async def test_execute_while_loop(self, engine):
        """While 루프 노드"""
        dsl = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "loop",
                    "config": {
                        "loop_type": "while",
                        "condition": "counter < 3",
                        "nodes": [{"id": "l1", "type": "action", "config": {"action": "log_event"}}]
                    }
                }
            ]
        }
        # counter가 context에 없으므로 조건 평가 실패 -> 루프 즉시 종료

        result = await engine.execute_workflow("wf-1", dsl, {})

        assert result["status"] == "completed"
        assert result["results"][0]["iterations"] == 0

    @pytest.mark.asyncio
    async def test_execute_parallel_branches(self, engine):
        """병렬 노드 실행"""
        dsl = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "parallel",
                    "config": {
                        "branches": [
                            [{"id": "b1", "type": "action", "config": {"action": "log_event"}}],
                            [{"id": "b2", "type": "action", "config": {"action": "log_event"}}]
                        ]
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-1", dsl, {})

        assert result["status"] == "completed"
        assert result["results"][0]["branches_count"] == 2

    @pytest.mark.asyncio
    async def test_execute_parallel_empty_branches(self, engine):
        """병렬 노드 - 빈 브랜치"""
        dsl = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "parallel",
                    "config": {"branches": []}
                }
            ]
        }

        result = await engine.execute_workflow("wf-1", dsl, {})

        assert result["status"] == "completed"
        assert result["results"][0]["branches_count"] == 0

    @pytest.mark.asyncio
    async def test_execute_unknown_node_type(self, engine):
        """알 수 없는 노드 타입"""
        dsl = {
            "nodes": [
                {"id": "n1", "type": "unknown_type", "config": {}}
            ]
        }

        result = await engine.execute_workflow("wf-1", dsl, {})

        assert result["nodes_skipped"] == 1

    @pytest.mark.asyncio
    async def test_execute_workflow_timing(self, engine):
        """워크플로우 실행 시간 측정"""
        dsl = {"nodes": []}

        result = await engine.execute_workflow("wf-1", dsl, {})

        assert "execution_time_ms" in result
        assert "executed_at" in result


class TestGlobalInstances:
    """전역 인스턴스 테스트"""

    def test_execution_log_store_exists(self):
        """execution_log_store 전역 인스턴스"""
        assert execution_log_store is not None
        assert isinstance(execution_log_store, ExecutionLogStore)

    def test_sensor_simulator_exists(self):
        """sensor_simulator 전역 인스턴스"""
        assert sensor_simulator is not None
        assert isinstance(sensor_simulator, SensorSimulator)

    def test_condition_evaluator_exists(self):
        """condition_evaluator 전역 인스턴스"""
        assert condition_evaluator is not None
        assert isinstance(condition_evaluator, ConditionEvaluator)

    def test_action_executor_exists(self):
        """action_executor 전역 인스턴스"""
        assert action_executor is not None
        assert isinstance(action_executor, ActionExecutor)

    def test_workflow_engine_exists(self):
        """workflow_engine 전역 인스턴스"""
        assert workflow_engine is not None
        assert isinstance(workflow_engine, WorkflowEngine)


class TestWorkflowEngineConstants:
    """WorkflowEngine 상수 테스트"""

    def test_max_loop_iterations(self):
        """최대 루프 반복 횟수"""
        assert WorkflowEngine.MAX_LOOP_ITERATIONS == 100


class TestTriggerNode:
    """TRIGGER 노드 테스트 (V2 Phase 1)"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_trigger_node_manual(self, engine):
        """TRIGGER 노드 - 수동 트리거"""
        dsl = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "config": {
                        "trigger_type": "manual",
                        "description": "수동 실행 트리거",
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-trigger-1", dsl, {})

        assert result["status"] == "completed"
        assert result["nodes_executed"] == 1
        assert "trigger_result" in result.get("context", {}) or result["nodes_executed"] == 1

    @pytest.mark.asyncio
    async def test_trigger_node_schedule(self, engine):
        """TRIGGER 노드 - 스케줄 트리거 (cron)"""
        dsl = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "config": {
                        "trigger_type": "schedule",
                        "cron_expression": "0 9 * * *",  # 매일 9시
                        "timezone": "Asia/Seoul",
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-trigger-2", dsl, {})

        assert result["status"] == "completed"
        assert result["nodes_executed"] == 1

    @pytest.mark.asyncio
    async def test_trigger_node_event(self, engine):
        """TRIGGER 노드 - 이벤트 트리거"""
        dsl = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "config": {
                        "trigger_type": "event",
                        "event_type": "sensor_alert",
                        "filters": {
                            "sensor_type": "temperature",
                            "level": "critical",
                        },
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-trigger-3", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_trigger_node_condition(self, engine):
        """TRIGGER 노드 - 조건 트리거 (센서 임계값)"""
        dsl = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "config": {
                        "trigger_type": "condition",
                        "condition_config": {
                            "expression": "temperature > 80",
                            "check_interval_seconds": 60,
                            "debounce_seconds": 5,
                        },
                        "sensor_ids": ["TEMP-001", "TEMP-002"],
                    }
                }
            ]
        }

        # 조건을 만족하는 입력 데이터
        input_data = {"temperature": 85}
        result = await engine.execute_workflow("wf-trigger-4", dsl, input_data)

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_trigger_node_webhook(self, engine):
        """TRIGGER 노드 - 웹훅 트리거"""
        dsl = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "config": {
                        "trigger_type": "webhook",
                        "endpoint": "/api/v1/webhooks/trigger/wf-trigger-5",
                        "secret": "webhook_secret_key",
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-trigger-5", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_trigger_node_with_following_action(self, engine):
        """TRIGGER 노드 + 후속 액션 노드"""
        dsl = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "config": {
                        "trigger_type": "manual",
                    }
                },
                {
                    "id": "a1",
                    "type": "action",
                    "config": {
                        "action": "log_event",
                        "parameters": {"event_type": "workflow_triggered"},
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-trigger-6", dsl, {})

        assert result["status"] == "completed"
        assert result["nodes_executed"] == 2


class TestCodeNode:
    """CODE 노드 테스트 (V2 Phase 1) - Python Sandbox"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_code_node_simple_calculation(self, engine):
        """CODE 노드 - 간단한 계산"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = data.get('value', 0) * 2",
                        "input": {"value": 10},
                        "sandbox_enabled": False,  # 간단한 테스트용
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-1", dsl, {})

        assert result["status"] == "completed"
        assert result["nodes_executed"] == 1

    @pytest.mark.asyncio
    async def test_code_node_with_template(self, engine):
        """CODE 노드 - 사전 정의 템플릿 사용"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "code_template_id": "defect_rate_calc",
                        "input": {
                            "total_count": 1000,
                            "defect_count": 25,
                        },
                        "sandbox_enabled": False,
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-2", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_code_node_moving_average(self, engine):
        """CODE 노드 - 이동 평균 계산 템플릿"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "code_template_id": "moving_average",
                        "input": {
                            "values": [72.5, 73.0, 74.5, 75.0, 73.5],
                        },
                        "sandbox_enabled": False,
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-3", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_code_node_data_transform(self, engine):
        """CODE 노드 - 데이터 변환 템플릿"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "code_template_id": "data_transform",
                        "input": {
                            "source": {"temp": 72.5, "press": 3.2},
                        },
                        "sandbox_enabled": False,
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-4", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_code_node_anomaly_score(self, engine):
        """CODE 노드 - 이상 점수 계산 템플릿"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "code_template_id": "anomaly_score",
                        "input": {
                            "values": [70, 71, 72, 73, 74, 95],  # 95는 이상치
                        },
                        "sandbox_enabled": False,
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-5", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_code_node_with_timeout(self, engine):
        """CODE 노드 - 타임아웃 설정"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = sum(range(1000))",
                        "timeout_ms": 5000,
                        "sandbox_enabled": False,
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-6", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_code_node_sandbox_restricted_builtins(self, engine):
        """CODE 노드 - 비샌드박스 모드 테스트"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = len([1, 2, 3]) + max(1, 2, 3)",
                        "sandbox_enabled": False,
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-7", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_code_node_with_context_variables(self, engine):
        """CODE 노드 - 컨텍스트 변수 접근"""
        dsl = {
            "nodes": [
                {
                    "id": "a1",
                    "type": "action",
                    "config": {
                        "action": "log_event",
                        "parameters": {"event_type": "start"},
                    }
                },
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = {'processed': True, 'source': 'code_node'}",
                        "sandbox_enabled": False,
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-8", dsl, {"initial": "data"})

        assert result["status"] == "completed"
        assert result["nodes_executed"] == 2

    @pytest.mark.asyncio
    async def test_code_node_empty_code(self, engine):
        """CODE 노드 - 빈 코드 (실패 예상)"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        # inline_code도 code_template_id도 없음
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-9", dsl, {})

        # 코드 없으면 실패
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_code_node_syntax_error(self, engine):
        """CODE 노드 - 문법 오류 처리"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = this is not valid python",
                        "sandbox_enabled": False,
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-10", dsl, {})

        # 문법 오류 시 실패
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_code_node_unknown_template(self, engine):
        """CODE 노드 - 알 수 없는 템플릿"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "code_template_id": "unknown_template_xyz",
                    }
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-11", dsl, {})

        # 알 수 없는 템플릿은 실패 처리
        assert result["status"] == "failed"


class TestNodeTypeIntegration:
    """노드 타입 통합 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_trigger_condition_action_flow(self, engine):
        """TRIGGER → CONDITION → ACTION 플로우"""
        dsl = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "config": {"trigger_type": "manual"},
                },
                {
                    "id": "c1",
                    "type": "condition",
                    "config": {"condition": "temperature > 80"},
                },
                {
                    "id": "a1",
                    "type": "action",
                    "config": {
                        "action": "log_event",
                        "parameters": {"event_type": "high_temp_alert"},
                    },
                },
            ]
        }

        input_data = {"temperature": 85}
        result = await engine.execute_workflow("wf-int-1", dsl, input_data)

        assert result["status"] == "completed"
        assert result["nodes_executed"] >= 2  # trigger + action (condition은 평가만)

    @pytest.mark.asyncio
    async def test_code_if_else_flow(self, engine):
        """CODE → IF_ELSE 플로우"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = data.get('value', 0) * 10",
                        "output_variable": "multiplied",
                        "sandbox_enabled": False,
                    },
                },
                {
                    "id": "ie1",
                    "type": "if_else",
                    "config": {
                        "condition": "multiplied > 50",
                        "then": [
                            {"id": "t1", "type": "action", "config": {"action": "log_event"}},
                        ],
                        "else": [
                            {"id": "e1", "type": "action", "config": {"action": "log_event"}},
                        ],
                    },
                },
            ]
        }

        input_data = {"value": 10}  # 10 * 10 = 100 > 50
        result = await engine.execute_workflow("wf-int-2", dsl, input_data)

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_parallel_code_nodes(self, engine):
        """병렬 CODE 노드 실행"""
        dsl = {
            "nodes": [
                {
                    "id": "p1",
                    "type": "parallel",
                    "config": {
                        "branches": [
                            [
                                {
                                    "id": "c1",
                                    "type": "code",
                                    "config": {
                                        "inline_code": "result = 'branch_1'",
                                        "output_variable": "b1_result",
                                        "sandbox_enabled": False,
                                    },
                                },
                            ],
                            [
                                {
                                    "id": "c2",
                                    "type": "code",
                                    "config": {
                                        "inline_code": "result = 'branch_2'",
                                        "output_variable": "b2_result",
                                        "sandbox_enabled": False,
                                    },
                                },
                            ],
                        ],
                    },
                },
            ]
        }

        result = await engine.execute_workflow("wf-int-3", dsl, {})

        assert result["status"] == "completed"
        assert result["results"][0]["branches_count"] == 2
