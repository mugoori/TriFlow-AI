"""
V7 Intent 체계 테스트 (B-6 스펙)
================================
- 14개 V7 Intent 분류 테스트
- Route Target 매핑 테스트
- Legacy Intent 호환성 테스트
- 패턴 매칭 우선순위 테스트
"""
import pytest

from app.agents.routing_rules import (
    V7Intent,
    RouteTarget,
    V7_ROUTING_RULES,
    LEGACY_ROUTING_RULES,
    v7_to_legacy,
    get_all_v7_intents,
)
from app.agents.intent_classifier import (
    ClassificationResult,
    V7IntentClassifier,
    IntentClassifier,
)
from app.agents.meta_router import MetaRouterAgent


class TestV7IntentEnum:
    """V7Intent 열거형 테스트"""

    def test_all_14_intents_defined(self):
        """14개 V7 Intent 정의 확인"""
        expected_intents = [
            "CHECK", "TREND", "COMPARE", "RANK",
            "FIND_CAUSE", "DETECT_ANOMALY", "PREDICT", "WHAT_IF",
            "REPORT", "NOTIFY",
            "CONTINUE", "CLARIFY", "STOP", "SYSTEM"
        ]
        actual_intents = [intent.value for intent in V7Intent]
        assert len(actual_intents) == 14
        for intent in expected_intents:
            assert intent in actual_intents

    def test_intent_categories(self):
        """Intent 카테고리별 분류"""
        # 정보 조회 (Information)
        info_intents = ["CHECK", "TREND", "COMPARE", "RANK"]
        for intent in info_intents:
            assert V7Intent(intent) in V7Intent

        # 분석 (Analysis)
        analysis_intents = ["FIND_CAUSE", "DETECT_ANOMALY", "PREDICT", "WHAT_IF"]
        for intent in analysis_intents:
            assert V7Intent(intent) in V7Intent

        # 액션 (Action)
        action_intents = ["REPORT", "NOTIFY"]
        for intent in action_intents:
            assert V7Intent(intent) in V7Intent

        # 대화 제어 (Conversation)
        conv_intents = ["CONTINUE", "CLARIFY", "STOP", "SYSTEM"]
        for intent in conv_intents:
            assert V7Intent(intent) in V7Intent


class TestRouteTarget:
    """RouteTarget 열거형 테스트"""

    def test_all_route_targets(self):
        """8개 Route Target 정의 확인"""
        expected_targets = [
            "DATA_LAYER", "JUDGMENT_ENGINE", "RULE_ENGINE",
            "BI_GUIDE", "WORKFLOW_GUIDE",
            "CONTEXT_DEPENDENT", "ASK_BACK", "DIRECT_RESPONSE"
        ]
        actual_targets = [target.value for target in RouteTarget]
        assert len(actual_targets) == 8
        for target in expected_targets:
            assert target in actual_targets


class TestV7RoutingRules:
    """V7 라우팅 규칙 테스트"""

    def test_all_intents_have_rules(self):
        """모든 V7 Intent에 라우팅 규칙 존재"""
        for intent in V7Intent:
            assert intent.value in V7_ROUTING_RULES, f"Missing rule for {intent.value}"

    def test_rules_have_required_fields(self):
        """각 규칙에 필수 필드 존재"""
        required_fields = ["priority", "route_to", "patterns"]
        for intent, rule in V7_ROUTING_RULES.items():
            for field in required_fields:
                assert field in rule, f"Missing {field} in {intent} rule"

    def test_priority_values(self):
        """우선순위 값 범위 확인"""
        for intent, rule in V7_ROUTING_RULES.items():
            priority = rule["priority"]
            assert 0 <= priority <= 100, f"Invalid priority {priority} for {intent}"

    def test_route_to_valid_target(self):
        """route_to가 유효한 RouteTarget인지 확인"""
        valid_targets = [t.value for t in RouteTarget]
        for intent, rule in V7_ROUTING_RULES.items():
            route_to = rule["route_to"]
            assert route_to in valid_targets, f"Invalid route_to {route_to} for {intent}"


