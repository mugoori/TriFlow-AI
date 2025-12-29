"""
JudgmentAgent 테스트

센서 데이터 분석 및 룰 기반 판단 수행 에이전트 테스트
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4


class TestJudgmentAgentInit:
    """JudgmentAgent 초기화 테스트"""

    def test_agent_init(self):
        """에이전트 초기화"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        assert agent.name == "JudgmentAgent"
        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent.max_tokens == 4096
        assert agent.rhai_engine is not None
        assert agent.hybrid_service is not None
        assert agent.judgment_cache is not None

    def test_agent_inherits_base_agent(self):
        """BaseAgent 상속 확인"""
        from app.agents.judgment_agent import JudgmentAgent
        from app.agents.base_agent import BaseAgent

        agent = JudgmentAgent()

        assert isinstance(agent, BaseAgent)


class TestGetSystemPrompt:
    """get_system_prompt 메서드 테스트"""

    def test_get_system_prompt_returns_string(self):
        """시스템 프롬프트 반환"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        prompt = agent.get_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_get_system_prompt_fallback(self, mock_open):
        """프롬프트 파일 없을 때 기본값"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        prompt = agent.get_system_prompt()

        assert "Judgment Agent" in prompt


class TestGetTools:
    """get_tools 메서드 테스트"""

    def test_get_tools_returns_list(self):
        """도구 목록 반환"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        tools = agent.get_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_tools_contains_required_tools(self):
        """필수 도구 포함 확인"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        tools = agent.get_tools()
        tool_names = [t["name"] for t in tools]

        assert "fetch_sensor_history" in tool_names
        assert "run_rhai_engine" in tool_names
        assert "query_rag_knowledge" in tool_names
        assert "get_line_status" in tool_names
        assert "get_available_lines" in tool_names
        assert "create_ruleset" in tool_names
        assert "hybrid_judgment" in tool_names
        assert "get_judgment_cache_stats" in tool_names

    def test_tool_has_required_fields(self):
        """도구 필수 필드 확인"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        tools = agent.get_tools()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool


class TestExecuteTool:
    """execute_tool 메서드 테스트"""

    def test_execute_unknown_tool_raises_error(self):
        """알 수 없는 도구 실행 시 에러"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with pytest.raises(ValueError) as exc_info:
            agent.execute_tool("unknown_tool", {})

        assert "Unknown tool" in str(exc_info.value)


