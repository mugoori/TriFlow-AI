"""
Learning Agent 테스트

LearningAgent 클래스의 모든 메서드 테스트
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestLearningAgentInit:
    """LearningAgent 초기화 테스트"""

    def test_agent_init(self):
        """에이전트 초기화"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        assert agent.name == "LearningAgent"
        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent.max_tokens == 4096

    def test_agent_inherits_base_agent(self):
        """BaseAgent 상속 확인"""
        from app.agents.learning_agent import LearningAgent
        from app.agents.base_agent import BaseAgent

        agent = LearningAgent()

        assert isinstance(agent, BaseAgent)


class TestGetSystemPrompt:
    """get_system_prompt 메서드 테스트"""

    def test_get_system_prompt_returns_string(self):
        """시스템 프롬프트 반환"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        prompt = agent.get_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_system_prompt_fallback(self, mock_open):
        """프롬프트 파일 없을 때 기본값"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        prompt = agent.get_system_prompt()

        assert "Learning Agent" in prompt


class TestGetTools:
    """get_tools 메서드 테스트"""

    def test_get_tools_returns_list(self):
        """도구 목록 반환"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        tools = agent.get_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_tools_contains_required_tools(self):
        """필수 도구 포함 확인"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        tools = agent.get_tools()
        tool_names = [t["name"] for t in tools]

        assert "analyze_feedback_logs" in tool_names
        assert "propose_new_rule" in tool_names
        assert "run_zwave_simulation" in tool_names
        assert "get_rule_performance" in tool_names
        assert "create_ruleset" in tool_names
        assert "analyze_and_suggest_rules" in tool_names
        assert "list_pending_proposals" in tool_names
        assert "review_proposal" in tool_names

    def test_tool_has_required_fields(self):
        """도구 필수 필드 확인"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        tools = agent.get_tools()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool


class TestExecuteTool:
    """execute_tool 메서드 테스트"""

    def test_execute_unknown_tool_raises_error(self):
        """알 수 없는 도구 실행 시 에러"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with pytest.raises(ValueError) as exc_info:
            agent.execute_tool("unknown_tool", {})

        assert "Unknown tool" in str(exc_info.value)


class TestExtractPatterns:
    """_extract_patterns 메서드 테스트"""

    def test_extract_patterns_from_feedbacks(self):
        """피드백에서 패턴 추출"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        # Mock feedbacks
        mock_feedbacks = []
        for i in range(5):
            fb = MagicMock()
            fb.feedback_text = "temperature high warning alert"
            fb.feedback_type = "negative"
            fb.corrected_output = None
            fb.original_output = None
            mock_feedbacks.append(fb)

        patterns = agent._extract_patterns(mock_feedbacks, min_occurrences=3)

        # "temperature", "high", "warning", "alert" 중 일부가 패턴으로 추출되어야 함
        assert len(patterns) > 0
        assert all("type" in p for p in patterns)
        assert all("occurrences" in p for p in patterns)

    def test_extract_patterns_correction_type(self):
        """수정 타입 피드백 패턴 추출"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        mock_feedbacks = []
        for i in range(5):
            fb = MagicMock()
            fb.feedback_text = ""
            fb.feedback_type = "correction"
            fb.corrected_output = {"status": "WARNING", "threshold": 80}
            fb.original_output = {"status": "NORMAL", "threshold": 70}
            mock_feedbacks.append(fb)

        patterns = agent._extract_patterns(mock_feedbacks, min_occurrences=3)

        # correction 패턴이 있어야 함
        correction_patterns = [p for p in patterns if p["type"] == "correction"]
        assert len(correction_patterns) > 0

    def test_extract_patterns_empty_feedbacks(self):
        """빈 피드백 리스트"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        patterns = agent._extract_patterns([], min_occurrences=3)

        assert patterns == []


class TestGenerateRecommendations:
    """_generate_recommendations 메서드 테스트"""

    def test_generate_recommendations_from_patterns(self):
        """패턴에서 추천 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        patterns = [
            {"type": "keyword", "value": "temperature", "occurrences": 10},
            {"type": "correction", "value": "field_change:status", "occurrences": 5},
        ]

        recommendations = agent._generate_recommendations(patterns)

        assert len(recommendations) > 0
        assert any("temperature" in r for r in recommendations)
        assert any("status" in r for r in recommendations)

    def test_generate_recommendations_empty_patterns(self):
        """빈 패턴 리스트"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        recommendations = agent._generate_recommendations([])

        assert len(recommendations) == 1
        assert "발견되지 않았습니다" in recommendations[0]


class TestGenerateRhaiScript:
    """_generate_rhai_script 메서드 테스트"""

    def test_generate_rhai_script_basic(self):
        """기본 Rhai 스크립트 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        script = agent._generate_rhai_script(
            rule_name="온도 경고",
            description="온도 80도 초과 시 경고",
            trigger_condition="온도 80도 초과",
            action_description="알림 전송",
        )

        assert "온도 경고" in script
        assert "result" in script
        assert "let input" in script

    def test_generate_rhai_script_with_temperature(self):
        """온도 조건 스크립트 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        script = agent._generate_rhai_script(
            rule_name="온도 체크",
            description="온도 체크",
            trigger_condition="온도가 75도를 초과하면",
            action_description="알림 전송",
        )

        assert "temperature" in script
        assert "75" in script

    def test_generate_rhai_script_with_pressure(self):
        """압력 조건 스크립트 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        script = agent._generate_rhai_script(
            rule_name="압력 체크",
            description="압력 체크",
            trigger_condition="압력 100 초과",
            action_description="라인 중지",
        )

        assert "pressure" in script
        assert "100" in script