class TestV7ToLegacy:
    """V7 Intent → Legacy Intent 변환 테스트"""

    def test_check_to_judgment(self):
        """CHECK → judgment"""
        assert v7_to_legacy("CHECK") == "judgment"

    def test_trend_to_judgment(self):
        """TREND → judgment"""
        assert v7_to_legacy("TREND") == "judgment"

    def test_compare_to_judgment(self):
        """COMPARE → judgment"""
        assert v7_to_legacy("COMPARE") == "judgment"

    def test_rank_to_bi(self):
        """RANK → bi"""
        assert v7_to_legacy("RANK") == "bi"

    def test_find_cause_to_judgment(self):
        """FIND_CAUSE → judgment"""
        assert v7_to_legacy("FIND_CAUSE") == "judgment"

    def test_detect_anomaly_to_learning(self):
        """DETECT_ANOMALY → learning"""
        assert v7_to_legacy("DETECT_ANOMALY") == "learning"

    def test_predict_to_judgment(self):
        """PREDICT → judgment"""
        assert v7_to_legacy("PREDICT") == "judgment"

    def test_what_if_to_judgment(self):
        """WHAT_IF → judgment"""
        assert v7_to_legacy("WHAT_IF") == "judgment"

    def test_report_to_bi(self):
        """REPORT → bi"""
        assert v7_to_legacy("REPORT") == "bi"

    def test_notify_to_workflow(self):
        """NOTIFY → workflow"""
        assert v7_to_legacy("NOTIFY") == "workflow"

    def test_continue_to_general(self):
        """CONTINUE → general"""
        assert v7_to_legacy("CONTINUE") == "general"

    def test_clarify_to_general(self):
        """CLARIFY → general"""
        assert v7_to_legacy("CLARIFY") == "general"

    def test_stop_to_general(self):
        """STOP → general"""
        assert v7_to_legacy("STOP") == "general"

    def test_system_to_general(self):
        """SYSTEM → general"""
        assert v7_to_legacy("SYSTEM") == "general"

    def test_unknown_to_general(self):
        """알 수 없는 Intent → general"""
        assert v7_to_legacy("UNKNOWN_INTENT") == "general"


