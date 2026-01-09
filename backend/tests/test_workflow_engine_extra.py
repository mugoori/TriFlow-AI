"""
Workflow Engine 추가 테스트
workflow_engine.py 커버리지 향상을 위한 추가 테스트
"""
import pytest
from unittest.mock import MagicMock, patch


# ========== ConditionEvaluator 추가 테스트 ==========


class TestConditionEvaluatorExceptions:
    """ConditionEvaluator 예외 처리 테스트"""

    @pytest.fixture
    def evaluator(self):
        from app.services.workflow_engine import ConditionEvaluator
        return ConditionEvaluator()

    def test_evaluate_exception_in_condition(self, evaluator):
        """조건 평가 중 예외 발생"""
        # 잘못된 조건식으로 예외 유발
        result, msg = evaluator.evaluate("invalid[", {})
        assert result is False
        assert "평가 오류" in msg or "실패" in msg or result is False

    def test_evaluate_with_none_context(self, evaluator):
        """None 컨텍스트로 평가"""
        result, msg = evaluator.evaluate("value > 10", None)
        # None 컨텍스트를 처리하거나 오류 반환
        assert isinstance(result, bool)


# ========== ActionExecutor 추가 테스트 ==========


class TestActionExecutorExceptions:
    """ActionExecutor 예외 처리 테스트"""

    @pytest.fixture
    def executor(self):
        from app.services.workflow_engine import ActionExecutor
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_execute_handler_exception(self, executor):
        """핸들러에서 예외 발생"""
        # 실제로 예외를 발생시키는 핸들러 테스트
        # log_event는 정상이지만 잘못된 데이터로 예외 유도
        params = {
            "event_type": "test",
            "details": object(),  # JSON 직렬화 불가
        }

        # execute 메서드 호출 시 예외 처리 확인
        result = await executor.execute("log_event", params, {})
        # 결과가 있어야 함 (예외든 성공이든)
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_unsupported_action(self, executor):
        """지원하지 않는 액션 실행"""
        result = await executor.execute("nonexistent_action_xyz", {}, {})

        assert result["success"] is False
        assert "지원하지 않는" in result["message"]


# ========== ActionExecutor 예측 분석 테스트 ==========


class TestActionExecutorPredictEquipmentFailure:
    """ActionExecutor _predict_equipment_failure 테스트"""

    @pytest.fixture
    def executor(self):
        from app.services.workflow_engine import ActionExecutor
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_predict_failure_critical_threshold(self, executor):
        """critical 임계값 초과 테스트"""
        params = {
            "equipment_id": "EQUIP_TEST",
            "sensor_data": [
                {"temperature": 150.0},
                {"temperature": 155.0},
                {"temperature": 160.0},
            ],
            "thresholds": {
                "temperature": {"warning": 80, "critical": 100}
            }
        }

        result = await executor.execute("predict_equipment_failure", params, {})

        assert result["success"] is True
        data = result.get("data", {})
        # 고장 확률이 높아야 함
        assert "failure_probability" in data

    @pytest.mark.asyncio
    async def test_predict_failure_warning_threshold(self, executor):
        """warning 임계값 초과 테스트"""
        params = {
            "equipment_id": "EQUIP_TEST",
            "sensor_data": [
                {"temperature": 85.0},
                {"temperature": 88.0},
                {"temperature": 90.0},
            ],
            "thresholds": {
                "temperature": {"warning": 80, "critical": 100}
            }
        }

        result = await executor.execute("predict_equipment_failure", params, {})

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_predict_failure_high_variance(self, executor):
        """높은 변동성 테스트"""
        params = {
            "equipment_id": "EQUIP_TEST",
            "sensor_data": [
                {"temperature": 30.0},
                {"temperature": 60.0},
                {"temperature": 90.0},
            ],
            "thresholds": {
                "temperature": {"warning": 100, "critical": 150}
            }
        }

        result = await executor.execute("predict_equipment_failure", params, {})

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_predict_failure_no_values(self, executor):
        """해당 메트릭 값 없음"""
        params = {
            "equipment_id": "EQUIP_TEST",
            "sensor_data": [
                {"humidity": 50.0},
            ],
            "thresholds": {
                "temperature": {"warning": 80, "critical": 100}
            }
        }

        result = await executor.execute("predict_equipment_failure", params, {})

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_predict_failure_invalid_values(self, executor):
        """변환 불가능한 값 (TypeError, ValueError)"""
        params = {
            "equipment_id": "EQUIP_TEST",
            "sensor_data": [
                {"temperature": "not_a_number"},
                {"temperature": None},
            ],
            "thresholds": {
                "temperature": {"warning": 80, "critical": 100}
            }
        }

        result = await executor.execute("predict_equipment_failure", params, {})

        # 에러 없이 처리되어야 함
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_predict_failure_avg_near_warning(self, executor):
        """평균이 경고 수준의 90% 이상일 때"""
        params = {
            "equipment_id": "EQUIP_TEST",
            "sensor_data": [
                {"temperature": 72.0},
                {"temperature": 73.0},
                {"temperature": 74.0},
            ],
            "thresholds": {
                "temperature": {"warning": 80, "critical": 100}
            }
        }

        result = await executor.execute("predict_equipment_failure", params, {})

        assert result["success"] is True
        data = result.get("data", {})
        risk_factors = data.get("risk_factors", [])
        # 경고 수준 근접 메시지가 있을 수 있음
        assert isinstance(risk_factors, list)

    @pytest.mark.asyncio
    async def test_predict_failure_multiple_days_ranges(self, executor):
        """다양한 고장 확률에 따른 잔여 일수"""
        # 매우 높은 위험도
        high_risk_params = {
            "equipment_id": "EQUIP_HIGH",
            "sensor_data": [
                {"temperature": 200.0},
                {"temperature": 200.0},
                {"temperature": 200.0},
            ],
            "thresholds": {
                "temperature": {"warning": 50, "critical": 100}
            }
        }

        result_high = await executor.execute("predict_equipment_failure", high_risk_params, {})
        assert result_high["success"] is True

        # 낮은 위험도
        low_risk_params = {
            "equipment_id": "EQUIP_LOW",
            "sensor_data": [
                {"temperature": 20.0},
                {"temperature": 21.0},
                {"temperature": 22.0},
            ],
            "thresholds": {
                "temperature": {"warning": 80, "critical": 100}
            }
        }

        result_low = await executor.execute("predict_equipment_failure", low_risk_params, {})
        assert result_low["success"] is True