class TestParseCondition:
    """_parse_condition 메서드 테스트"""

    def test_parse_condition_temperature(self):
        """온도 조건 파싱"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        code = agent._parse_condition("온도 80 초과")

        assert "temperature" in code
        assert "80" in code

    def test_parse_condition_pressure(self):
        """압력 조건 파싱"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        code = agent._parse_condition("pressure > 100")

        assert "pressure" in code
        assert "100" in code

    def test_parse_condition_unknown(self):
        """알 수 없는 조건 파싱"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        code = agent._parse_condition("unknown condition xyz")

        assert "TODO" in code


class TestParseAction:
    """_parse_action 메서드 테스트"""

    def test_parse_action_notification(self):
        """알림 액션 파싱"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        code = agent._parse_action("알림 전송")

        assert "notification" in code
        assert "slack" in code

    def test_parse_action_stop(self):
        """중지 액션 파싱"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        code = agent._parse_action("라인 중지")

        assert "stop_line" in code

    def test_parse_action_default(self):
        """기본 액션 파싱"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        code = agent._parse_action("something else")

        assert "log" in code


class TestRunZwaveSimulation:
    """_run_zwave_simulation 메서드 테스트"""

    def test_run_zwave_simulation_basic(self):
        """기본 시뮬레이션 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._run_zwave_simulation(
            rule_script="test script",
            scenario="random",
            iterations=10,
        )

        assert result["success"] is True
        assert result["iterations"] == 10
        assert "accuracy" in result
        assert "sample_results" in result
        assert len(result["sample_results"]) <= 5

    def test_run_zwave_simulation_normal_scenario(self):
        """정상 시나리오 시뮬레이션"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._run_zwave_simulation(
            rule_script="test",
            scenario="normal",
            iterations=20,
        )

        assert result["success"] is True
        assert result["scenario"] == "normal"

    def test_run_zwave_simulation_warning_scenario(self):
        """경고 시나리오 시뮬레이션"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._run_zwave_simulation(
            rule_script="test",
            scenario="warning",
            iterations=20,
        )

        assert result["success"] is True
        assert result["scenario"] == "warning"

    def test_run_zwave_simulation_critical_scenario(self):
        """위험 시나리오 시뮬레이션"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._run_zwave_simulation(
            rule_script="test",
            scenario="critical",
            iterations=20,
        )

        assert result["success"] is True
        assert result["scenario"] == "critical"


class TestGenerateSimulationData:
    """_generate_simulation_data 메서드 테스트"""

    def test_generate_simulation_data_normal(self):
        """정상 시나리오 데이터 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        data = agent._generate_simulation_data("normal")

        assert "temperature" in data
        assert "pressure" in data
        assert "humidity" in data
        assert 20 <= data["temperature"] <= 70
        assert 2 <= data["pressure"] <= 8

    def test_generate_simulation_data_warning(self):
        """경고 시나리오 데이터 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        data = agent._generate_simulation_data("warning")

        assert 70 <= data["temperature"] <= 85
        assert 8 <= data["pressure"] <= 12

    def test_generate_simulation_data_critical(self):
        """위험 시나리오 데이터 생성"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        data = agent._generate_simulation_data("critical")

        assert 85 <= data["temperature"] <= 120
        assert 12 <= data["pressure"] <= 20


class TestEvaluateRule:
    """_evaluate_rule 메서드 테스트"""

    def test_evaluate_rule_normal(self):
        """정상 상태 평가"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._evaluate_rule(
            rule_script="test",
            input_data={"temperature": 50, "pressure": 5}
        )

        assert result["status"] == "NORMAL"
        assert len(result["checks"]) == 0

    def test_evaluate_rule_warning_temperature(self):
        """온도 경고 상태 평가"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._evaluate_rule(
            rule_script="test",
            input_data={"temperature": 75, "pressure": 5}
        )

        assert result["status"] == "WARNING"
        assert any(c["type"] == "temperature" for c in result["checks"])

    def test_evaluate_rule_critical(self):
        """위험 상태 평가"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._evaluate_rule(
            rule_script="test",
            input_data={"temperature": 90, "pressure": 15}
        )

        assert result["status"] == "CRITICAL"