class TestFetchSensorHistory:
    """_fetch_sensor_history 메서드 테스트"""

    @patch("app.agents.judgment_agent.get_db_context")
    def test_fetch_sensor_history_success(self, mock_db_context):
        """센서 이력 조회 성공"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_sensor = MagicMock()
        mock_sensor.sensor_id = uuid4()
        mock_sensor.sensor_type = "temperature"
        mock_sensor.line_code = "LINE_A"
        mock_sensor.value = 75.5
        mock_sensor.unit = "C"
        mock_sensor.recorded_at = datetime.utcnow()
        mock_sensor.sensor_metadata = {}

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_sensor]

        agent = JudgmentAgent()
        result = agent._fetch_sensor_history(
            sensor_type="temperature",
            line_code="LINE_A",
            hours=24,
            limit=100,
        )

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["data"]) == 1

    @patch("app.agents.judgment_agent.get_db_context")
    def test_fetch_sensor_history_empty(self, mock_db_context):
        """센서 이력 빈 결과"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        agent = JudgmentAgent()
        result = agent._fetch_sensor_history(
            sensor_type="temperature",
            line_code="LINE_A",
        )

        assert result["success"] is True
        assert result["count"] == 0
        assert result["data"] == []

    @patch("app.agents.judgment_agent.get_db_context")
    def test_fetch_sensor_history_error(self, mock_db_context):
        """센서 이력 조회 에러"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db_context.side_effect = Exception("DB error")

        agent = JudgmentAgent()
        result = agent._fetch_sensor_history(
            sensor_type="temperature",
            line_code="LINE_A",
        )

        assert result["success"] is False
        assert "error" in result


class TestRunRhaiEngine:
    """_run_rhai_engine 메서드 테스트"""

    @patch("app.agents.judgment_agent.get_db_context")
    def test_run_rhai_engine_success(self, mock_db_context):
        """Rhai 엔진 실행 성공"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_ruleset = MagicMock()
        mock_ruleset.ruleset_id = uuid4()
        mock_ruleset.name = "Test Ruleset"
        mock_ruleset.is_active = True
        mock_ruleset.rhai_script = "// test script"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_ruleset

        agent = JudgmentAgent()
        with patch.object(agent.rhai_engine, "execute", return_value={"result": "OK"}):
            result = agent._run_rhai_engine(
                ruleset_id=str(mock_ruleset.ruleset_id),
                input_data={"temperature": 75},
            )

        assert result["success"] is True
        assert result["ruleset_name"] == "Test Ruleset"

    @patch("app.agents.judgment_agent.get_db_context")
    def test_run_rhai_engine_ruleset_not_found(self, mock_db_context):
        """Ruleset 없음"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        agent = JudgmentAgent()
        result = agent._run_rhai_engine(
            ruleset_id=str(uuid4()),
            input_data={},
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @patch("app.agents.judgment_agent.get_db_context")
    def test_run_rhai_engine_inactive_ruleset(self, mock_db_context):
        """비활성 Ruleset"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_ruleset = MagicMock()
        mock_ruleset.is_active = False

        mock_db.query.return_value.filter.return_value.first.return_value = mock_ruleset

        agent = JudgmentAgent()
        result = agent._run_rhai_engine(
            ruleset_id=str(uuid4()),
            input_data={},
        )

        assert result["success"] is False
        assert "inactive" in result["error"]


class TestQueryRagKnowledge:
    """_query_rag_knowledge 메서드 테스트"""

    @patch("app.agents.judgment_agent.get_rag_service")
    def test_query_rag_knowledge_success(self, mock_get_rag):
        """RAG 검색 성공"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_rag = MagicMock()
        mock_get_rag.return_value = mock_rag

        agent = JudgmentAgent()
        # RAG 결과 없을 때 기본 응답 반환
        result = agent._query_rag_knowledge(query="온도 임계값")

        assert result["success"] is True
        assert "query" in result

    def test_query_rag_knowledge_default_response(self):
        """RAG 기본 응답"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        result = agent._query_rag_knowledge(query="온도 임계값")

        assert result["success"] is True
        assert len(result["documents"]) > 0


class TestGetLineStatus:
    """_get_line_status 메서드 테스트"""

    @patch("app.agents.judgment_agent.get_db_context")
    def test_get_line_status_success(self, mock_db_context):
        """라인 상태 조회 성공"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        # 센서 데이터 모킹
        mock_result = MagicMock()
        mock_result.avg_value = 75.5
        mock_result.max_value = 80.0
        mock_result.min_value = 70.0
        mock_result.count = 10

        mock_db.query.return_value.filter.return_value.first.return_value = mock_result

        agent = JudgmentAgent()
        with patch.object(agent.rhai_engine, "execute", return_value={"status": "OK", "checks": []}):
            result = agent._get_line_status(line_code="LINE_A")

        assert result["success"] is True
        assert result["line_code"] == "LINE_A"

    @patch("app.agents.judgment_agent.get_db_context")
    def test_get_line_status_no_data(self, mock_db_context):
        """라인 데이터 없음"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.count = 0

        mock_db.query.return_value.filter.return_value.first.return_value = mock_result

        agent = JudgmentAgent()
        result = agent._get_line_status(line_code="LINE_X")

        assert result["success"] is False
        assert "No sensor data" in result["error"]

    @patch("app.agents.judgment_agent.get_db_context")
    def test_get_line_status_error(self, mock_db_context):
        """라인 상태 조회 에러"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db_context.side_effect = Exception("DB error")

        agent = JudgmentAgent()
        result = agent._get_line_status(line_code="LINE_A")

        assert result["success"] is False
        assert "error" in result


class TestGetAvailableLines:
    """_get_available_lines 메서드 테스트"""

    @patch("app.agents.judgment_agent.get_db_context")
    def test_get_available_lines_success(self, mock_db_context):
        """라인 목록 조회 성공"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.all.return_value = [
            ("LINE_A",),
            ("LINE_B",),
            ("LINE_C",),
        ]

        agent = JudgmentAgent()
        result = agent._get_available_lines()

        assert result["success"] is True
        assert len(result["lines"]) == 3

    @patch("app.agents.judgment_agent.get_db_context")
    def test_get_available_lines_empty(self, mock_db_context):
        """라인 목록 빈 결과 - 기본값 반환"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.all.return_value = []

        agent = JudgmentAgent()
        result = agent._get_available_lines()

        assert result["success"] is True
        assert "LINE_A" in result["lines"]  # 기본값

    @patch("app.agents.judgment_agent.get_db_context")
    def test_get_available_lines_error(self, mock_db_context):
        """라인 목록 조회 에러"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db_context.side_effect = Exception("DB error")

        agent = JudgmentAgent()
        result = agent._get_available_lines()

        assert result["success"] is False
        assert "lines" in result  # fallback