class TestV7IntentClassifier:
    """V7IntentClassifier 테스트"""

    @pytest.fixture
    def classifier(self):
        return V7IntentClassifier()

    # === 정보 조회 (Information) ===

    def test_check_patterns(self, classifier):
        """CHECK Intent 패턴 테스트"""
        test_cases = [
            "오늘 생산량 얼마야?",
            "현재 온도 확인",
            "불량률 어때?",
            "A라인 상태 어때?",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "CHECK", f"Expected CHECK for: {text}, got {result.v7_intent}"
            assert result.route_to == "DATA_LAYER"

    def test_trend_patterns(self, classifier):
        """TREND Intent 패턴 테스트"""
        test_cases = [
            "이번 주 불량률 추이 보여줘",
            "월별 생산량 변화 보여줘",
            "온도 추이 보여줘",
            "최근 품질 트렌드 보여줘",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "TREND", f"Expected TREND for: {text}, got {result.v7_intent}"
            assert result.route_to == "DATA_LAYER"

    def test_compare_patterns(self, classifier):
        """COMPARE Intent 패턴 테스트"""
        test_cases = [
            "1호기랑 2호기 비교",
            "오늘이랑 어제 차이",
            "뭐가 더 나아?",
            "A라인 B라인 비교해줘",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "COMPARE", f"Expected COMPARE for: {text}, got {result.v7_intent}"
            assert result.route_to == "JUDGMENT_ENGINE"

    def test_rank_patterns(self, classifier):
        """RANK Intent 패턴 테스트"""
        test_cases = [
            "제일 문제인 설비 뭐야",
            "불량 많은 순서 알려줘",
            "생산량 top 5 보여줘",
            "가장 좋은 라인 어디야",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "RANK", f"Expected RANK for: {text}, got {result.v7_intent}"
            assert result.route_to == "JUDGMENT_ENGINE"

    # === 분석 (Analysis) ===

    def test_find_cause_patterns(self, classifier):
        """FIND_CAUSE Intent 패턴 테스트"""
        test_cases = [
            "왜 불량이 늘었어?",
            "생산량 떨어진 원인 알려줘",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "FIND_CAUSE", f"Expected FIND_CAUSE for: {text}, got {result.v7_intent}"
            assert result.route_to == "JUDGMENT_ENGINE"

    def test_detect_anomaly_patterns(self, classifier):
        """DETECT_ANOMALY Intent 패턴 테스트"""
        test_cases = [
            "뭔가 이상한 거 없어?",
            "경고 뜬 설비 있어?",
            "이상 징후 있어?",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "DETECT_ANOMALY", f"Expected DETECT_ANOMALY for: {text}, got {result.v7_intent}"
            assert result.route_to == "RULE_ENGINE"

    def test_predict_patterns(self, classifier):
        """PREDICT Intent 패턴 테스트"""
        test_cases = [
            "납기 맞출 수 있어?",
            "오늘 목표 달성 가능해?",
            "내일 생산량 예측",
            "앞으로 어떻게 될까?",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "PREDICT", f"Expected PREDICT for: {text}, got {result.v7_intent}"
            assert result.route_to == "JUDGMENT_ENGINE"

    def test_what_if_patterns(self, classifier):
        """WHAT_IF Intent 패턴 테스트"""
        test_cases = [
            "1호기 멈추면 어떻게 돼?",
            "생산량 10% 늘리면 어떻게 돼?",
            "만약 온도 올리면 어떻게 돼?",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "WHAT_IF", f"Expected WHAT_IF for: {text}, got {result.v7_intent}"
            assert result.route_to == "JUDGMENT_ENGINE"

    # === 액션 (Action) ===

    def test_report_patterns(self, classifier):
        """REPORT Intent 패턴 테스트"""
        test_cases = [
            "일일 리포트 만들어줘",
            "불량률 그래프 보여줘",
            "차트로 보여줘",
            "대시보드 보여줘",
            "시각화해줘",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "REPORT", f"Expected REPORT for: {text}, got {result.v7_intent}"
            assert result.route_to == "BI_GUIDE"

    def test_notify_patterns(self, classifier):
        """NOTIFY Intent 패턴 테스트"""
        test_cases = [
            "온도 60도 넘으면 알려줘",
            "워크플로우 만들어줘",
            "슬랙으로 알림 보내줘",
            "자동화 알림 설정해줘",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "NOTIFY", f"Expected NOTIFY for: {text}, got {result.v7_intent}"
            assert result.route_to == "WORKFLOW_GUIDE"

    # === 대화 제어 (Conversation) ===

    def test_continue_patterns(self, classifier):
        """CONTINUE Intent 패턴 테스트"""
        test_cases = [
            "응",
            "더 자세히",
            "그래",
            "yes",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "CONTINUE", f"Expected CONTINUE for: {text}, got {result.v7_intent}"
            assert result.route_to == "CONTEXT_DEPENDENT"

    def test_stop_patterns(self, classifier):
        """STOP Intent 패턴 테스트"""
        test_cases = [
            "그만",
            "취소해",
            "중단",
            "됐어",
            "멈춰",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "STOP", f"Expected STOP for: {text}, got {result.v7_intent}"
            assert result.route_to == "CONTEXT_DEPENDENT"

    def test_system_patterns(self, classifier):
        """SYSTEM Intent 패턴 테스트"""
        test_cases = [
            "안녕하세요",
            "도움말 보여줘",
            "기능 뭐 있어?",
        ]
        for text in test_cases:
            result = classifier.classify(text)
            assert result is not None, f"No match for: {text}"
            assert result.v7_intent == "SYSTEM", f"Expected SYSTEM for: {text}, got {result.v7_intent}"
            assert result.route_to == "DIRECT_RESPONSE"

    # === 분류 기능 테스트 ===

    def test_no_match_returns_none(self, classifier):
        """매칭되지 않는 텍스트는 None 반환"""
        result = classifier.classify("asdfghjkl12345")
        assert result is None

    def test_empty_text_returns_none(self, classifier):
        """빈 텍스트는 None 반환"""
        assert classifier.classify("") is None
        assert classifier.classify("   ") is None

    def test_classification_result_fields(self, classifier):
        """ClassificationResult 필드 확인"""
        result = classifier.classify("오늘 생산량 얼마야?")
        assert result is not None
        assert result.v7_intent == "CHECK"
        assert result.route_to == "DATA_LAYER"
        assert result.confidence > 0.9
        assert result.source == "rule_engine"
        assert result.legacy_intent == "judgment"
        assert result.matched_pattern is not None

    def test_priority_based_selection(self, classifier):
        """우선순위 기반 Intent 선택"""
        # "리포트 만들어줘" - REPORT (priority 100) vs other
        result = classifier.classify("일일 리포트 만들어줘")
        assert result is not None
        assert result.v7_intent == "REPORT"  # 가장 높은 우선순위

    def test_keyword_fallback(self, classifier):
        """키워드 기반 분류 폴백"""
        # 패턴 매칭 실패 시 키워드 매칭 시도
        result = classifier.classify_with_keywords("예측 좀 해봐")
        if result:
            assert result.source == "keyword_match"
            assert result.confidence < 0.9  # 낮은 신뢰도


class TestClarifyDetection:
    """명확화 필요 여부 감지 테스트"""

    @pytest.fixture
    def classifier(self):
        return V7IntentClassifier()

    def test_short_text_needs_clarify(self, classifier):
        """짧은 텍스트는 명확화 필요"""
        question = classifier.should_clarify("ㅇ")
        assert question is not None

    def test_ambiguous_text_needs_clarify(self, classifier):
        """모호한 텍스트는 명확화 필요"""
        ambiguous_texts = ["확인", "어떻게?"]
        for text in ambiguous_texts:
            question = classifier.should_clarify(text)
            assert question is not None, f"Should need clarify for: {text}"

    def test_clear_text_no_clarify(self, classifier):
        """명확한 텍스트는 명확화 불필요"""
        question = classifier.should_clarify("오늘 생산량 얼마야?")
        assert question is None


class TestMetaRouterAgent:
    """MetaRouterAgent V7 기능 테스트"""

    @pytest.fixture
    def router(self):
        return MetaRouterAgent()

    def test_route_target_to_agent_mapping(self, router):
        """Route Target → Agent 매핑"""
        mappings = {
            "DATA_LAYER": "judgment",
            "JUDGMENT_ENGINE": "judgment",
            "RULE_ENGINE": "learning",
            "BI_GUIDE": "bi",
            "WORKFLOW_GUIDE": "workflow",
            "CONTEXT_DEPENDENT": "general",
            "ASK_BACK": "general",
            "DIRECT_RESPONSE": "general",
        }
        for route_to, expected_agent in mappings.items():
            actual = router.route_target_to_agent(route_to)
            assert actual == expected_agent, f"Expected {expected_agent} for {route_to}, got {actual}"

    def test_route_with_hybrid_rule_based(self, router):
        """하이브리드 라우팅 - 규칙 기반"""
        result = router.route_with_hybrid("오늘 생산량 얼마야?")

        assert result["v7_intent"] == "CHECK"
        assert result["route_to"] == "DATA_LAYER"
        assert result["legacy_intent"] == "judgment"
        assert result["target_agent"] == "judgment"
        assert result["context"]["classification_source"] == "v7_rule_engine"

    def test_route_with_hybrid_clarify(self, router):
        """하이브리드 라우팅 - 명확화 필요"""
        # "뭐?" 같은 짧고 모호한 텍스트 (rule-based CLARIFY)
        result = router.route_with_hybrid("뭐?")

        assert result["v7_intent"] == "CLARIFY"
        assert result["route_to"] == "ASK_BACK"
        # Note: rule-based CLARIFY doesn't generate ask_back question
        # ask_back is only set when should_clarify() is triggered via specific ambiguous patterns
        assert result["legacy_intent"] == "general"

    def test_classify_v7_intent_tool(self, router):
        """classify_v7_intent 툴 정의 확인"""
        tools = router.get_tools()
        v7_tool = next(
            (t for t in tools if t["name"] == "classify_v7_intent"),
            None
        )
        assert v7_tool is not None
        assert "v7_intent" in v7_tool["input_schema"]["properties"]
        assert "route_to" in v7_tool["input_schema"]["properties"]


class TestLegacyCompatibility:
    """Legacy Intent 호환성 테스트"""

    def test_legacy_routing_rules_exist(self):
        """Legacy 라우팅 규칙 존재 확인"""
        assert LEGACY_ROUTING_RULES is not None
        assert len(LEGACY_ROUTING_RULES) > 0

    def test_intent_classifier_inheritance(self):
        """IntentClassifier가 V7IntentClassifier 상속"""
        classifier = IntentClassifier()
        assert isinstance(classifier, V7IntentClassifier)

    def test_classification_result_intent_property(self):
        """ClassificationResult.intent 속성 (Legacy)"""
        result = ClassificationResult(
            v7_intent="CHECK",
            route_to="DATA_LAYER",
            confidence=0.95,
            source="rule_engine",
            legacy_intent="judgment",
        )
        assert result.intent == "judgment"

    def test_get_all_v7_intents(self):
        """get_all_v7_intents 헬퍼 함수"""
        intents = get_all_v7_intents()
        assert len(intents) == 14
        assert "CHECK" in intents
        assert "NOTIFY" in intents


class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def classifier(self):
        return V7IntentClassifier()

    def test_mixed_language(self, classifier):
        """한영 혼용 텍스트"""
        result = classifier.classify("production 현황 check해줘")
        # 패턴에 따라 매칭될 수 있음
        # 결과가 있으면 유효한 V7 Intent인지 확인
        if result:
            assert result.v7_intent in [i.value for i in V7Intent]

    def test_multiple_intents_in_text(self, classifier):
        """여러 Intent가 포함된 텍스트"""
        # "생산량 확인하고 리포트 만들어줘" - CHECK와 REPORT 둘 다 포함
        result = classifier.classify("생산량 확인하고 리포트 만들어줘")
        assert result is not None
        # 우선순위에 따라 하나가 선택됨 (REPORT: 100 > CHECK: 50)
        assert result.v7_intent == "REPORT"

    def test_special_characters(self, classifier):
        """특수문자 포함 텍스트"""
        result = classifier.classify("생산량 어때?!?!")
        if result:
            assert result.v7_intent in [i.value for i in V7Intent]

    def test_unicode_text(self, classifier):
        """유니코드 텍스트"""
        result = classifier.classify("온도 체크해주세요 😀")
        if result:
            assert result.v7_intent in [i.value for i in V7Intent]


class TestClassificationDebug:
    """분류 디버그 정보 테스트"""

    @pytest.fixture
    def classifier(self):
        return V7IntentClassifier()

    def test_debug_info_structure(self, classifier):
        """디버그 정보 구조 확인"""
        debug = classifier.get_classification_debug("오늘 생산량 얼마야?")

        assert "input" in debug
        assert "pattern_result" in debug
        assert "keyword_result" in debug
        assert "clarify_question" in debug
        assert "final_v7_intent" in debug

    def test_debug_pattern_result(self, classifier):
        """패턴 매칭 결과 디버그"""
        debug = classifier.get_classification_debug("오늘 생산량 얼마야?")

        pattern_result = debug["pattern_result"]
        assert pattern_result is not None
        assert pattern_result["v7_intent"] == "CHECK"
        assert pattern_result["route_to"] == "DATA_LAYER"
        assert pattern_result["confidence"] > 0.9

    def test_debug_no_match(self, classifier):
        """매칭 없는 경우 디버그"""
        debug = classifier.get_classification_debug("asdfghjkl")

        assert debug["pattern_result"] is None
        assert debug["final_v7_intent"] in ["llm_required", "CLARIFY"]
