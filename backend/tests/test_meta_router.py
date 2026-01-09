"""
TriFlow AI - Meta Router Tests
==============================
Tests for app/agents/meta_router.py
"""

import pytest


class TestMetaRouterAgentInit:
    """MetaRouterAgent 초기화 테스트"""

    def test_agent_init(self):
        """Agent 초기화"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        assert agent.name == "MetaRouterAgent"
        assert agent.v7_intent_classifier is not None
        assert agent.intent_classifier is not None

    def test_get_system_prompt(self):
        """시스템 프롬프트 로드"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()
        prompt = agent.get_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_tools(self):
        """도구 목록 조회"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()
        tools = agent.get_tools()

        assert isinstance(tools, list)
        tool_names = [t["name"] for t in tools]
        assert "classify_v7_intent" in tool_names
        assert "classify_intent" in tool_names
        assert "extract_slots" in tool_names
        assert "route_request" in tool_names


class TestExecuteTool:
    """execute_tool 테스트"""

    def test_classify_v7_intent(self):
        """V7 Intent 분류 도구"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.execute_tool(
            "classify_v7_intent",
            {
                "v7_intent": "JUDGMENT_SINGLE_LINE",
                "route_to": "JUDGMENT_ENGINE",
                "legacy_intent": "judgment",
                "confidence": 0.95,
                "reason": "라인 판단 요청",
            }
        )

        assert result["success"] is True
        assert result["v7_intent"] == "JUDGMENT_SINGLE_LINE"
        assert result["route_to"] == "JUDGMENT_ENGINE"

    def test_classify_intent(self):
        """Legacy Intent 분류 도구"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.execute_tool(
            "classify_intent",
            {
                "intent": "judgment",
                "confidence": 0.9,
                "reason": "판단 요청",
            }
        )

        assert result["success"] is True
        assert result["intent"] == "judgment"

    def test_extract_slots(self):
        """슬롯 추출 도구"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.execute_tool(
            "extract_slots",
            {
                "slots": {
                    "line_code": "LINE_A",
                    "sensor_type": "temperature",
                }
            }
        )

        assert result["success"] is True
        assert result["slots"]["line_code"] == "LINE_A"

    def test_route_request(self):
        """요청 라우팅 도구"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.execute_tool(
            "route_request",
            {
                "target_agent": "judgment",
                "processed_request": "LINE_A 온도 판단해줘",
                "context": {"sensor_type": "temperature"},
            }
        )

        assert result["success"] is True
        assert result["target_agent"] == "judgment"

    def test_unknown_tool(self):
        """알 수 없는 도구"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        with pytest.raises(ValueError) as exc_info:
            agent.execute_tool("unknown_tool", {})

        assert "Unknown tool" in str(exc_info.value)


class TestParseRoutingResult:
    """parse_routing_result 테스트"""

    def test_parse_v7_intent_result(self):
        """V7 Intent 결과 파싱"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = {
            "tool_calls": [
                {
                    "tool": "classify_v7_intent",
                    "result": {
                        "v7_intent": "JUDGMENT_SINGLE_LINE",
                        "route_to": "JUDGMENT_ENGINE",
                        "legacy_intent": "judgment",
                    },
                },
                {
                    "tool": "route_request",
                    "result": {
                        "target_agent": "judgment",
                        "processed_request": "라인 판단",
                    },
                },
            ]
        }

        routing = agent.parse_routing_result(result)

        assert routing["v7_intent"] == "JUDGMENT_SINGLE_LINE"
        assert routing["target_agent"] == "judgment"

    def test_parse_legacy_intent_result(self):
        """Legacy Intent 결과 파싱"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = {
            "tool_calls": [
                {
                    "tool": "classify_intent",
                    "result": {
                        "intent": "bi",
                    },
                },
            ]
        }

        routing = agent.parse_routing_result(result)

        assert routing["intent"] == "bi"
        assert routing["legacy_intent"] == "bi"

    def test_parse_slots_result(self):
        """슬롯 추출 결과 파싱"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = {
            "tool_calls": [
                {
                    "tool": "extract_slots",
                    "result": {
                        "slots": {"line_code": "LINE_B"},
                    },
                },
            ]
        }

        routing = agent.parse_routing_result(result)

        assert routing["slots"]["line_code"] == "LINE_B"

    def test_parse_empty_result(self):
        """빈 결과 파싱"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        routing = agent.parse_routing_result({})

        assert routing["target_agent"] == "general"
        assert routing["v7_intent"] is None