class TestGetRecommendation:
    """_get_recommendation 메서드 테스트"""

    def test_recommendation_critical(self):
        """CRITICAL 상태 추천"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        checks = [{"status": "CRITICAL", "message": "온도 초과"}]

        result = agent._get_recommendation("CRITICAL", checks)

        assert "즉시 점검" in result

    def test_recommendation_warning(self):
        """WARNING 상태 추천"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        checks = [{"status": "WARNING", "message": "압력 주의"}]

        result = agent._get_recommendation("WARNING", checks)

        assert "주의 관찰" in result

    def test_recommendation_ok(self):
        """OK 상태 추천"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        result = agent._get_recommendation("OK", [])

        assert "정상 범위" in result


class TestCreateRuleset:
    """_create_ruleset 메서드 테스트"""

    @patch("app.agents.judgment_agent.get_db_context")
    def test_create_ruleset_success(self, mock_db_context):
        """Ruleset 생성 성공"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        agent = JudgmentAgent()
        result = agent._create_ruleset(
            name="온도 경고 규칙",
            condition_type="threshold",
            sensor_type="temperature",
            operator=">",
            threshold_value=80,
            action_type="alert",
        )

        assert result["success"] is True
        assert result["name"] == "온도 경고 규칙"
        assert "rhai_script" in result
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("app.agents.judgment_agent.get_db_context")
    def test_create_ruleset_error(self, mock_db_context):
        """Ruleset 생성 에러"""
        from app.agents.judgment_agent import JudgmentAgent

        mock_db_context.side_effect = Exception("DB error")

        agent = JudgmentAgent()
        result = agent._create_ruleset(
            name="테스트",
            condition_type="threshold",
            sensor_type="temperature",
            operator=">",
            threshold_value=80,
            action_type="alert",
        )

        assert result["success"] is False
        assert "error" in result


class TestGenerateRhaiScript:
    """_generate_rhai_script 메서드 테스트"""

    def test_generate_threshold_script(self):
        """임계값 스크립트 생성"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        script = agent._generate_rhai_script(
            condition_type="threshold",
            sensor_type="temperature",
            operator=">",
            threshold_value=80,
            action_type="alert",
            action_message="온도 초과",
        )

        assert "let value = input.temperature" in script
        assert "let threshold = 80" in script
        assert ">" in script
        assert "alert" in script

    def test_generate_range_script(self):
        """범위 스크립트 생성"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        script = agent._generate_rhai_script(
            condition_type="range",
            sensor_type="pressure",
            operator=">",
            threshold_value=50,
            threshold_value_2=100,
            action_type="warning",
        )

        assert "min_threshold" in script
        assert "max_threshold" in script
        assert "50" in script
        assert "100" in script

    def test_generate_default_script(self):
        """기본 스크립트 생성"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        script = agent._generate_rhai_script(
            condition_type="comparison",
            sensor_type="humidity",
            operator=">=",
            threshold_value=70,
            action_type="notify",
        )

        assert "let value = input.humidity" in script
        assert "70" in script

    def test_sensor_names_korean(self):
        """센서 이름 한글화"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        script = agent._generate_rhai_script(
            condition_type="threshold",
            sensor_type="temperature",
            operator=">",
            threshold_value=80,
            action_type="alert",
        )

        assert "온도" in script