class TestGetExpectedOutcome:
    """_get_expected_outcome 메서드 테스트"""

    def test_get_expected_outcome_normal(self):
        """정상 기대 결과"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._get_expected_outcome({"temperature": 50, "pressure": 5})

        assert result == "NORMAL"

    def test_get_expected_outcome_warning(self):
        """경고 기대 결과"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._get_expected_outcome({"temperature": 75, "pressure": 5})

        assert result == "WARNING"

    def test_get_expected_outcome_critical(self):
        """위험 기대 결과"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._get_expected_outcome({"temperature": 90, "pressure": 15})

        assert result == "CRITICAL"


class TestGetSimulationRecommendation:
    """_get_simulation_recommendation 메서드 테스트"""

    def test_recommendation_high_accuracy(self):
        """높은 정확도 추천"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        rec = agent._get_simulation_recommendation(0.96)

        assert "매우 정확" in rec
        assert "배포" in rec

    def test_recommendation_good_accuracy(self):
        """양호한 정확도 추천"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        rec = agent._get_simulation_recommendation(0.88)

        assert "양호" in rec

    def test_recommendation_low_accuracy(self):
        """낮은 정확도 추천"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        rec = agent._get_simulation_recommendation(0.72)

        assert "낮습니다" in rec

    def test_recommendation_very_low_accuracy(self):
        """매우 낮은 정확도 추천"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        rec = agent._get_simulation_recommendation(0.50)

        assert "재설계" in rec


class TestAnalyzeFeedbackLogs:
    """_analyze_feedback_logs 메서드 테스트"""

    @patch("app.agents.learning_agent.get_db_context")
    def test_analyze_feedback_logs_success(self, mock_db_context):
        """피드백 로그 분석 성공"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_feedback = MagicMock()
        mock_feedback.feedback_type = "negative"
        mock_feedback.feedback_text = "temperature too high"
        mock_feedback.corrected_output = None
        mock_feedback.original_output = None
        mock_feedback.is_processed = False

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_feedback] * 5

        agent = LearningAgent()
        result = agent._analyze_feedback_logs(
            feedback_type="all",
            days=7,
            min_occurrences=3,
        )

        assert result["success"] is True
        assert result["total_feedbacks"] == 5

    @patch("app.agents.learning_agent.get_db_context")
    def test_analyze_feedback_logs_empty(self, mock_db_context):
        """피드백 없음"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.all.return_value = []

        agent = LearningAgent()
        result = agent._analyze_feedback_logs()

        assert result["success"] is True
        assert result["total_feedbacks"] == 0
        assert "분석할 피드백이 없습니다" in result["summary"]

    @patch("app.agents.learning_agent.get_db_context")
    def test_analyze_feedback_logs_db_error(self, mock_db_context):
        """DB 에러 시 기본값 반환"""
        from app.agents.learning_agent import LearningAgent

        mock_db_context.side_effect = Exception("DB error")

        agent = LearningAgent()
        result = agent._analyze_feedback_logs()

        assert result["success"] is True
        assert result["total_feedbacks"] == 0
        assert "note" in result


class TestProposeNewRule:
    """_propose_new_rule 메서드 테스트"""

    @patch("app.agents.learning_agent.get_db_context")
    def test_propose_new_rule_success(self, mock_db_context):
        """규칙 제안 성공"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = uuid4()
        mock_db.query.return_value.first.return_value = mock_tenant

        mock_proposal = MagicMock()
        mock_proposal.proposal_id = uuid4()

        agent = LearningAgent()
        result = agent._propose_new_rule(
            rule_name="온도 경고",
            rule_description="온도 80도 초과 시 경고",
            trigger_condition="온도 80도 초과",
            action_description="알림 전송",
        )

        assert result["success"] is True
        assert result["rule_name"] == "온도 경고"
        assert "rhai_script" in result

    @patch("app.agents.learning_agent.get_db_context")
    def test_propose_new_rule_db_error(self, mock_db_context):
        """DB 에러 시 기본값 반환"""
        from app.agents.learning_agent import LearningAgent

        mock_db_context.side_effect = Exception("DB error")

        agent = LearningAgent()
        result = agent._propose_new_rule(
            rule_name="테스트 규칙",
            rule_description="테스트",
            trigger_condition="온도 80도 초과",
            action_description="알림",
        )

        assert result["success"] is True
        assert result["status"] == "draft"
        assert "note" in result


