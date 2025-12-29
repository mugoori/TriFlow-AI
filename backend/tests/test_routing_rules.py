"""
Intent Routing Rules 테스트
app/agents/routing_rules.py 테스트
"""
import pytest


# ========== Enum 테스트 ==========


class TestV7IntentEnum:
    """V7Intent 열거형 테스트"""

    def test_v7_intent_values(self):
        """V7Intent 값들 확인"""
        from app.agents.routing_rules import V7Intent

        # 정보 조회
        assert V7Intent.CHECK.value == "CHECK"
        assert V7Intent.TREND.value == "TREND"
        assert V7Intent.COMPARE.value == "COMPARE"
        assert V7Intent.RANK.value == "RANK"

        # 분석
        assert V7Intent.FIND_CAUSE.value == "FIND_CAUSE"
        assert V7Intent.DETECT_ANOMALY.value == "DETECT_ANOMALY"
        assert V7Intent.PREDICT.value == "PREDICT"
        assert V7Intent.WHAT_IF.value == "WHAT_IF"

        # 액션
        assert V7Intent.REPORT.value == "REPORT"
        assert V7Intent.NOTIFY.value == "NOTIFY"

        # 대화 제어
        assert V7Intent.CONTINUE.value == "CONTINUE"
        assert V7Intent.CLARIFY.value == "CLARIFY"
        assert V7Intent.STOP.value == "STOP"
        assert V7Intent.SYSTEM.value == "SYSTEM"

    def test_v7_intent_count(self):
        """V7Intent 개수 확인 (14개)"""
        from app.agents.routing_rules import V7Intent

        assert len(V7Intent) == 14


class TestRouteTargetEnum:
    """RouteTarget 열거형 테스트"""

    def test_route_target_values(self):
        """RouteTarget 값들 확인"""
        from app.agents.routing_rules import RouteTarget

        assert RouteTarget.DATA_LAYER.value == "DATA_LAYER"
        assert RouteTarget.JUDGMENT_ENGINE.value == "JUDGMENT_ENGINE"
        assert RouteTarget.RULE_ENGINE.value == "RULE_ENGINE"
        assert RouteTarget.BI_GUIDE.value == "BI_GUIDE"
        assert RouteTarget.WORKFLOW_GUIDE.value == "WORKFLOW_GUIDE"
        assert RouteTarget.CONTEXT_DEPENDENT.value == "CONTEXT_DEPENDENT"
        assert RouteTarget.ASK_BACK.value == "ASK_BACK"
        assert RouteTarget.DIRECT_RESPONSE.value == "DIRECT_RESPONSE"


# ========== 매핑 테스트 ==========


class TestIntentMappings:
    """Intent 매핑 테스트"""

    def test_v7_intent_to_route(self):
        """V7 Intent → Route Target 매핑"""
        from app.agents.routing_rules import V7_INTENT_TO_ROUTE, V7Intent, RouteTarget

        assert V7_INTENT_TO_ROUTE[V7Intent.CHECK] == RouteTarget.DATA_LAYER
        assert V7_INTENT_TO_ROUTE[V7Intent.TREND] == RouteTarget.DATA_LAYER
        assert V7_INTENT_TO_ROUTE[V7Intent.COMPARE] == RouteTarget.JUDGMENT_ENGINE
        assert V7_INTENT_TO_ROUTE[V7Intent.REPORT] == RouteTarget.BI_GUIDE
        assert V7_INTENT_TO_ROUTE[V7Intent.NOTIFY] == RouteTarget.WORKFLOW_GUIDE
        assert V7_INTENT_TO_ROUTE[V7Intent.DETECT_ANOMALY] == RouteTarget.RULE_ENGINE

    def test_v7_to_legacy_intent(self):
        """V7 Intent → Legacy Intent 매핑"""
        from app.agents.routing_rules import V7_TO_LEGACY_INTENT, V7Intent

        assert V7_TO_LEGACY_INTENT[V7Intent.CHECK] == "judgment"
        assert V7_TO_LEGACY_INTENT[V7Intent.REPORT] == "bi"
        assert V7_TO_LEGACY_INTENT[V7Intent.NOTIFY] == "workflow"
        assert V7_TO_LEGACY_INTENT[V7Intent.DETECT_ANOMALY] == "learning"
        assert V7_TO_LEGACY_INTENT[V7Intent.SYSTEM] == "general"


# ========== 상수 테스트 ==========