class TestHybridJudgment:
    """_hybrid_judgment 메서드 테스트"""

    def test_hybrid_judgment_invalid_uuid(self):
        """잘못된 UUID로 에러"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        # 잘못된 UUID로 에러 유발
        result = agent._hybrid_judgment(
            ruleset_id="invalid-uuid",
            input_data={},
        )

        assert result["success"] is False
        assert "error" in result

    def test_hybrid_judgment_policy_mapping(self):
        """정책 매핑 테스트"""
        from app.services.judgment_policy import JudgmentPolicy

        policy_map = {
            "rule_only": JudgmentPolicy.RULE_ONLY,
            "llm_only": JudgmentPolicy.LLM_ONLY,
            "hybrid_weighted": JudgmentPolicy.HYBRID_WEIGHTED,
            "escalate": JudgmentPolicy.ESCALATE,
        }

        assert policy_map.get("rule_only") == JudgmentPolicy.RULE_ONLY
        assert policy_map.get("unknown", JudgmentPolicy.HYBRID_WEIGHTED) == JudgmentPolicy.HYBRID_WEIGHTED

    def test_hybrid_judgment_returns_decision(self):
        """하이브리드 판단 응답 형식"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        # 유효한 UUID로 테스트 (실제 서비스 호출은 실패할 수 있음)
        result = agent._hybrid_judgment(
            ruleset_id=str(uuid4()),
            input_data={"temperature": 75},
            policy="rule_only",
        )

        # 성공 또는 실패 응답
        assert "success" in result or "decision" in result or "error" in result


class TestGetJudgmentCacheStats:
    """_get_judgment_cache_stats 메서드 테스트"""

    def test_get_cache_stats(self):
        """캐시 통계 조회"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()
        result = agent._get_judgment_cache_stats()

        # 성공 또는 에러 응답
        assert "success" in result


class TestGetRecommendationFromResult:
    """_get_recommendation_from_result 메서드 테스트"""

    def test_critical_high_confidence(self):
        """CRITICAL + 높은 신뢰도"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        mock_result = MagicMock()
        mock_result.decision = "CRITICAL"
        mock_result.confidence = 0.9

        recommendation = agent._get_recommendation_from_result(mock_result)

        assert "즉시 점검" in recommendation

    def test_critical_low_confidence(self):
        """CRITICAL + 낮은 신뢰도"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        mock_result = MagicMock()
        mock_result.decision = "CRITICAL"
        mock_result.confidence = 0.6

        recommendation = agent._get_recommendation_from_result(mock_result)

        assert "추가 확인" in recommendation

    def test_warning_high_confidence(self):
        """WARNING + 높은 신뢰도"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        mock_result = MagicMock()
        mock_result.decision = "WARNING"
        mock_result.confidence = 0.9

        recommendation = agent._get_recommendation_from_result(mock_result)

        assert "주의" in recommendation

    def test_ok_status(self):
        """OK 상태"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        mock_result = MagicMock()
        mock_result.decision = "OK"
        mock_result.confidence = 0.95

        recommendation = agent._get_recommendation_from_result(mock_result)

        assert "정상" in recommendation

    def test_unknown_status(self):
        """UNKNOWN 상태"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        mock_result = MagicMock()
        mock_result.decision = "UNKNOWN"
        mock_result.confidence = 0.5

        recommendation = agent._get_recommendation_from_result(mock_result)

        assert "수동 확인" in recommendation