class TestGetRulePerformance:
    """_get_rule_performance 메서드 테스트"""

    @patch("app.agents.learning_agent.get_db_context")
    def test_get_rule_performance_success(self, mock_db_context):
        """규칙 성능 조회 성공"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_execution = MagicMock()
        mock_execution.confidence = 0.85
        mock_execution.execution_time_ms = 100
        mock_execution.method_used = "rhai"

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_execution] * 10

        agent = LearningAgent()
        result = agent._get_rule_performance(days=30)

        assert result["success"] is True
        assert result["total_executions"] == 10
        assert "average_confidence" in result

    @patch("app.agents.learning_agent.get_db_context")
    def test_get_rule_performance_empty(self, mock_db_context):
        """실행 데이터 없음"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.all.return_value = []

        agent = LearningAgent()
        result = agent._get_rule_performance()

        assert result["success"] is True
        assert result["total_executions"] == 0

    @patch("app.agents.learning_agent.get_db_context")
    def test_get_rule_performance_db_error(self, mock_db_context):
        """DB 에러 시 기본값 반환"""
        from app.agents.learning_agent import LearningAgent

        mock_db_context.side_effect = Exception("DB error")

        agent = LearningAgent()
        result = agent._get_rule_performance()

        assert result["success"] is True
        assert "note" in result


class TestCreateRuleset:
    """_create_ruleset 메서드 테스트"""

    @patch("app.agents.learning_agent.get_db_context")
    def test_create_ruleset_success(self, mock_db_context):
        """룰셋 생성 성공"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = uuid4()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_tenant

        agent = LearningAgent()
        result = agent._create_ruleset(
            name="온도 경고 규칙",
            sensor_type="temperature",
            warning_threshold=70,
            critical_threshold=80,
        )

        assert result["success"] is True
        assert "ruleset_id" in result
        assert result["name"] == "온도 경고 규칙"

    @patch("app.agents.learning_agent.get_db_context")
    def test_create_ruleset_no_tenant(self, mock_db_context):
        """테넌트 없음"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        agent = LearningAgent()
        result = agent._create_ruleset(
            name="테스트",
            sensor_type="temperature",
            warning_threshold=70,
            critical_threshold=80,
        )

        assert result["success"] is False
        assert "tenant" in result["error"].lower()

    @patch("app.agents.learning_agent.get_db_context")
    def test_create_ruleset_db_error(self, mock_db_context):
        """DB 에러"""
        from app.agents.learning_agent import LearningAgent

        mock_db_context.side_effect = Exception("DB error")

        agent = LearningAgent()
        result = agent._create_ruleset(
            name="테스트",
            sensor_type="temperature",
            warning_threshold=70,
            critical_threshold=80,
        )

        assert result["success"] is False
        assert "error" in result


class TestAnalyzeAndSuggestRules:
    """_analyze_and_suggest_rules 메서드 테스트"""

    @patch("app.agents.learning_agent.get_db_context")
    def test_analyze_and_suggest_rules_no_patterns(self, mock_db_context):
        """패턴 없음"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.services.feedback_analyzer.FeedbackAnalyzer") as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_feedback_patterns.return_value = []
            mock_analyzer_class.return_value = mock_analyzer

            agent = LearningAgent()
            result = agent._analyze_and_suggest_rules()

            assert result["success"] is True
            assert result["patterns_found"] == 0

    @patch("app.agents.learning_agent.get_db_context")
    def test_analyze_and_suggest_rules_error(self, mock_db_context):
        """에러 발생"""
        from app.agents.learning_agent import LearningAgent

        mock_db_context.side_effect = Exception("error")

        agent = LearningAgent()
        result = agent._analyze_and_suggest_rules()

        assert result["success"] is False
        assert "error" in result


class TestListPendingProposals:
    """_list_pending_proposals 메서드 테스트"""

    @patch("app.agents.learning_agent.get_db_context")
    def test_list_pending_proposals_success(self, mock_db_context):
        """대기 제안 목록 조회"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_proposal = MagicMock()
        mock_proposal.proposal_id = uuid4()
        mock_proposal.rule_name = "테스트 규칙"
        mock_proposal.rule_description = "테스트"
        mock_proposal.source_type = "feedback_analysis"
        mock_proposal.confidence = 0.8
        mock_proposal.created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_proposal]

        agent = LearningAgent()
        result = agent._list_pending_proposals(limit=10)

        assert result["success"] is True
        assert result["total"] == 1

    @patch("app.agents.learning_agent.get_db_context")
    def test_list_pending_proposals_error(self, mock_db_context):
        """에러 발생"""
        from app.agents.learning_agent import LearningAgent

        mock_db_context.side_effect = Exception("error")

        agent = LearningAgent()
        result = agent._list_pending_proposals()

        assert result["success"] is False