class TestConstants:
    """상수 테스트"""

    def test_legacy_intent_types(self):
        """Legacy Intent 타입"""
        from app.agents.routing_rules import LEGACY_INTENT_TYPES

        expected = ["judgment", "bi", "workflow", "learning", "general"]
        assert LEGACY_INTENT_TYPES == expected

    def test_v7_routing_rules_exist(self):
        """V7 라우팅 규칙 존재"""
        from app.agents.routing_rules import V7_ROUTING_RULES

        assert len(V7_ROUTING_RULES) == 14

    def test_v7_routing_rules_structure(self):
        """V7 라우팅 규칙 구조"""
        from app.agents.routing_rules import V7_ROUTING_RULES

        for intent, rule in V7_ROUTING_RULES.items():
            assert "priority" in rule
            assert "route_to" in rule
            assert "description" in rule
            assert "patterns" in rule
            assert isinstance(rule["patterns"], list)

    def test_legacy_routing_rules_exist(self):
        """Legacy 라우팅 규칙 존재"""
        from app.agents.routing_rules import LEGACY_ROUTING_RULES

        assert len(LEGACY_ROUTING_RULES) == 5


# ========== 유틸리티 함수 테스트 ==========


class TestUtilityFunctions:
    """유틸리티 함수 테스트"""

    def test_get_v7_rule(self):
        """get_v7_rule 함수"""
        from app.agents.routing_rules import get_v7_rule

        rule = get_v7_rule("CHECK")
        assert rule["route_to"] == "DATA_LAYER"
        assert rule["priority"] == 50

    def test_get_v7_rule_case_insensitive(self):
        """get_v7_rule 대소문자 무관"""
        from app.agents.routing_rules import get_v7_rule

        rule_upper = get_v7_rule("CHECK")
        rule_lower = get_v7_rule("check")

        assert rule_upper == rule_lower

    def test_get_v7_rule_unknown(self):
        """get_v7_rule 알 수 없는 Intent"""
        from app.agents.routing_rules import get_v7_rule

        rule = get_v7_rule("UNKNOWN")
        assert rule == {}

    def test_get_legacy_rule(self):
        """get_legacy_rule 함수"""
        from app.agents.routing_rules import get_legacy_rule

        rule = get_legacy_rule("bi")
        assert rule["priority"] == 100
        assert "REPORT" in rule["v7_mapping"]

    def test_get_legacy_rule_case_insensitive(self):
        """get_legacy_rule 대소문자 무관"""
        from app.agents.routing_rules import get_legacy_rule

        rule_upper = get_legacy_rule("BI")
        rule_lower = get_legacy_rule("bi")

        assert rule_upper == rule_lower

    def test_get_legacy_rule_unknown(self):
        """get_legacy_rule 알 수 없는 Intent"""
        from app.agents.routing_rules import get_legacy_rule

        rule = get_legacy_rule("unknown")
        assert rule == {}

    def test_get_all_v7_intents(self):
        """get_all_v7_intents 함수"""
        from app.agents.routing_rules import get_all_v7_intents

        intents = get_all_v7_intents()
        assert len(intents) == 14
        assert "CHECK" in intents
        assert "REPORT" in intents

    def test_get_all_legacy_intents(self):
        """get_all_legacy_intents 함수"""
        from app.agents.routing_rules import get_all_legacy_intents

        intents = get_all_legacy_intents()
        assert len(intents) == 5
        assert "judgment" in intents
        assert "bi" in intents

    def test_get_sorted_v7_rules(self):
        """get_sorted_v7_rules 함수"""
        from app.agents.routing_rules import get_sorted_v7_rules

        sorted_rules = get_sorted_v7_rules()
        assert len(sorted_rules) == 14

        # 첫 번째가 가장 높은 우선순위
        priorities = [rule[1]["priority"] for rule in sorted_rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_v7_to_legacy(self):
        """v7_to_legacy 함수"""
        from app.agents.routing_rules import v7_to_legacy

        assert v7_to_legacy("CHECK") == "judgment"
        assert v7_to_legacy("REPORT") == "bi"
        assert v7_to_legacy("NOTIFY") == "workflow"
        assert v7_to_legacy("DETECT_ANOMALY") == "learning"
        assert v7_to_legacy("SYSTEM") == "general"

    def test_v7_to_legacy_case_insensitive(self):
        """v7_to_legacy 대소문자 무관"""
        from app.agents.routing_rules import v7_to_legacy

        assert v7_to_legacy("check") == "judgment"
        assert v7_to_legacy("Check") == "judgment"
        assert v7_to_legacy("CHECK") == "judgment"

    def test_v7_to_legacy_unknown(self):
        """v7_to_legacy 알 수 없는 Intent"""
        from app.agents.routing_rules import v7_to_legacy

        assert v7_to_legacy("UNKNOWN") == "general"

    def test_v7_to_route_target(self):
        """v7_to_route_target 함수"""
        from app.agents.routing_rules import v7_to_route_target

        assert v7_to_route_target("CHECK") == "DATA_LAYER"
        assert v7_to_route_target("REPORT") == "BI_GUIDE"
        assert v7_to_route_target("NOTIFY") == "WORKFLOW_GUIDE"

    def test_v7_to_route_target_case_insensitive(self):
        """v7_to_route_target 대소문자 무관"""
        from app.agents.routing_rules import v7_to_route_target

        assert v7_to_route_target("check") == "DATA_LAYER"
        assert v7_to_route_target("Check") == "DATA_LAYER"

    def test_v7_to_route_target_unknown(self):
        """v7_to_route_target 알 수 없는 Intent"""
        from app.agents.routing_rules import v7_to_route_target

        assert v7_to_route_target("UNKNOWN") == "DIRECT_RESPONSE"

    def test_get_route_target(self):
        """get_route_target 함수"""
        from app.agents.routing_rules import get_route_target

        assert get_route_target("CHECK") == "DATA_LAYER"
        assert get_route_target("REPORT") == "BI_GUIDE"

    def test_get_route_target_unknown(self):
        """get_route_target 알 수 없는 Intent"""
        from app.agents.routing_rules import get_route_target

        assert get_route_target("UNKNOWN") is None


# ========== 하위호환 함수 테스트 ==========


class TestBackwardCompatibility:
    """하위호환 함수 테스트"""

    def test_intent_types_alias(self):
        """INTENT_TYPES 별칭"""
        from app.agents.routing_rules import INTENT_TYPES, LEGACY_INTENT_TYPES

        assert INTENT_TYPES == LEGACY_INTENT_TYPES

    def test_routing_rules_alias(self):
        """ROUTING_RULES 별칭"""
        from app.agents.routing_rules import ROUTING_RULES, LEGACY_ROUTING_RULES

        assert ROUTING_RULES == LEGACY_ROUTING_RULES

    def test_get_rule_v7(self):
        """get_rule - V7 Intent"""
        from app.agents.routing_rules import get_rule

        rule = get_rule("CHECK")
        assert rule["route_to"] == "DATA_LAYER"

    def test_get_rule_legacy(self):
        """get_rule - Legacy Intent"""
        from app.agents.routing_rules import get_rule

        rule = get_rule("bi")
        assert rule["priority"] == 100

    def test_get_rule_unknown(self):
        """get_rule - 알 수 없는 Intent"""
        from app.agents.routing_rules import get_rule

        rule = get_rule("unknown_intent")
        assert rule == {}

    def test_get_all_intents(self):
        """get_all_intents 함수"""
        from app.agents.routing_rules import get_all_intents

        intents = get_all_intents()
        assert len(intents) == 5

    def test_get_sorted_rules(self):
        """get_sorted_rules 함수"""
        from app.agents.routing_rules import get_sorted_rules

        sorted_rules = get_sorted_rules()
        assert len(sorted_rules) == 5

        # 우선순위 내림차순
        priorities = [rule[1]["priority"] for rule in sorted_rules]
        assert priorities == sorted(priorities, reverse=True)


# ========== 규칙 구조 테스트 ==========


class TestRulesStructure:
    """규칙 구조 상세 테스트"""

    def test_check_rule_structure(self):
        """CHECK 규칙 구조"""
        from app.agents.routing_rules import V7_ROUTING_RULES

        rule = V7_ROUTING_RULES["CHECK"]
        assert rule["priority"] == 50
        assert rule["route_to"] == "DATA_LAYER"
        assert "patterns" in rule
        assert "keywords" in rule
        assert "examples" in rule
        assert "slots" in rule

    def test_report_rule_highest_priority(self):
        """REPORT 규칙 최고 우선순위"""
        from app.agents.routing_rules import V7_ROUTING_RULES

        report_priority = V7_ROUTING_RULES["REPORT"]["priority"]

        # REPORT가 가장 높은 우선순위
        for intent, rule in V7_ROUTING_RULES.items():
            if intent != "REPORT":
                assert rule["priority"] <= report_priority

    def test_system_rule_lowest_priority(self):
        """SYSTEM 규칙 최저 우선순위"""
        from app.agents.routing_rules import V7_ROUTING_RULES

        system_priority = V7_ROUTING_RULES["SYSTEM"]["priority"]

        # SYSTEM이 가장 낮은 우선순위
        for intent, rule in V7_ROUTING_RULES.items():
            if intent != "SYSTEM":
                assert rule["priority"] >= system_priority

    def test_all_rules_have_patterns(self):
        """모든 규칙에 패턴 존재"""
        from app.agents.routing_rules import V7_ROUTING_RULES

        for intent, rule in V7_ROUTING_RULES.items():
            assert len(rule["patterns"]) > 0, f"{intent} has no patterns"

    def test_clarify_rule_confidence_threshold(self):
        """CLARIFY 규칙 신뢰도 임계값"""
        from app.agents.routing_rules import V7_ROUTING_RULES

        rule = V7_ROUTING_RULES["CLARIFY"]
        assert "confidence_threshold" in rule
        assert rule["confidence_threshold"] == 0.7