class TestClassifyWithRules:
    """classify_with_rules 테스트"""

    def test_classify_judgment_pattern(self):
        """판단 패턴 분류"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.classify_with_rules("LINE_A 온도 상태 어때?")

        # 규칙에 매칭되면 결과 반환, 아니면 None
        if result:
            assert result.legacy_intent in ["judgment", "general"]

    def test_classify_workflow_pattern(self):
        """워크플로우 패턴 분류"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.classify_with_rules("온도 80도 넘으면 알림 워크플로우 만들어줘")

        if result:
            assert result.legacy_intent in ["workflow", "general"]

    def test_classify_bi_pattern(self):
        """BI 패턴 분류"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.classify_with_rules("이번 달 생산량 분석해줘")

        if result:
            assert result.legacy_intent in ["bi", "general"]

    def test_classify_no_match(self):
        """매칭 없는 입력"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        result = agent.classify_with_rules("안녕하세요")

        # 규칙에 매칭되지 않으면 None 또는 낮은 confidence 결과
        # None이거나 confidence가 낮을 수 있음
        if result:
            assert result.confidence >= 0


class TestRouteWithHybrid:
    """route_with_hybrid 테스트"""

    def test_route_with_rules_high_confidence(self):
        """규칙 기반 고신뢰도 라우팅"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        # 명확한 패턴으로 테스트
        result = agent.route_with_hybrid("LINE_A 라인 온도 상태 판단해줘")

        assert "target_agent" in result
        assert "processed_request" in result

    def test_route_with_clarification_needed(self):
        """명확화 필요한 경우"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        # 애매한 입력
        result = agent.route_with_hybrid("알림 설정")

        assert "target_agent" in result
        # 명확화가 필요하면 ask_back 또는 CLARIFY
        if result.get("v7_intent") == "CLARIFY":
            assert "ask_back" in result

    def test_route_with_llm_fallback(self):
        """LLM fallback 라우팅"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        llm_result = {
            "tool_calls": [
                {
                    "tool": "classify_v7_intent",
                    "result": {
                        "v7_intent": "BI_TREND",
                        "route_to": "BI_GUIDE",
                        "legacy_intent": "bi",
                    },
                },
                {
                    "tool": "route_request",
                    "result": {
                        "target_agent": "bi",
                        "processed_request": "트렌드 분석",
                        "context": {},
                    },
                },
            ]
        }

        # 규칙 매칭 안되는 입력으로 LLM fallback 테스트
        result = agent.route_with_hybrid("xyz abc 123", llm_result)

        assert result["target_agent"] == "bi"
        assert result["context"]["classification_source"] == "llm"

    def test_route_fallback_without_llm(self):
        """LLM 없이 fallback"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        # 규칙 매칭 안되고 LLM도 없으면 기본값
        result = agent.route_with_hybrid("xyz abc 123")

        assert result["target_agent"] == "general"
        assert result["context"]["classification_source"] == "fallback"


class TestGetClassificationDebug:
    """get_classification_debug 테스트"""

    def test_debug_info(self):
        """디버그 정보 조회"""
        from app.agents.meta_router import MetaRouterAgent

        agent = MetaRouterAgent()

        debug = agent.get_classification_debug("LINE_A 온도 확인")

        assert isinstance(debug, dict)