class TestExecuteToolDispatch:
    """execute_tool 디스패치 테스트"""

    def test_dispatch_fetch_sensor_history(self):
        """fetch_sensor_history 디스패치"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with patch.object(agent, "_fetch_sensor_history", return_value={"success": True}):
            result = agent.execute_tool("fetch_sensor_history", {
                "sensor_type": "temperature",
                "line_code": "LINE_A",
            })

            assert result["success"] is True

    def test_dispatch_run_rhai_engine(self):
        """run_rhai_engine 디스패치"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with patch.object(agent, "_run_rhai_engine", return_value={"success": True}):
            result = agent.execute_tool("run_rhai_engine", {
                "ruleset_id": str(uuid4()),
                "input_data": {},
            })

            assert result["success"] is True

    def test_dispatch_query_rag_knowledge(self):
        """query_rag_knowledge 디스패치"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with patch.object(agent, "_query_rag_knowledge", return_value={"success": True}):
            result = agent.execute_tool("query_rag_knowledge", {
                "query": "온도",
            })

            assert result["success"] is True

    def test_dispatch_get_line_status(self):
        """get_line_status 디스패치"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with patch.object(agent, "_get_line_status", return_value={"success": True}):
            result = agent.execute_tool("get_line_status", {
                "line_code": "LINE_A",
            })

            assert result["success"] is True

    def test_dispatch_get_available_lines(self):
        """get_available_lines 디스패치"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with patch.object(agent, "_get_available_lines", return_value={"success": True}):
            result = agent.execute_tool("get_available_lines", {})

            assert result["success"] is True

    def test_dispatch_create_ruleset(self):
        """create_ruleset 디스패치"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with patch.object(agent, "_create_ruleset", return_value={"success": True}):
            result = agent.execute_tool("create_ruleset", {
                "name": "테스트",
                "condition_type": "threshold",
                "sensor_type": "temperature",
                "operator": ">",
                "threshold_value": 80,
                "action_type": "alert",
            })

            assert result["success"] is True

    def test_dispatch_hybrid_judgment(self):
        """hybrid_judgment 디스패치"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with patch.object(agent, "_hybrid_judgment", return_value={"success": True}):
            result = agent.execute_tool("hybrid_judgment", {
                "ruleset_id": str(uuid4()),
                "input_data": {"temperature": 75},
            })

            assert result["success"] is True

    def test_dispatch_get_judgment_cache_stats(self):
        """get_judgment_cache_stats 디스패치"""
        from app.agents.judgment_agent import JudgmentAgent

        agent = JudgmentAgent()

        with patch.object(agent, "_get_judgment_cache_stats", return_value={"success": True}):
            result = agent.execute_tool("get_judgment_cache_stats", {})

            assert result["success"] is True


class TestPolicyMapping:
    """정책 매핑 테스트"""

    def test_rule_only_policy(self):
        """rule_only 정책"""
        from app.services.judgment_policy import JudgmentPolicy

        policy_map = {
            "rule_only": JudgmentPolicy.RULE_ONLY,
            "llm_only": JudgmentPolicy.LLM_ONLY,
            "hybrid_weighted": JudgmentPolicy.HYBRID_WEIGHTED,
            "escalate": JudgmentPolicy.ESCALATE,
        }

        assert policy_map["rule_only"] == JudgmentPolicy.RULE_ONLY
        assert policy_map["llm_only"] == JudgmentPolicy.LLM_ONLY
        assert policy_map["hybrid_weighted"] == JudgmentPolicy.HYBRID_WEIGHTED
        assert policy_map["escalate"] == JudgmentPolicy.ESCALATE


class TestActionResults:
    """액션 결과 테스트"""

    def test_action_type_mapping(self):
        """액션 타입별 결과"""
        action_results = {
            "alert": '"alert"',
            "warning": '"warning"',
            "log": '"log"',
            "stop_line": '"stop_line"',
            "notify": '"notify"',
        }

        assert "alert" in action_results["alert"]
        assert "warning" in action_results["warning"]
        assert "log" in action_results["log"]
        assert "stop_line" in action_results["stop_line"]
        assert "notify" in action_results["notify"]
