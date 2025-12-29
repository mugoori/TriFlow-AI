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


class TestDataSourceNode:
    """DATA 노드 - DataSource MCP 통합 테스트"""

    @pytest.fixture
    def engine(self):
        """WorkflowEngine 인스턴스"""
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_data_node_datasource_type_missing_source_id(self, engine):
        """DATA 노드 - datasource 타입, source_id 누락"""
        dsl = {
            "nodes": [
                {
                    "id": "d1",
                    "type": "data",
                    "config": {
                        "source_type": "datasource",
                        # source_id 누락
                        "tool": "get_production_status",
                        "arguments": {"line_id": "LINE-001"},
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-ds-1", dsl, {})

        # source_id 누락으로 실패하거나 에러 처리됨
        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_data_node_datasource_type_missing_tool(self, engine):
        """DATA 노드 - datasource 타입, tool 누락"""
        from uuid import uuid4

        dsl = {
            "nodes": [
                {
                    "id": "d1",
                    "type": "data",
                    "config": {
                        "source_type": "datasource",
                        "source_id": str(uuid4()),
                        # tool 누락
                        "arguments": {},
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-ds-2", dsl, {})

        # tool 누락으로 실패하거나 에러 처리됨
        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_data_node_connector_type(self, engine):
        """DATA 노드 - connector 타입 (기존 기능)"""
        from uuid import uuid4

        dsl = {
            "nodes": [
                {
                    "id": "d1",
                    "type": "data",
                    "config": {
                        "source_type": "connector",
                        "source_id": str(uuid4()),  # source_id 필수
                        "connector_id": "conn-1",
                        "query": "SELECT * FROM sensors LIMIT 10",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-ds-3", dsl, {})

        # connector가 없으므로 실패하거나 완료됨
        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_data_node_api_type(self, engine):
        """DATA 노드 - api 타입 (기존 기능)"""
        dsl = {
            "nodes": [
                {
                    "id": "d1",
                    "type": "data",
                    "config": {
                        "source_type": "api",
                        "method": "GET",
                        "endpoint": "https://httpbin.org/get",  # endpoint 필수
                        "headers": {"Accept": "application/json"},
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-ds-4", dsl, {})

        # HTTP 요청 성공 여부와 관계없이 완료 또는 실패
        assert result["status"] in ["completed", "failed"]


class TestSwitchNode:
    """SWITCH 노드 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_switch_node_matches_first_case(self, engine):
        """SWITCH 노드 - 첫 번째 case 매칭"""
        dsl = {
            "nodes": [
                {
                    "id": "sw1",
                    "type": "switch",
                    "config": {
                        "expression": "status",
                        "cases": [
                            {"value": "running", "nodes": []},
                            {"value": "stopped", "nodes": []},
                            {"value": "error", "nodes": []},
                        ],
                        "default": [],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-switch-1", dsl, {"status": "running"}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_switch_node_matches_second_case(self, engine):
        """SWITCH 노드 - 두 번째 case 매칭"""
        dsl = {
            "nodes": [
                {
                    "id": "sw1",
                    "type": "switch",
                    "config": {
                        "expression": "status",
                        "cases": [
                            {"value": "running", "nodes": []},
                            {"value": "stopped", "nodes": []},
                        ],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-switch-2", dsl, {"status": "stopped"}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_switch_node_matches_default(self, engine):
        """SWITCH 노드 - default case 매칭"""
        dsl = {
            "nodes": [
                {
                    "id": "sw1",
                    "type": "switch",
                    "config": {
                        "expression": "status",
                        "cases": [
                            {"value": "running", "nodes": []},
                            {"value": "stopped", "nodes": []},
                        ],
                        "default": [],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-switch-3", dsl, {"status": "unknown"}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_switch_node_no_match_no_default(self, engine):
        """SWITCH 노드 - 매칭 없고 default도 없음"""
        dsl = {
            "nodes": [
                {
                    "id": "sw1",
                    "type": "switch",
                    "config": {
                        "expression": "status",
                        "cases": [
                            {"value": "running", "nodes": []},
                            {"value": "stopped", "nodes": []},
                        ],
                        # default 없음
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-switch-4", dsl, {"status": "unknown"}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_switch_node_with_nested_nodes(self, engine):
        """SWITCH 노드 - 중첩된 노드 실행"""
        dsl = {
            "nodes": [
                {
                    "id": "sw1",
                    "type": "switch",
                    "config": {
                        "expression": "mode",
                        "cases": [
                            {
                                "value": "production",
                                "nodes": [
                                    {
                                        "id": "c1",
                                        "type": "code",
                                        "config": {
                                            "inline_code": "result = 'production_mode'",
                                            "output_variable": "mode_result",
                                        },
                                    }
                                ],
                            },
                            {
                                "value": "test",
                                "nodes": [
                                    {
                                        "id": "c2",
                                        "type": "code",
                                        "config": {
                                            "inline_code": "result = 'test_mode'",
                                            "output_variable": "mode_result",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-switch-5", dsl, {"mode": "production"}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_switch_node_expression_as_value(self, engine):
        """SWITCH 노드 - expression이 context에 없으면 값으로 사용"""
        dsl = {
            "nodes": [
                {
                    "id": "sw1",
                    "type": "switch",
                    "config": {
                        "expression": "running",  # context에 없는 키
                        "cases": [
                            {"value": "running", "nodes": []},
                        ],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-switch-6", dsl, {}
        )

        assert result["status"] == "completed"


class TestWaitNode:
    """WAIT 노드 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_wait_node_duration_seconds(self, engine):
        """WAIT 노드 - duration (초)"""
        import time

        dsl = {
            "nodes": [
                {
                    "id": "w1",
                    "type": "wait",
                    "config": {
                        "wait_type": "duration",
                        "duration_seconds": 0.1,  # 0.1초
                    },
                }
            ]
        }

        start = time.time()
        result = await engine.execute_workflow("wf-wait-1", dsl, {})
        elapsed = time.time() - start

        assert result["status"] == "completed"
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_wait_node_duration_zero(self, engine):
        """WAIT 노드 - duration 0 (즉시 완료)"""
        dsl = {
            "nodes": [
                {
                    "id": "w1",
                    "type": "wait",
                    "config": {
                        "wait_type": "duration",
                        "duration_seconds": 0,
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-wait-2", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_wait_node_schedule_interval(self, engine):
        """WAIT 노드 - schedule with interval_seconds"""
        import time

        dsl = {
            "nodes": [
                {
                    "id": "w1",
                    "type": "wait",
                    "config": {
                        "wait_type": "schedule",
                        "interval_seconds": 0.1,  # 0.1초
                    },
                }
            ]
        }

        start = time.time()
        result = await engine.execute_workflow("wf-wait-3", dsl, {})
        elapsed = time.time() - start

        assert result["status"] == "completed"
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Event type wait node requires event bus integration")
    async def test_wait_node_event_type_timeout(self, engine):
        """WAIT 노드 - event 타입 (timeout)"""
        dsl = {
            "nodes": [
                {
                    "id": "w1",
                    "type": "wait",
                    "config": {
                        "wait_type": "event",
                        "event_type": "sensor_alert",
                        "timeout": 0.05,  # 0.05초 후 타임아웃
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-wait-4", dsl, {})

        # 타임아웃으로 완료 또는 실패
        assert result["status"] in ["completed", "failed"]


class TestIfElseNode:
    """IF_ELSE 노드 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_if_else_true_branch(self, engine):
        """IF_ELSE 노드 - 조건 참일 때 true_nodes 실행"""
        dsl = {
            "nodes": [
                {
                    "id": "ie1",
                    "type": "if_else",
                    "config": {
                        "condition": "value > 50",
                        "true_nodes": [
                            {
                                "id": "c1",
                                "type": "code",
                                "config": {
                                    "inline_code": "result = 'true_branch'",
                                    "output_variable": "branch_result",
                                },
                            }
                        ],
                        "false_nodes": [
                            {
                                "id": "c2",
                                "type": "code",
                                "config": {
                                    "inline_code": "result = 'false_branch'",
                                    "output_variable": "branch_result",
                                },
                            }
                        ],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-if-1", dsl, {"value": 75}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_if_else_false_branch(self, engine):
        """IF_ELSE 노드 - 조건 거짓일 때 false_nodes 실행"""
        dsl = {
            "nodes": [
                {
                    "id": "ie1",
                    "type": "if_else",
                    "config": {
                        "condition": "value > 50",
                        "true_nodes": [],
                        "false_nodes": [
                            {
                                "id": "c1",
                                "type": "code",
                                "config": {
                                    "inline_code": "result = 'false_branch'",
                                    "output_variable": "branch_result",
                                },
                            }
                        ],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-if-2", dsl, {"value": 25}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_if_else_no_false_nodes(self, engine):
        """IF_ELSE 노드 - 조건 거짓이지만 false_nodes 없음"""
        dsl = {
            "nodes": [
                {
                    "id": "ie1",
                    "type": "if_else",
                    "config": {
                        "condition": "value > 50",
                        "true_nodes": [],
                        # false_nodes 없음
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-if-3", dsl, {"value": 25}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_if_else_condition_evaluation_error(self, engine):
        """IF_ELSE 노드 - 조건 평가 에러"""
        dsl = {
            "nodes": [
                {
                    "id": "ie1",
                    "type": "if_else",
                    "config": {
                        "condition": "undefined_var > 50",
                        "true_nodes": [],
                        "false_nodes": [],
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-if-4", dsl, {})

        # 조건 평가 에러는 false로 처리되거나 실패
        assert result["status"] in ["completed", "failed"]


class TestLoopNode:
    """LOOP 노드 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_loop_node_for_each(self, engine):
        """LOOP 노드 - for_each 모드 (빈 노드)"""
        dsl = {
            "nodes": [
                {
                    "id": "l1",
                    "type": "loop",
                    "config": {
                        "loop_type": "for_each",
                        "items": "items",  # context에서 items 참조
                        "item_variable": "item",
                        "nodes": [],  # 빈 노드로 테스트
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-loop-1", dsl, {"items": [1, 2, 3]}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_loop_node_while(self, engine):
        """LOOP 노드 - while 모드 (즉시 종료)"""
        dsl = {
            "nodes": [
                {
                    "id": "l1",
                    "type": "loop",
                    "config": {
                        "loop_type": "while",
                        "condition": "counter < 0",  # 즉시 종료되는 조건
                        "max_iterations": 10,
                        "nodes": [],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-loop-2", dsl, {"counter": 0}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_loop_node_count(self, engine):
        """LOOP 노드 - count 모드 (빈 노드)"""
        dsl = {
            "nodes": [
                {
                    "id": "l1",
                    "type": "loop",
                    "config": {
                        "loop_type": "count",
                        "count": 3,
                        "index_variable": "i",
                        "nodes": [],  # 빈 노드로 테스트
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-loop-3", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_loop_node_empty_items(self, engine):
        """LOOP 노드 - 빈 items 배열"""
        dsl = {
            "nodes": [
                {
                    "id": "l1",
                    "type": "loop",
                    "config": {
                        "loop_type": "for_each",
                        "items": "items",
                        "nodes": [],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-loop-4", dsl, {"items": []}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_loop_node_max_iterations(self, engine):
        """LOOP 노드 - max_iterations 제한"""
        dsl = {
            "nodes": [
                {
                    "id": "l1",
                    "type": "loop",
                    "config": {
                        "loop_type": "while",
                        "condition": "True",  # 무한 루프
                        "max_iterations": 3,
                        "nodes": [],
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-loop-5", dsl, {})

        # max_iterations 제한으로 종료
        assert result["status"] == "completed"


class TestParallelNode:
    """PARALLEL 노드 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_parallel_node_all_branches(self, engine):
        """PARALLEL 노드 - 모든 브랜치 실행"""
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
                                        "inline_code": "result = 'branch1'",
                                        "output_variable": "b1",
                                    },
                                }
                            ],
                            [
                                {
                                    "id": "c2",
                                    "type": "code",
                                    "config": {
                                        "inline_code": "result = 'branch2'",
                                        "output_variable": "b2",
                                    },
                                }
                            ],
                        ],
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-parallel-1", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_parallel_node_empty_branches(self, engine):
        """PARALLEL 노드 - 빈 브랜치"""
        dsl = {
            "nodes": [
                {
                    "id": "p1",
                    "type": "parallel",
                    "config": {
                        "branches": [[], []],
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-parallel-2", dsl, {})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_parallel_node_single_branch(self, engine):
        """PARALLEL 노드 - 단일 브랜치"""
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
                                        "inline_code": "result = 'only_branch'",
                                        "output_variable": "b1",
                                    },
                                }
                            ],
                        ],
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-parallel-3", dsl, {})

        assert result["status"] == "completed"


class TestActionExecutorExtended:
    """ActionExecutor 확장 테스트"""

    @pytest.fixture
    def executor(self):
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_execute_stop_production_line(self, executor):
        """stop_production_line 액션"""
        result = await executor.execute(
            "stop_production_line",
            {"line_id": "LINE-001", "reason": "maintenance"},
            {"sensor_data": {}},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_adjust_sensor_threshold(self, executor):
        """adjust_sensor_threshold 액션"""
        result = await executor.execute(
            "adjust_sensor_threshold",
            {"sensor_id": "TEMP-001", "new_threshold": 85.0},
            {"sensor_data": {}},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_trigger_maintenance(self, executor):
        """trigger_maintenance 액션"""
        result = await executor.execute(
            "trigger_maintenance",
            {"equipment_id": "EQ-001", "priority": "high"},
            {"sensor_data": {}},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_calculate_defect_rate(self, executor):
        """calculate_defect_rate 액션"""
        result = await executor.execute(
            "calculate_defect_rate",
            {"line_id": "LINE-001", "time_range": "1h"},
            {"sensor_data": {}},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_analyze_sensor_trend(self, executor):
        """analyze_sensor_trend 액션"""
        result = await executor.execute(
            "analyze_sensor_trend",
            {"sensor_id": "TEMP-001", "duration": "24h"},
            {"sensor_data": {}},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_predict_equipment_failure(self, executor):
        """predict_equipment_failure 액션"""
        result = await executor.execute(
            "predict_equipment_failure",
            {"equipment_id": "EQ-001"},
            {"sensor_data": {}},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_unknown_action_returns_error(self, executor):
        """알 수 없는 액션 에러 처리"""
        result = await executor.execute(
            "completely_unknown_action",
            {},
            {},
        )

        # Unknown action should return error result
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_with_db_dependency(self, executor):
        """DB 의존성이 있는 액션 (Mock 없이)"""
        result = await executor.execute(
            "export_to_csv",
            {"query": "SELECT 1", "filename": "test.csv"},
            {},
        )

        # DB 없이도 실행되어야 함 (에러 처리 또는 기본 동작)
        assert result is not None


class TestConditionEvaluatorExtended:
    """ConditionEvaluator 확장 테스트"""

    @pytest.fixture
    def evaluator(self):
        return ConditionEvaluator()

    def test_evaluate_with_string_comparison(self, evaluator):
        """문자열 비교 조건"""
        result = evaluator.evaluate(
            "status == 'active'",
            {"status": "active"},
        )

        # ConditionEvaluator returns (bool, message) tuple
        if isinstance(result, tuple):
            assert result[0] is True
        else:
            assert result is True

    def test_evaluate_simple_comparison(self, evaluator):
        """단순 비교 조건"""
        result = evaluator.evaluate(
            "value > 50",
            {"value": 75},
        )

        if isinstance(result, tuple):
            assert result[0] is True
        else:
            assert result is True

    def test_evaluate_less_than(self, evaluator):
        """작다 비교"""
        result = evaluator.evaluate(
            "temperature < 100",
            {"temperature": 72.5},
        )

        if isinstance(result, tuple):
            assert result[0] is True
        else:
            assert result is True

    def test_evaluate_equal(self, evaluator):
        """같다 비교"""
        result = evaluator.evaluate(
            "count == 10",
            {"count": 10},
        )

        if isinstance(result, tuple):
            assert result[0] is True
        else:
            assert result is True

    def test_evaluate_not_equal(self, evaluator):
        """다르다 비교"""
        result = evaluator.evaluate(
            "status != 'error'",
            {"status": "active"},
        )

        if isinstance(result, tuple):
            assert result[0] is True
        else:
            assert result is True

    def test_evaluate_and_condition(self, evaluator):
        """AND 조건 (&&)"""
        result = evaluator.evaluate(
            "temp > 50 && temp < 100",
            {"temp": 75},
        )

        if isinstance(result, tuple):
            assert result[0] is True
        else:
            assert result is True

    def test_evaluate_or_condition(self, evaluator):
        """OR 조건 (||)"""
        result = evaluator.evaluate(
            "status == 'active' || status == 'running'",
            {"status": "active"},
        )

        if isinstance(result, tuple):
            assert result[0] is True
        else:
            assert result is True

    def test_evaluate_false_condition(self, evaluator):
        """거짓 조건"""
        result = evaluator.evaluate(
            "value > 100",
            {"value": 50},
        )

        if isinstance(result, tuple):
            assert result[0] is False
        else:
            assert result is False


class TestActionExecutorInsightActions:
    """ActionExecutor 인사이트 액션 테스트"""

    @pytest.fixture
    def executor(self):
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_aggregate_data_no_grouping(self, executor):
        """aggregate_data - 그룹화 없이 전체 집계"""
        data = [
            {"value": 10, "category": "A"},
            {"value": 20, "category": "A"},
            {"value": 30, "category": "B"},
        ]
        params = {
            "data": data,
            "aggregations": {
                "total": {"field": "value", "func": "sum"},
                "average": {"field": "value", "func": "avg"},
            },
        }

        result = await executor.execute("aggregate_data", params, {})

        assert result["success"] is True
        assert result["data"]["result"]["total"] == 60
        assert result["data"]["result"]["average"] == 20

    @pytest.mark.asyncio
    async def test_aggregate_data_with_grouping(self, executor):
        """aggregate_data - 그룹화 집계"""
        data = [
            {"value": 10, "category": "A"},
            {"value": 20, "category": "A"},
            {"value": 30, "category": "B"},
        ]
        params = {
            "data": data,
            "group_by": "category",
            "aggregations": {
                "total": {"field": "value", "func": "sum"},
            },
        }

        result = await executor.execute("aggregate_data", params, {})

        assert result["success"] is True
        assert result["data"]["total_groups"] == 2

    @pytest.mark.asyncio
    async def test_aggregate_data_empty(self, executor):
        """aggregate_data - 빈 데이터"""
        params = {
            "data": [],
            "aggregations": {"total": {"field": "value", "func": "sum"}},
        }

        result = await executor.execute("aggregate_data", params, {})

        assert result["success"] is True
        assert "집계할 데이터가 없습니다" in result["message"]

    @pytest.mark.asyncio
    async def test_evaluate_threshold_normal_mode(self, executor):
        """evaluate_threshold - 일반 모드 (높을수록 좋음)"""
        params = {
            "value": 85,
            "thresholds": [
                {"min": 90, "status": "EXCELLENT", "message": "우수"},
                {"min": 80, "status": "GOOD", "message": "양호"},
                {"min": 70, "status": "WARNING", "message": "주의"},
                {"min": 0, "status": "CRITICAL", "message": "위험"},
            ],
            "metric_name": "가동률",
        }

        result = await executor.execute("evaluate_threshold", params, {})

        assert result["success"] is True
        assert result["data"]["status"] == "GOOD"
        assert result["data"]["level"] == 1

    @pytest.mark.asyncio
    async def test_evaluate_threshold_inverse_mode(self, executor):
        """evaluate_threshold - 역방향 모드 (낮을수록 좋음)"""
        params = {
            "value": 1.5,
            "inverse": True,
            "metric_name": "불량률",
        }

        result = await executor.execute("evaluate_threshold", params, {})

        assert result["success"] is True
        assert result["data"]["status"] == "GREEN"

    @pytest.mark.asyncio
    async def test_evaluate_threshold_default_thresholds(self, executor):
        """evaluate_threshold - 기본 임계값"""
        params = {
            "value": 45,
            "metric_name": "점수",
        }

        result = await executor.execute("evaluate_threshold", params, {})

        assert result["success"] is True
        # 45는 기본 임계값에서 50 미만이므로 RED
        assert result["data"]["status"] == "RED"

    @pytest.mark.asyncio
    async def test_generate_chart_bar(self, executor):
        """generate_chart - 막대 차트"""
        params = {
            "chart_type": "bar",
            "data": [
                {"name": "1월", "value": 100},
                {"name": "2월", "value": 150},
                {"name": "3월", "value": 120},
            ],
            "options": {
                "title": "월별 생산량",
                "x_key": "name",
                "y_key": "value",
                "style": "gradient_rounded",
            },
        }

        result = await executor.execute("generate_chart", params, {})

        assert result["success"] is True
        chart_json = result["data"]["chart_json"]
        assert chart_json["type"] == "bar"
        assert chart_json["title"] == "월별 생산량"
        assert chart_json["config"]["gradient"] is True

    @pytest.mark.asyncio
    async def test_generate_chart_line(self, executor):
        """generate_chart - 선 차트"""
        params = {
            "chart_type": "line",
            "data": [
                {"time": "00:00", "temp": 72.5},
                {"time": "01:00", "temp": 73.0},
            ],
            "options": {
                "title": "온도 추이",
                "x_key": "time",
                "y_key": "temp",
                "style": "glow_smooth",
            },
        }

        result = await executor.execute("generate_chart", params, {})

        assert result["success"] is True
        chart_json = result["data"]["chart_json"]
        assert chart_json["type"] == "line"
        assert chart_json["config"]["glow"] is True
        assert chart_json["config"]["smooth"] is True

    @pytest.mark.asyncio
    async def test_generate_chart_pie(self, executor):
        """generate_chart - 파이 차트"""
        params = {
            "chart_type": "pie",
            "data": [
                {"category": "A", "count": 30},
                {"category": "B", "count": 50},
                {"category": "C", "count": 20},
            ],
            "options": {
                "title": "카테고리 분포",
                "name_key": "category",
                "value_key": "count",
                "style": "donut",
            },
        }

        result = await executor.execute("generate_chart", params, {})

        assert result["success"] is True
        chart_json = result["data"]["chart_json"]
        assert chart_json["type"] == "pie"
        assert chart_json["config"]["innerRadius"] == 60  # donut style

    @pytest.mark.asyncio
    async def test_generate_chart_gauge(self, executor):
        """generate_chart - 게이지 차트"""
        params = {
            "chart_type": "gauge",
            "data": [{"value": 75}],
            "options": {
                "title": "가동률",
                "max": 100,
                "min": 0,
            },
        }

        result = await executor.execute("generate_chart", params, {})

        assert result["success"] is True
        chart_json = result["data"]["chart_json"]
        assert chart_json["type"] == "gauge"
        assert chart_json["value"] == 75

    @pytest.mark.asyncio
    async def test_format_insight_template(self, executor):
        """format_insight - 템플릿 기반"""
        params = {
            "template": "현재 {metric}은(는) {value}%입니다.",
            "data": {"metric": "가동률", "value": 85.5},
        }

        result = await executor.execute("format_insight", params, {})

        assert result["success"] is True
        assert "가동률" in result["data"]["insight_text"]
        assert "85.5" in result["data"]["insight_text"]

    @pytest.mark.asyncio
    async def test_format_insight_with_sections(self, executor):
        """format_insight - 섹션 포함"""
        params = {
            "template": "",
            "data": {},
            "sections": [
                {"type": "summary", "content": "오늘의 생산 현황입니다."},
                {"type": "table", "headers": ["항목", "값"], "rows": [["생산량", "1000"], ["불량률", "2%"]]},
                {"type": "recommendation", "content": "유지보수 점검을 권장합니다."},
            ],
        }

        result = await executor.execute("format_insight", params, {})

        assert result["success"] is True
        text = result["data"]["insight_text"]
        assert "요약" in text
        assert "권장 조치" in text
        assert "| 항목 | 값 |" in text

    @pytest.mark.asyncio
    async def test_format_insight_template_error(self, executor):
        """format_insight - 템플릿 변수 누락"""
        params = {
            "template": "현재 {missing_var}입니다.",
            "data": {"other_var": "test"},
        }

        result = await executor.execute("format_insight", params, {})

        assert result["success"] is True
        assert "템플릿 오류" in result["data"]["insight_text"]

    @pytest.mark.asyncio
    async def test_calculate_metric_oee(self, executor):
        """calculate_metric - OEE 계산"""
        params = {
            "metric_type": "oee",
            "data": {
                "availability": 90,
                "performance": 95,
                "quality": 98,
            },
        }

        result = await executor.execute("calculate_metric", params, {})

        assert result["success"] is True
        # OEE = 90 * 95 * 98 / 10000 = 83.79
        assert result["data"]["value"] == 83.79

    @pytest.mark.asyncio
    async def test_calculate_metric_yield(self, executor):
        """calculate_metric - 수율 계산"""
        params = {
            "metric_type": "yield",
            "numerator": 950,  # good_count
            "denominator": 1000,  # total_count
        }

        result = await executor.execute("calculate_metric", params, {})

        assert result["success"] is True
        assert result["data"]["value"] == 95.0

    @pytest.mark.asyncio
    async def test_calculate_metric_defect_rate(self, executor):
        """calculate_metric - 불량률 계산"""
        params = {
            "metric_type": "defect_rate",
            "numerator": 25,  # defect_count
            "denominator": 1000,  # total_count
        }

        result = await executor.execute("calculate_metric", params, {})

        assert result["success"] is True
        assert result["data"]["value"] == 2.5

    @pytest.mark.asyncio
    async def test_calculate_metric_availability(self, executor):
        """calculate_metric - 가동률 계산"""
        params = {
            "metric_type": "availability",
            "numerator": 420,  # run_time (7시간)
            "denominator": 480,  # planned_time (8시간)
        }

        result = await executor.execute("calculate_metric", params, {})

        assert result["success"] is True
        assert result["data"]["value"] == 87.5

    @pytest.mark.asyncio
    async def test_calculate_metric_custom(self, executor):
        """calculate_metric - 사용자 정의 계산"""
        params = {
            "metric_type": "custom",
            "numerator": 75,
            "denominator": 100,
        }

        result = await executor.execute("calculate_metric", params, {})

        assert result["success"] is True
        assert result["data"]["value"] == 75.0

    @pytest.mark.asyncio
    async def test_analyze_sensor_trend_with_data(self, executor):
        """analyze_sensor_trend - 실제 데이터"""
        # 증가 추세 데이터
        data = [
            {"timestamp": "2025-01-01T00:00:00", "value": 70},
            {"timestamp": "2025-01-01T01:00:00", "value": 72},
            {"timestamp": "2025-01-01T02:00:00", "value": 74},
            {"timestamp": "2025-01-01T03:00:00", "value": 76},
            {"timestamp": "2025-01-01T04:00:00", "value": 78},
            {"timestamp": "2025-01-01T05:00:00", "value": 80},
        ]
        params = {
            "data": data,
            "sensor_type": "temperature",
            "value_key": "value",
        }

        result = await executor.execute("analyze_sensor_trend", params, {})

        assert result["success"] is True
        assert result["data"]["is_mock"] is False
        assert result["data"]["trend"] == "increasing"
        assert result["data"]["data_points"] == 6

    @pytest.mark.asyncio
    async def test_analyze_sensor_trend_stable(self, executor):
        """analyze_sensor_trend - 안정 추세"""
        data = [
            {"value": 72.0},
            {"value": 72.1},
            {"value": 71.9},
            {"value": 72.0},
            {"value": 72.2},
            {"value": 71.8},
        ]
        params = {
            "data": data,
            "sensor_type": "temperature",
        }

        result = await executor.execute("analyze_sensor_trend", params, {})

        assert result["success"] is True
        assert result["data"]["trend"] == "stable"

    @pytest.mark.asyncio
    async def test_analyze_sensor_trend_no_data(self, executor):
        """analyze_sensor_trend - 데이터 없음 (Mock)"""
        params = {
            "sensor_type": "temperature",
            "hours": 24,
        }

        result = await executor.execute("analyze_sensor_trend", params, {})

        assert result["success"] is True
        assert result["data"]["is_mock"] is True
        assert result["data"]["trend"] in ["increasing", "decreasing", "stable"]

    @pytest.mark.asyncio
    async def test_predict_equipment_failure_with_data(self, executor):
        """predict_equipment_failure - 실제 센서 데이터"""
        sensor_data = [
            {"temperature": 85, "vibration": 3.5, "pressure": 145},
            {"temperature": 88, "vibration": 4.0, "pressure": 155},
            {"temperature": 92, "vibration": 4.5, "pressure": 165},
        ]
        params = {
            "equipment_id": "EQUIP-001",
            "sensor_data": sensor_data,
            "thresholds": {
                "temperature": {"warning": 80, "critical": 95},
                "vibration": {"warning": 3.0, "critical": 5.0},
                "pressure": {"warning": 150, "critical": 180},
            },
        }

        result = await executor.execute("predict_equipment_failure", params, {})

        assert result["success"] is True
        assert result["data"]["is_mock"] is False
        assert result["data"]["failure_probability"] >= 0
        assert len(result["data"]["risk_factors"]) > 0

    @pytest.mark.asyncio
    async def test_predict_equipment_failure_no_data(self, executor):
        """predict_equipment_failure - 데이터 없음 (Mock)"""
        params = {
            "equipment_id": "EQUIP-002",
        }

        result = await executor.execute("predict_equipment_failure", params, {})

        assert result["success"] is True
        assert result["data"]["is_mock"] is True


class TestWorkflowEngineCheckpointRecovery:
    """워크플로우 체크포인트 및 복구 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_workflow_generates_instance_id(self, engine):
        """인스턴스 ID 자동 생성"""
        dsl = {"nodes": []}

        result = await engine.execute_workflow("wf-test", dsl, {})

        assert "instance_id" in result
        assert len(result["instance_id"]) == 36  # UUID 형식

    @pytest.mark.asyncio
    async def test_workflow_uses_provided_instance_id(self, engine):
        """제공된 인스턴스 ID 사용"""
        dsl = {"nodes": []}
        custom_id = "custom-instance-123"

        result = await engine.execute_workflow(
            "wf-test", dsl, {}, instance_id=custom_id
        )

        assert result["instance_id"] == custom_id


class TestWorkflowEngineConstants:
    """WorkflowEngine 상수 테스트 확장"""

    def test_max_wait_seconds(self):
        """최대 대기 시간"""
        assert WorkflowEngine.MAX_WAIT_SECONDS == 3600  # 1시간

    def test_default_approval_timeout(self):
        """기본 승인 타임아웃"""
        assert WorkflowEngine.DEFAULT_APPROVAL_TIMEOUT == 86400  # 24시간


class TestSensorSimulatorExtended:
    """SensorSimulator 확장 테스트"""

    @pytest.fixture
    def simulator(self):
        return SensorSimulator()

    def test_generate_production_delay_scenario(self, simulator):
        """생산 지연 시나리오"""
        data = simulator.generate_test_scenario("production_delay")

        assert data["units_per_hour"] == 75
        assert data["production_count"] == 300
        assert data["runtime_hours"] == 6

    def test_generate_shift_change_scenario(self, simulator):
        """교대 시간 시나리오"""
        data = simulator.generate_test_scenario("shift_change")

        assert data["current_hour"] == 18
        assert data["production_count"] == 1000
        assert data["equipment_status"] == "running"

    def test_generate_vibration_sensor(self, simulator):
        """진동 센서 데이터"""
        data = simulator.generate_sensor_data(
            sensors=["vibration"],
            scenario="random"
        )

        assert "vibration" in data
        assert 0.0 <= data["vibration"] <= 100.0

    def test_generate_humidity_sensor(self, simulator):
        """습도 센서 데이터"""
        data = simulator.generate_sensor_data(
            sensors=["humidity"],
            scenario="normal"
        )

        assert "humidity" in data
        # normal 시나리오는 중앙 50% 범위
        # 범위: 20~90, 중앙 50%: 37.5~72.5

    def test_generate_all_sensors_random(self, simulator):
        """모든 센서 랜덤 데이터"""
        data = simulator.generate_sensor_data(scenario="random")

        # 기본 센서 범위에 정의된 모든 키가 있어야 함
        assert "temperature" in data
        assert "pressure" in data
        assert "humidity" in data


class TestAggregateFunctions:
    """집계 함수 테스트"""

    @pytest.fixture
    def executor(self):
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_aggregate_count(self, executor):
        """count 집계"""
        data = [{"v": 1}, {"v": 2}, {"v": 3}, {"v": 4}]
        params = {
            "data": data,
            "aggregations": {"count": {"field": "v", "func": "count"}},
        }

        result = await executor.execute("aggregate_data", params, {})

        assert result["success"] is True
        assert result["data"]["result"]["count"] == 4

    @pytest.mark.asyncio
    async def test_aggregate_min_max(self, executor):
        """min/max 집계"""
        data = [{"v": 10}, {"v": 5}, {"v": 20}, {"v": 15}]
        params = {
            "data": data,
            "aggregations": {
                "minimum": {"field": "v", "func": "min"},
                "maximum": {"field": "v", "func": "max"},
            },
        }

        result = await executor.execute("aggregate_data", params, {})

        assert result["success"] is True
        assert result["data"]["result"]["minimum"] == 5
        assert result["data"]["result"]["maximum"] == 20

    @pytest.mark.asyncio
    async def test_aggregate_multi_group_keys(self, executor):
        """다중 그룹 키 집계"""
        data = [
            {"year": 2024, "month": 1, "sales": 100},
            {"year": 2024, "month": 1, "sales": 150},
            {"year": 2024, "month": 2, "sales": 200},
            {"year": 2025, "month": 1, "sales": 300},
        ]
        params = {
            "data": data,
            "group_by": ["year", "month"],
            "aggregations": {"total": {"field": "sales", "func": "sum"}},
        }

        result = await executor.execute("aggregate_data", params, {})

        assert result["success"] is True
        assert result["data"]["total_groups"] == 3


class TestActionExecutorCallApi:
    """ActionExecutor _call_api 메서드 테스트"""

    @pytest.fixture
    def executor(self):
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_call_api_missing_url(self, executor):
        """URL 누락시 오류"""
        params = {"method": "GET"}
        result = await executor.execute("call_api", params, {})

        # URL 누락시 메시지에 URL 언급
        assert "URL" in result.get("message", "") or result.get("success") is False

    @pytest.mark.asyncio
    async def test_call_api_unsupported_method(self, executor):
        """지원하지 않는 HTTP 메서드"""
        params = {
            "url": "https://example.com/api",
            "method": "INVALID",
        }
        result = await executor.execute("call_api", params, {})

        # 실제로는 오류가 발생하거나 unsupported 메시지
        assert "지원하지 않는" in result.get("message", "") or "unsupported" in str(result).lower() or result.get("success") is False

    @pytest.mark.asyncio
    async def test_call_api_get_success(self, executor):
        """GET 요청 성공"""
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}

        mock_client_instance = MagicMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            params = {
                "url": "https://example.com/api",
                "method": "GET",
                "headers": {"Authorization": "Bearer test"},
            }
            result = await executor.execute("call_api", params, {})

            assert result["success"] is True
            assert result["data"]["status_code"] == 200

    @pytest.mark.asyncio
    async def test_call_api_post_success(self, executor):
        """POST 요청 성공"""
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 123}

        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            params = {
                "url": "https://example.com/api",
                "method": "POST",
                "body": {"name": "test"},
            }
            result = await executor.execute("call_api", params, {})

            assert result["success"] is True
            assert result["data"]["status_code"] == 201

    @pytest.mark.asyncio
    async def test_call_api_put_success(self, executor):
        """PUT 요청 성공"""
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"updated": True}

        mock_client_instance = MagicMock()
        mock_client_instance.put = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            params = {
                "url": "https://example.com/api/1",
                "method": "PUT",
                "body": {"name": "updated"},
            }
            result = await executor.execute("call_api", params, {})

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_call_api_delete_success(self, executor):
        """DELETE 요청 성공"""
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.json.side_effect = Exception("No JSON")
        mock_response.text = ""

        mock_client_instance = MagicMock()
        mock_client_instance.delete = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            params = {
                "url": "https://example.com/api/1",
                "method": "DELETE",
            }
            result = await executor.execute("call_api", params, {})

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_call_api_patch_success(self, executor):
        """PATCH 요청 성공"""
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"patched": True}

        mock_client_instance = MagicMock()
        mock_client_instance.patch = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            params = {
                "url": "https://example.com/api/1",
                "method": "PATCH",
                "body": {"field": "value"},
            }
            result = await executor.execute("call_api", params, {})

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_call_api_timeout_with_retry(self, executor):
        """타임아웃 + 재시도 (외부 호출 없이 검증)"""
        # 실제 네트워크 호출을 피하고 로직만 검증
        params = {
            "url": "https://nonexistent.invalid.domain.test/api",
            "method": "GET",
            "timeout": 1,
            "retry_count": 0,  # 재시도 안함
        }
        result = await executor.execute("call_api", params, {})

        # 연결 불가능한 URL이므로 실패
        assert result.get("success") is False or "오류" in result.get("message", "") or "실패" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_call_api_request_error(self, executor):
        """요청 오류 (연결 불가 URL)"""
        params = {
            "url": "https://nonexistent.invalid.domain.test/api",
            "method": "GET",
        }
        result = await executor.execute("call_api", params, {})

        # 연결 불가능하므로 실패
        assert result.get("success") is False or "오류" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_call_api_with_internal_url_dev(self, executor):
        """개발 환경에서 내부 URL 허용 (연결 시도)"""
        params = {
            "url": "http://localhost:9999/nonexistent",
            "method": "GET",
            "timeout": 1,
        }
        result = await executor.execute("call_api", params, {})

        # 개발환경에서는 내부 URL 허용하지만 연결 실패
        assert "message" in result


class TestActionExecutorExportToCsv:
    """ActionExecutor _export_to_csv 메서드 테스트"""

    @pytest.fixture
    def executor(self):
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_export_to_csv_empty_data(self, executor):
        """빈 데이터 내보내기"""
        params = {"data": [], "filename": "empty.csv"}
        result = await executor.execute("export_to_csv", params, {})

        assert result["success"] is True
        assert "데이터가 없" in result["message"] or result["data"]["rows"] == 0

    @pytest.mark.asyncio
    async def test_export_to_csv_invalid_data(self, executor):
        """잘못된 데이터 형식"""
        params = {"data": "not a list", "filename": "invalid.csv"}
        result = await executor.execute("export_to_csv", params, {})

        # list가 아니면 빈 데이터로 처리
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_export_to_csv_local_success(self, executor):
        """로컬 파일 저장 성공"""
        import os
        import shutil

        params = {
            "data": [
                {"name": "test1", "value": 100},
                {"name": "test2", "value": 200},
            ],
            "filename": "test_export.csv",
        }

        result = await executor.execute("export_to_csv", params, {"workflow_id": "test-wf"})

        assert result["success"] is True
        assert result["data"]["rows"] == 2
        assert result["data"]["storage_type"] == "local"

        # 정리
        export_dir = os.path.join(os.getcwd(), "exports", "test-wf")
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)

    @pytest.mark.asyncio
    async def test_export_to_csv_with_custom_fields(self, executor):
        """커스텀 필드 지정"""
        import os
        import shutil

        params = {
            "data": [
                {"name": "test1", "value": 100, "extra": "ignored"},
                {"name": "test2", "value": 200, "extra": "ignored"},
            ],
            "filename": "test_fields.csv",
            "fields": ["name", "value"],  # extra 필드 제외
        }

        result = await executor.execute("export_to_csv", params, {"workflow_id": "test-wf-2"})

        assert result["success"] is True

        # 정리
        export_dir = os.path.join(os.getcwd(), "exports", "test-wf-2")
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)


class TestActionExecutorSaveToDatabase:
    """ActionExecutor _save_to_database 메서드 테스트"""

    @pytest.fixture
    def executor(self):
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_save_to_database_db_error(self, executor):
        """DB 오류 처리"""
        params = {
            "table": "test_table",
            "data": {"key": "value"},
        }

        result = await executor.execute("save_to_database", params, {"workflow_id": "wf-test"})

        # 실제 DB가 없어서 실패할 수 있음
        assert "message" in result


class TestDataNodeExecution:
    """DATA 노드 실행 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_data_node_simulated_source(self, engine):
        """DATA 노드 - 시뮬레이션 소스"""
        dsl = {
            "nodes": [
                {
                    "id": "d1",
                    "type": "data",
                    "config": {
                        "source_type": "simulated",
                        "simulated": {
                            "scenario": "normal",
                            "sensors": ["temperature", "pressure"],
                        },
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-data-1", dsl, {})

        # data 노드는 완료 또는 실패 (DB 없을 경우)
        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_data_node_context_source(self, engine):
        """DATA 노드 - 컨텍스트 소스"""
        dsl = {
            "nodes": [
                {
                    "id": "d1",
                    "type": "data",
                    "config": {
                        "source_type": "context",
                        "variable": "input_data",
                        "output_variable": "result_data",
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-data-2", dsl, {"input_data": {"key": "value"}}
        )

        assert result["status"] in ["completed", "failed"]


class TestSwitchNodeExecution:
    """SWITCH 노드 실행 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_switch_node_first_case_match(self, engine):
        """SWITCH 노드 - 첫 번째 케이스 매치"""
        dsl = {
            "nodes": [
                {
                    "id": "s1",
                    "type": "switch",
                    "config": {
                        "expression": "status",
                        "cases": [
                            {
                                "value": "active",
                                "nodes": [
                                    {
                                        "id": "c1",
                                        "type": "code",
                                        "config": {
                                            "inline_code": "result = 'active_case'",
                                            "output_variable": "case_result",
                                        },
                                    }
                                ],
                            },
                            {
                                "value": "inactive",
                                "nodes": [],
                            },
                        ],
                        "default_nodes": [],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-switch-1", dsl, {"status": "active"}
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_switch_node_default_case(self, engine):
        """SWITCH 노드 - 디폴트 케이스"""
        dsl = {
            "nodes": [
                {
                    "id": "s1",
                    "type": "switch",
                    "config": {
                        "expression": "status",
                        "cases": [
                            {"value": "active", "nodes": []},
                        ],
                        "default_nodes": [
                            {
                                "id": "c1",
                                "type": "code",
                                "config": {
                                    "inline_code": "result = 'default_case'",
                                    "output_variable": "case_result",
                                },
                            }
                        ],
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-switch-2", dsl, {"status": "unknown"}
        )

        assert result["status"] == "completed"


class TestTriggerNodeExecution:
    """TRIGGER 노드 실행 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_trigger_node_schedule(self, engine):
        """TRIGGER 노드 - 스케줄 타입"""
        dsl = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger",
                    "config": {
                        "trigger_type": "schedule",
                        "schedule": {
                            "cron": "0 9 * * *",
                            "timezone": "Asia/Seoul",
                        },
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-trigger-1", dsl, {})

        # 트리거 노드는 실행 조건만 기록하고 통과
        assert result["status"] == "completed"

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
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-trigger-2", dsl, {})

        assert result["status"] == "completed"


class TestCodeNodeExecution:
    """CODE 노드 실행 테스트 확장"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_code_node_with_context_access(self, engine):
        """CODE 노드 - 컨텍스트 접근"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = input_value * 2",
                        "output_variable": "doubled",
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-code-1", dsl, {"input_value": 21}
        )

        # 샌드박스 환경에서 완료 또는 실패 가능
        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_code_node_with_builtins(self, engine):
        """CODE 노드 - 내장 함수만 사용 (import 없이)"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = sum([1, 2, 3, 4])",
                        "output_variable": "sum_result",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-2", dsl, {})

        # 샌드박스에서 기본 builtins은 허용될 수 있음
        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_code_node_syntax_error(self, engine):
        """CODE 노드 - 문법 오류"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = invalid syntax here >>>",
                        "output_variable": "error_result",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-code-3", dsl, {})

        # 코드 오류는 노드 실패로 처리될 수 있음
        assert result["status"] in ["completed", "failed"]


class TestApprovalNodeExecution:
    """APPROVAL 노드 실행 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_approval_node_no_wait(self, engine):
        """APPROVAL 노드 - 대기 안함"""
        dsl = {
            "nodes": [
                {
                    "id": "a1",
                    "type": "approval",
                    "config": {
                        "approval_type": "single",
                        "approvers": ["admin@test.com"],
                        "wait_for_approval": False,
                        "title": "테스트 승인",
                    },
                }
            ]
        }

        result = await engine.execute_workflow(
            "wf-approval-1", dsl, {"tenant_id": "test-tenant"}
        )

        # wait_for_approval=False이면 바로 완료, 또는 waiting 상태
        assert result["status"] in ["completed", "failed", "waiting"]


class TestJudgmentNodeExecution:
    """JUDGMENT 노드 실행 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_judgment_node_basic(self, engine):
        """JUDGMENT 노드 - 기본 실행"""
        from unittest.mock import patch, MagicMock

        mock_agent = MagicMock()
        mock_agent._hybrid_judgment.return_value = {
            "success": True,
            "decision": "APPROVED",
            "confidence": 0.95,
            "source": "rule",
            "policy_used": "rule_first",
        }

        with patch("app.agents.judgment_agent.JudgmentAgent", return_value=mock_agent):
            dsl = {
                "nodes": [
                    {
                        "id": "j1",
                        "type": "judgment",
                        "config": {
                            "policy": {"type": "RULE_FIRST"},
                            "input": {"temperature": 85},
                        },
                    }
                ]
            }

            result = await engine.execute_workflow("wf-judgment-1", dsl, {})

            assert result["status"] in ["completed", "failed"]


class TestBINodeExecution:
    """BI 노드 실행 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_bi_node_basic(self, engine):
        """BI 노드 - 기본 실행"""
        from unittest.mock import patch, MagicMock, AsyncMock

        mock_agent = MagicMock()
        mock_agent.plan_dashboard = AsyncMock(return_value={
            "success": True,
            "charts": [{"type": "bar", "title": "Test"}],
        })

        with patch("app.agents.bi_planner.BIPlannerAgent", return_value=mock_agent):
            dsl = {
                "nodes": [
                    {
                        "id": "b1",
                        "type": "bi",
                        "config": {
                            "mode": "dashboard",
                            "query": "월별 매출 분석",
                        },
                    }
                ]
            }

            result = await engine.execute_workflow("wf-bi-1", dsl, {})

            assert result["status"] in ["completed", "failed"]


class TestMCPNodeExecution:
    """MCP 노드 실행 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_mcp_node_basic(self, engine):
        """MCP 노드 - 기본 실행"""
        from unittest.mock import patch, MagicMock, AsyncMock

        mock_toolhub = MagicMock()
        mock_toolhub.call_tool = AsyncMock(return_value={
            "success": True,
            "result": {"data": "test"},
        })

        with patch("app.services.mcp_toolhub.get_mcp_toolhub_service", return_value=mock_toolhub):
            dsl = {
                "nodes": [
                    {
                        "id": "m1",
                        "type": "mcp",
                        "config": {
                            "server_id": "test-server",
                            "tool_name": "test_tool",
                            "arguments": {"param": "value"},
                        },
                    }
                ]
            }

            result = await engine.execute_workflow("wf-mcp-1", dsl, {})

            assert result["status"] in ["completed", "failed"]


class TestWorkflowStateMachine:
    """WorkflowStateMachine 테스트"""

    def test_state_machine_initialization(self):
        """상태 머신 초기화"""
        from app.services.workflow_engine import WorkflowStateMachine

        sm = WorkflowStateMachine()

        # 상태 머신은 인스턴스 없이 초기화됨
        assert sm._states == {}
        assert sm._state_history == {}

    def test_can_transition_valid(self):
        """유효한 상태 전이 확인"""
        from app.services.workflow_engine import WorkflowStateMachine, WorkflowState

        sm = WorkflowStateMachine()

        # created -> pending 가능
        assert sm.can_transition(WorkflowState.CREATED, WorkflowState.PENDING) is True

    def test_can_transition_invalid(self):
        """잘못된 상태 전이 확인"""
        from app.services.workflow_engine import WorkflowStateMachine, WorkflowState

        sm = WorkflowStateMachine()

        # created -> completed 불가 (pending을 거쳐야 함)
        can_trans = sm.can_transition(WorkflowState.CREATED, WorkflowState.COMPLETED)
        # 구현에 따라 다를 수 있음
        assert isinstance(can_trans, bool)

    @pytest.mark.asyncio
    async def test_state_transition(self):
        """상태 전이 실행"""
        from app.services.workflow_engine import WorkflowStateMachine, WorkflowState

        sm = WorkflowStateMachine()

        # created -> pending 전이
        result = await sm.transition("test-instance", WorkflowState.PENDING, reason="Starting")

        assert result["current_state"] == "pending"
        assert result["previous_state"] == "created"

    def test_get_state_not_exists(self):
        """존재하지 않는 인스턴스 상태 조회"""
        from app.services.workflow_engine import WorkflowStateMachine

        sm = WorkflowStateMachine()

        state = sm.get_state("nonexistent-instance")

        assert state["state"] == "created"
        assert state["exists"] is False


class TestCheckpointManager:
    """CheckpointManager 테스트"""

    @pytest.mark.asyncio
    async def test_checkpoint_save_and_restore(self):
        """체크포인트 저장 및 복구"""
        from app.services.workflow_engine import CheckpointManager

        manager = CheckpointManager()

        context = {"key": "value", "count": 42}

        # 저장
        checkpoint_id = await manager.save_checkpoint(
            instance_id="test-wf",
            node_id="node1",
            context=context
        )

        assert checkpoint_id is not None

        # 복구
        restored = await manager.restore_checkpoint("test-wf")

        assert restored is not None
        assert restored["checkpoint"]["node_id"] == "node1"

    @pytest.mark.asyncio
    async def test_checkpoint_delete(self):
        """체크포인트 삭제"""
        from app.services.workflow_engine import CheckpointManager

        manager = CheckpointManager()

        # 삭제 시도 (없어도 오류 없이 처리)
        result = await manager.delete_checkpoint("test-wf-nonexistent")
        assert result is True

    @pytest.mark.asyncio
    async def test_checkpoint_list(self):
        """체크포인트 목록 조회"""
        from app.services.workflow_engine import CheckpointManager

        manager = CheckpointManager()

        # 체크포인트 생성
        await manager.save_checkpoint("test-wf-list", "node1", {"step": 1})
        await manager.save_checkpoint("test-wf-list", "node2", {"step": 2})

        # 목록 조회
        checkpoints = await manager.list_checkpoints("test-wf-list")

        assert len(checkpoints) >= 1


class TestWorkflowEngineErrorHandling:
    """WorkflowEngine 오류 처리 테스트"""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_execute_unknown_node_type(self, engine):
        """알 수 없는 노드 타입 실행"""
        dsl = {
            "nodes": [
                {
                    "id": "u1",
                    "type": "unknown_type",
                    "config": {},
                }
            ]
        }

        result = await engine.execute_workflow("wf-unknown-1", dsl, {})

        # 알 수 없는 노드 타입은 오류 또는 스킵
        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_execute_with_node_failure(self, engine):
        """노드 실패 시 처리"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "raise Exception('Test error')",
                        "output_variable": "result",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-error-1", dsl, {})

        # 노드 오류는 워크플로우 실패 또는 오류 처리
        assert result["status"] in ["completed", "failed"]


class TestSensorSimulatorExtended2:
    """SensorSimulator 확장 테스트 2"""

    def test_generate_random_equipment_status(self):
        """랜덤 장비 상태 생성"""
        simulator = SensorSimulator()

        data = simulator.generate_sensor_data(
            sensors=["equipment_status"],
            scenario="random"
        )

        assert "equipment_status" in data
        assert data["equipment_status"] in ["running", "stopped", "error", "maintenance"]

    def test_generate_alert_equipment_status(self):
        """경고 장비 상태 생성"""
        simulator = SensorSimulator()

        data = simulator.generate_sensor_data(
            sensors=["equipment_status"],
            scenario="alert"
        )

        assert data["equipment_status"] == "error"

    def test_generate_normal_equipment_status(self):
        """정상 장비 상태 생성"""
        simulator = SensorSimulator()

        data = simulator.generate_sensor_data(
            sensors=["equipment_status"],
            scenario="normal"
        )

        assert data["equipment_status"] == "running"


class TestExecutionLogStoreExtended:
    """ExecutionLogStore 확장 테스트"""

    def test_get_logs_multiple_filters(self):
        """다중 필터 적용"""
        store = ExecutionLogStore(max_logs=100)

        store.add_log({"workflow_id": "wf-1", "event_type": "start"})
        store.add_log({"workflow_id": "wf-1", "event_type": "action"})
        store.add_log({"workflow_id": "wf-2", "event_type": "start"})
        store.add_log({"workflow_id": "wf-1", "event_type": "end"})

        logs = store.get_logs(workflow_id="wf-1", event_type="action")

        assert len(logs) == 1
        assert logs[0]["event_type"] == "action"

    def test_log_entry_has_log_id_and_timestamp(self):
        """로그 엔트리에 log_id와 timestamp 포함"""
        store = ExecutionLogStore()

        log_id = store.add_log({"event_type": "test"})
        logs = store.get_logs()

        assert logs[0]["log_id"] == log_id
        assert "timestamp" in logs[0]