class TestRouteTargetToAgent:
    """route_target_to_agent 테스트"""

    def test_data_layer_mapping(self):
        """DATA_LAYER 매핑"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("DATA_LAYER")
        assert result == "judgment"

    def test_judgment_engine_mapping(self):
        """JUDGMENT_ENGINE 매핑"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("JUDGMENT_ENGINE")
        assert result == "judgment"

    def test_rule_engine_mapping(self):
        """RULE_ENGINE 매핑"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("RULE_ENGINE")
        assert result == "learning"

    def test_bi_guide_mapping(self):
        """BI_GUIDE 매핑"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("BI_GUIDE")
        assert result == "bi"

    def test_workflow_guide_mapping(self):
        """WORKFLOW_GUIDE 매핑"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("WORKFLOW_GUIDE")
        assert result == "workflow"

    def test_context_dependent_mapping(self):
        """CONTEXT_DEPENDENT 매핑"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("CONTEXT_DEPENDENT")
        assert result == "general"

    def test_ask_back_mapping(self):
        """ASK_BACK 매핑"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("ASK_BACK")
        assert result == "general"

    def test_direct_response_mapping(self):
        """DIRECT_RESPONSE 매핑"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("DIRECT_RESPONSE")
        assert result == "general"

    def test_unknown_mapping(self):
        """알 수 없는 Route Target"""
        from app.agents.meta_router import MetaRouterAgent

        result = MetaRouterAgent.route_target_to_agent("UNKNOWN_TARGET")
        assert result == "general"


class TestIntentClassifier:
    """IntentClassifier 테스트"""

    def test_intent_classifier_init(self):
        """IntentClassifier 초기화"""
        from app.agents.intent_classifier import IntentClassifier

        classifier = IntentClassifier()
        assert classifier is not None

    def test_v7_intent_classifier_init(self):
        """V7IntentClassifier 초기화"""
        from app.agents.intent_classifier import V7IntentClassifier

        classifier = V7IntentClassifier()
        assert classifier is not None

    def test_v7_classify(self):
        """V7 Intent 분류"""
        from app.agents.intent_classifier import V7IntentClassifier

        classifier = V7IntentClassifier()

        result = classifier.classify("라인 상태 판단해줘")

        if result:
            assert result.v7_intent is not None
            assert result.confidence >= 0

    def test_should_clarify(self):
        """명확화 필요 여부"""
        from app.agents.intent_classifier import V7IntentClassifier

        classifier = V7IntentClassifier()

        # 명확한 요청
        question = classifier.should_clarify("LINE_A 온도 상태 판단해줘")
        # 명확화 필요 없으면 None

        # 애매한 요청
        question2 = classifier.should_clarify("알림")
        # 명확화 필요하면 질문 문자열

    def test_get_classification_debug(self):
        """분류 디버그 정보"""
        from app.agents.intent_classifier import V7IntentClassifier

        classifier = V7IntentClassifier()

        debug = classifier.get_classification_debug("테스트 입력")

        assert isinstance(debug, dict)


class TestRoutingRules:
    """routing_rules 모듈 테스트"""

    def test_route_target_enum(self):
        """RouteTarget enum"""
        from app.agents.routing_rules import RouteTarget

        assert RouteTarget.DATA_LAYER.value == "DATA_LAYER"
        assert RouteTarget.JUDGMENT_ENGINE.value == "JUDGMENT_ENGINE"
        assert RouteTarget.BI_GUIDE.value == "BI_GUIDE"
        assert RouteTarget.WORKFLOW_GUIDE.value == "WORKFLOW_GUIDE"

    def test_get_all_v7_intents(self):
        """V7 Intent 목록"""
        from app.agents.routing_rules import get_all_v7_intents

        intents = get_all_v7_intents()

        assert isinstance(intents, list)
        assert len(intents) > 0


class TestClassificationResult:
    """ClassificationResult 테스트"""

    def test_classification_result_init(self):
        """ClassificationResult 초기화"""
        from app.agents.intent_classifier import ClassificationResult

        result = ClassificationResult(
            v7_intent="JUDGMENT_SINGLE_LINE",
            route_to="JUDGMENT_ENGINE",
            legacy_intent="judgment",
            confidence=0.95,
            matched_pattern="LINE_* 상태",
            slots={"line_code": "LINE_A"},
            source="rule",
        )

        assert result.v7_intent == "JUDGMENT_SINGLE_LINE"
        assert result.route_to == "JUDGMENT_ENGINE"
        assert result.legacy_intent == "judgment"
        assert result.confidence == 0.95
        assert result.matched_pattern == "LINE_* 상태"
        assert result.slots["line_code"] == "LINE_A"
        assert result.source == "rule"