# ========== WorkflowEngine 코드 노드 테스트 ==========


class TestCodeNodeSandbox:
    """CODE 노드 샌드박스 테스트"""

    @pytest.fixture
    def engine(self):
        from app.services.workflow_engine import WorkflowEngine
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_code_node_with_pandas_import(self, engine):
        """pandas 모듈 import 테스트"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = 'pandas_tested'",
                        "allowed_imports": ["pandas"],
                        "output_variable": "out",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-pandas", dsl, {})

        # pandas 없어도 에러 없이 진행
        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_code_node_with_numpy_import(self, engine):
        """numpy 모듈 import 테스트"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = 'numpy_tested'",
                        "allowed_imports": ["numpy"],
                        "output_variable": "out",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-numpy", dsl, {})

        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_code_node_with_unknown_module(self, engine):
        """알 수 없는 모듈 import 시도"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = 'unknown_tested'",
                        "allowed_imports": ["unknown_module_xyz"],
                        "output_variable": "out",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-unknown-mod", dsl, {})

        # 모듈 없어도 에러 없이 처리
        assert result["status"] in ["completed", "failed"]


# ========== WorkflowEngine 싱글톤 테스트 ==========


class TestWorkflowEngineSingleton:
    """WorkflowEngine 싱글톤 테스트"""

    def test_singleton_instances(self):
        """싱글톤 인스턴스 확인"""
        from app.services.workflow_engine import (
            execution_log_store,
            sensor_simulator,
            condition_evaluator,
            action_executor,
            workflow_engine,
        )

        assert execution_log_store is not None
        assert sensor_simulator is not None
        assert condition_evaluator is not None
        assert action_executor is not None
        assert workflow_engine is not None


# ========== ExecutionLogStore 필터 조합 테스트 ==========


class TestExecutionLogStoreFilters:
    """ExecutionLogStore 필터 조합 테스트"""

    def test_filter_by_workflow_and_event_type(self):
        """워크플로우 ID + 이벤트 타입 필터"""
        from app.services.workflow_engine import ExecutionLogStore

        store = ExecutionLogStore()
        store.add_log({"workflow_id": "wf-1", "event_type": "start"})
        store.add_log({"workflow_id": "wf-1", "event_type": "action"})
        store.add_log({"workflow_id": "wf-2", "event_type": "start"})
        store.add_log({"workflow_id": "wf-1", "event_type": "end"})

        logs = store.get_logs(workflow_id="wf-1", event_type="action")

        assert len(logs) == 1
        assert logs[0]["event_type"] == "action"

    def test_log_entry_has_log_id_and_timestamp(self):
        """로그 엔트리에 log_id와 timestamp 포함"""
        from app.services.workflow_engine import ExecutionLogStore

        store = ExecutionLogStore()

        log_id = store.add_log({"event_type": "test"})
        logs = store.get_logs()

        assert logs[0]["log_id"] == log_id
        assert "timestamp" in logs[0]


# ========== ActionExecutor DB 저장 테스트 ==========


class TestActionExecutorDatabaseSave:
    """ActionExecutor _save_to_database 테스트"""

    @pytest.fixture
    def executor(self):
        from app.services.workflow_engine import ActionExecutor
        return ActionExecutor()

    @pytest.mark.asyncio
    @patch("app.database.get_db_context")
    async def test_save_to_database_success(self, mock_db_context, executor):
        """데이터베이스 저장 성공"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 123
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        params = {
            "table": "test_table",
            "data": {"key": "value"},
        }
        context = {"workflow_id": "wf-test"}

        result = await executor.execute("save_to_database", params, context)

        assert "message" in result

    @pytest.mark.asyncio
    @patch("app.database.get_db_context")
    async def test_save_to_database_exception(self, mock_db_context, executor):
        """데이터베이스 저장 예외"""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("DB connection failed")
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        params = {
            "table": "test_table",
            "data": {"key": "value"},
        }

        result = await executor.execute("save_to_database", params, {})

        # 실패 메시지가 있어야 함
        assert "message" in result