class TestReviewProposal:
    """_review_proposal 메서드 테스트"""

    @patch("app.agents.learning_agent.get_db_context")
    def test_review_proposal_approve_success(self, mock_db_context):
        """제안 승인 성공"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        mock_ruleset = MagicMock()
        mock_ruleset.ruleset_id = uuid4()
        mock_ruleset.name = "승인된 규칙"

        with patch("app.services.feedback_analyzer.FeedbackAnalyzer") as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.approve_proposal.return_value = mock_ruleset
            mock_analyzer_class.return_value = mock_analyzer

            agent = LearningAgent()
            result = agent._review_proposal(
                proposal_id=str(uuid4()),
                action="approve",
            )

            assert result["success"] is True
            assert result["action"] == "approved"

    @patch("app.agents.learning_agent.get_db_context")
    def test_review_proposal_reject_success(self, mock_db_context):
        """제안 거절 성공"""
        from app.agents.learning_agent import LearningAgent

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.services.feedback_analyzer.FeedbackAnalyzer") as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.reject_proposal.return_value = True
            mock_analyzer_class.return_value = mock_analyzer

            agent = LearningAgent()
            result = agent._review_proposal(
                proposal_id=str(uuid4()),
                action="reject",
            )

            assert result["success"] is True
            assert result["action"] == "rejected"

    def test_review_proposal_invalid_uuid(self):
        """잘못된 UUID"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()
        result = agent._review_proposal(
            proposal_id="invalid-uuid",
            action="approve",
        )

        assert result["success"] is False
        assert "형식" in result["error"]


class TestExecuteToolDispatch:
    """execute_tool 디스패치 테스트"""

    def test_execute_tool_analyze_feedback_logs(self):
        """analyze_feedback_logs 도구 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with patch.object(agent, "_analyze_feedback_logs") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("analyze_feedback_logs", {})

            mock_method.assert_called_once()

    def test_execute_tool_propose_new_rule(self):
        """propose_new_rule 도구 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with patch.object(agent, "_propose_new_rule") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("propose_new_rule", {
                "rule_name": "테스트",
                "rule_description": "설명",
                "trigger_condition": "조건",
                "action_description": "액션",
            })

            mock_method.assert_called_once()

    def test_execute_tool_run_zwave_simulation(self):
        """run_zwave_simulation 도구 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with patch.object(agent, "_run_zwave_simulation") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("run_zwave_simulation", {
                "rule_script": "test"
            })

            mock_method.assert_called_once()

    def test_execute_tool_get_rule_performance(self):
        """get_rule_performance 도구 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with patch.object(agent, "_get_rule_performance") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("get_rule_performance", {})

            mock_method.assert_called_once()

    def test_execute_tool_create_ruleset(self):
        """create_ruleset 도구 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with patch.object(agent, "_create_ruleset") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("create_ruleset", {
                "name": "테스트",
                "sensor_type": "temperature",
                "warning_threshold": 70,
                "critical_threshold": 80,
            })

            mock_method.assert_called_once()

    def test_execute_tool_analyze_and_suggest_rules(self):
        """analyze_and_suggest_rules 도구 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with patch.object(agent, "_analyze_and_suggest_rules") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("analyze_and_suggest_rules", {})

            mock_method.assert_called_once()

    def test_execute_tool_list_pending_proposals(self):
        """list_pending_proposals 도구 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with patch.object(agent, "_list_pending_proposals") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("list_pending_proposals", {})

            mock_method.assert_called_once()

    def test_execute_tool_review_proposal(self):
        """review_proposal 도구 실행"""
        from app.agents.learning_agent import LearningAgent

        agent = LearningAgent()

        with patch.object(agent, "_review_proposal") as mock_method:
            mock_method.return_value = {"success": True}

            agent.execute_tool("review_proposal", {
                "proposal_id": str(uuid4()),
                "action": "approve",
            })

            mock_method.assert_called_once()