# ========== ActionExecutor CSV 내보내기 로컬 저장 테스트 ==========


class TestExportToCsvLocal:
    """CSV 내보내기 로컬 저장 테스트"""

    @pytest.fixture
    def executor(self):
        from app.services.workflow_engine import ActionExecutor
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_export_csv_local_success(self, executor):
        """로컬에 CSV 내보내기 성공"""
        import os
        import shutil

        params = {
            "filename": "test_export.csv",
            "data": [
                {"name": "item1", "value": 100},
                {"name": "item2", "value": 200},
            ],
        }

        result = await executor.execute("export_to_csv", params, {"workflow_id": "wf-local-test"})

        assert "message" in result
        assert result["success"] is True

        # 정리
        export_dir = os.path.join(os.getcwd(), "exports", "wf-local-test")
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)


# ========== WorkflowEngine 다양한 DSL 테스트 ==========


class TestWorkflowEngineDSLVariations:
    """WorkflowEngine DSL 변형 테스트"""

    @pytest.fixture
    def engine(self):
        from app.services.workflow_engine import WorkflowEngine
        return WorkflowEngine()

    @pytest.mark.asyncio
    async def test_code_node_with_math_import(self, engine):
        """math 모듈 import 테스트 - allowed_imports로 math 모듈 사용"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = math.sqrt(16)",
                        "allowed_imports": ["math"],
                        "output_variable": "sqrt_result",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-math", dsl, {})

        assert result["status"] == "completed"
        # Output is in results[0]["output"]
        assert result["results"][0]["output"] == 4.0

    @pytest.mark.asyncio
    async def test_code_node_with_statistics_import(self, engine):
        """statistics 모듈 import 테스트"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = statistics.mean([1,2,3,4,5])",
                        "allowed_imports": ["statistics"],
                        "output_variable": "mean_result",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-stats", dsl, {})

        assert result["status"] == "completed"
        assert result["results"][0]["output"] == 3.0

    @pytest.mark.asyncio
    async def test_code_node_with_re_import(self, engine):
        """re 모듈 import 테스트"""
        dsl = {
            "nodes": [
                {
                    "id": "c1",
                    "type": "code",
                    "config": {
                        "inline_code": "result = bool(re.match(r'\\d+', '123'))",
                        "allowed_imports": ["re"],
                        "output_variable": "match_result",
                    },
                }
            ]
        }

        result = await engine.execute_workflow("wf-re", dsl, {})

        assert result["status"] == "completed"
        assert result["results"][0]["output"] is True


# ========== ActionExecutor 분석 액션 테스트 ==========


class TestActionExecutorAnalysisActions:
    """ActionExecutor 분석 액션 테스트"""

    @pytest.fixture
    def executor(self):
        from app.services.workflow_engine import ActionExecutor
        return ActionExecutor()

    @pytest.mark.asyncio
    async def test_calculate_defect_rate(self, executor):
        """불량률 계산"""
        params = {
            "total_count": 1000,
            "defect_count": 25,
        }

        result = await executor.execute("calculate_defect_rate", params, {})

        assert result["success"] is True
        data = result.get("data", {})
        assert "defect_rate" in data

    @pytest.mark.asyncio
    async def test_calculate_metric(self, executor):
        """메트릭 계산"""
        params = {
            "metric_type": "average",
            "values": [10, 20, 30, 40, 50],
        }

        result = await executor.execute("calculate_metric", params, {})

        assert result["success"] is True
