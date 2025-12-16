# ===================================================
# TriFlow AI - Hybrid Intent Classifier (V7)
# V7 Intent 체계 기반 하이브리드 분류기
# ===================================================
"""
하이브리드 Intent 분류기 (V7 체계)

V7 Intent 체계 (14개):
- 정보 조회: CHECK, TREND, COMPARE, RANK
- 분석: FIND_CAUSE, DETECT_ANOMALY, PREDICT, WHAT_IF
- 액션: REPORT, NOTIFY
- 대화 제어: CONTINUE, CLARIFY, STOP, SYSTEM

1차: 규칙 기반 분류 (정규식 패턴 매칭)
   - 명확한 패턴은 빠르고 정확하게 분류
   - 우선순위 기반으로 충돌 해결

2차: LLM 분류 (MetaRouterAgent)
   - 규칙으로 분류되지 않은 애매한 경우
   - 문맥 이해가 필요한 복잡한 요청
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .routing_rules import (
    V7_ROUTING_RULES,
    LEGACY_ROUTING_RULES,
    get_sorted_v7_rules,
    v7_to_legacy,
)

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """분류 결과 (V7 체계)"""
    # V7 Intent (기본)
    v7_intent: str
    route_to: str
    confidence: float
    source: str  # "rule_engine", "keyword_match", "llm"

    # Legacy Intent (하위호환)
    legacy_intent: str = ""

    # 매칭 정보
    matched_pattern: Optional[str] = None
    matched_keyword: Optional[str] = None
    all_matches: Optional[List[Dict]] = None

    # Slot 정보 (선택)
    slots: Dict[str, Any] = field(default_factory=dict)

    # 명확화 필요 시
    ask_back: Optional[str] = None

    @property
    def intent(self) -> str:
        """Legacy 호환: intent 속성 (v7_intent 반환)"""
        return self.legacy_intent or v7_to_legacy(self.v7_intent)


class V7IntentClassifier:
    """
    V7 Intent 분류기

    사용법:
        classifier = V7IntentClassifier()
        result = classifier.classify("오늘 생산량 얼마야?")

        if result:
            print(f"V7 Intent: {result.v7_intent}, Route: {result.route_to}")
        else:
            # LLM으로 분류 필요
            pass
    """

    def __init__(self):
        self.v7_rules = V7_ROUTING_RULES
        self.legacy_rules = LEGACY_ROUTING_RULES
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """정규식 패턴 사전 컴파일 (V7 규칙)"""
        for intent, rule in self.v7_rules.items():
            patterns = rule.get("patterns", [])
            self._compiled_patterns[intent] = [
                re.compile(pattern, re.IGNORECASE | re.UNICODE)
                for pattern in patterns
            ]
        logger.info(f"Compiled V7 patterns for {len(self._compiled_patterns)} intents")

    def classify(self, text: str) -> Optional[ClassificationResult]:
        """
        텍스트를 V7 Intent로 분류

        Args:
            text: 사용자 입력 텍스트

        Returns:
            ClassificationResult: 분류 결과 (규칙 매칭 시)
            None: 규칙으로 분류 불가 (LLM 필요)
        """
        if not text or not text.strip():
            return None

        text = text.strip()
        all_matches: List[Dict[str, Any]] = []

        # 모든 V7 Intent에 대해 패턴 매칭 시도
        for intent, compiled_patterns in self._compiled_patterns.items():
            rule = self.v7_rules[intent]
            priority = rule.get("priority", 0)

            for pattern in compiled_patterns:
                match = pattern.search(text)
                if match:
                    all_matches.append({
                        "intent": intent,
                        "priority": priority,
                        "pattern": pattern.pattern,
                        "matched_text": match.group(),
                        "route_to": rule.get("route_to"),
                    })

        if not all_matches:
            logger.debug(f"No V7 rule match for: '{text[:50]}...'")
            return None

        # 우선순위가 가장 높은 매칭 선택
        best_match = max(all_matches, key=lambda x: x["priority"])

        # 동일 우선순위에서 여러 매칭이 있는 경우 로그
        same_priority_matches = [
            m for m in all_matches
            if m["priority"] == best_match["priority"]
        ]
        if len(same_priority_matches) > 1:
            logger.info(
                f"Multiple V7 matches with same priority {best_match['priority']}: "
                f"{[m['intent'] for m in same_priority_matches]}"
            )

        v7_intent = best_match["intent"]
        route_to = best_match["route_to"]
        legacy_intent = v7_to_legacy(v7_intent)

        result = ClassificationResult(
            v7_intent=v7_intent,
            route_to=route_to,
            confidence=0.95,  # 규칙 기반은 높은 신뢰도
            source="rule_engine",
            legacy_intent=legacy_intent,
            matched_pattern=best_match["pattern"],
            all_matches=all_matches,
        )

        logger.info(
            f"V7 Rule classification: '{text[:30]}...' → {v7_intent} "
            f"(route: {route_to}, pattern: {best_match['pattern'][:40]}...)"
        )

        return result

    def classify_with_keywords(self, text: str) -> Optional[ClassificationResult]:
        """
        키워드 기반 분류 (패턴 매칭 실패 시 보조)

        Args:
            text: 사용자 입력 텍스트

        Returns:
            ClassificationResult or None
        """
        text_lower = text.lower()

        for intent, rule in get_sorted_v7_rules():
            keywords = rule.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    route_to = rule.get("route_to", "DIRECT_RESPONSE")
                    legacy_intent = v7_to_legacy(intent)

                    return ClassificationResult(
                        v7_intent=intent,
                        route_to=route_to,
                        confidence=0.7,  # 키워드 매칭은 낮은 신뢰도
                        source="keyword_match",
                        legacy_intent=legacy_intent,
                        matched_keyword=keyword,
                    )

        return None

    def should_clarify(self, text: str, confidence: float = 0.7) -> Optional[str]:
        """
        명확화가 필요한지 확인

        Args:
            text: 사용자 입력 텍스트
            confidence: 신뢰도 임계값

        Returns:
            명확화 질문 (필요 시) or None
        """
        # 짧은 발화
        if len(text.strip()) <= 3:
            return "무엇을 도와드릴까요? 생산, 품질, 설비 중 어느 것이 궁금하신가요?"

        # 모호한 단어
        ambiguous_patterns = [
            (r"^(확인|체크|봐줘)$", "무엇을 확인해 드릴까요?"),
            (r"^(어떻게|어떡해)\??$", "어떤 작업을 도와드릴까요?"),
            (r"^(괜찮아|됐어)\??$", "현재 상태를 확인해 드릴까요, 아니면 다른 작업이 필요하신가요?"),
        ]

        for pattern, question in ambiguous_patterns:
            if re.match(pattern, text.strip(), re.IGNORECASE):
                return question

        return None

    def get_classification_debug(self, text: str) -> Dict[str, Any]:
        """
        분류 디버그 정보 반환 (개발/테스트용)

        Args:
            text: 사용자 입력 텍스트

        Returns:
            디버그 정보 딕셔너리
        """
        result = self.classify(text)
        keyword_result = self.classify_with_keywords(text)
        clarify_question = self.should_clarify(text)

        return {
            "input": text,
            "pattern_result": {
                "v7_intent": result.v7_intent if result else None,
                "route_to": result.route_to if result else None,
                "legacy_intent": result.legacy_intent if result else None,
                "confidence": result.confidence if result else 0,
                "matched_pattern": result.matched_pattern if result else None,
                "all_matches": result.all_matches if result else [],
            } if result else None,
            "keyword_result": {
                "v7_intent": keyword_result.v7_intent if keyword_result else None,
                "route_to": keyword_result.route_to if keyword_result else None,
                "confidence": keyword_result.confidence if keyword_result else 0,
                "matched_keyword": keyword_result.matched_keyword if keyword_result else None,
            } if keyword_result else None,
            "clarify_question": clarify_question,
            "final_v7_intent": result.v7_intent if result else (
                keyword_result.v7_intent if keyword_result else (
                    "CLARIFY" if clarify_question else "llm_required"
                )
            ),
        }

    def test_patterns(self, test_cases: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        테스트 케이스 일괄 실행

        Args:
            test_cases: [{"input": "...", "expected": "CHECK"}, ...]

        Returns:
            테스트 결과 목록
        """
        results = []
        for case in test_cases:
            text = case.get("input", "")
            expected = case.get("expected", "")

            result = self.classify(text)
            actual = result.v7_intent if result else "llm_required"

            results.append({
                "input": text,
                "expected": expected,
                "actual": actual,
                "passed": actual.upper() == expected.upper(),
                "matched_pattern": result.matched_pattern if result else None,
                "route_to": result.route_to if result else None,
            })

        passed = sum(1 for r in results if r["passed"])
        logger.info(f"V7 Test results: {passed}/{len(results)} passed")

        return results


# =========================================
# Legacy 호환 IntentClassifier
# =========================================
class IntentClassifier(V7IntentClassifier):
    """
    Legacy 호환 Intent 분류기

    V7IntentClassifier를 상속하여 기존 API 유지
    """

    def __init__(self):
        super().__init__()
        # Legacy 규칙도 컴파일 (하위호환)
        self.rules = LEGACY_ROUTING_RULES
        self._legacy_compiled_patterns: Dict[str, List[re.Pattern]] = {}

    @property
    def compiled_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Legacy 호환: compiled_patterns 속성"""
        return self._compiled_patterns


# 싱글톤 인스턴스
intent_classifier = IntentClassifier()
v7_intent_classifier = V7IntentClassifier()


# =========================================
# 테스트 함수
# =========================================
def run_v7_classifier_tests():
    """V7 분류기 테스트 실행"""
    test_cases = [
        # 정보 조회 (Information)
        {"input": "오늘 생산량 얼마야?", "expected": "CHECK"},
        {"input": "불량률 어때?", "expected": "CHECK"},
        {"input": "현재 온도 확인", "expected": "CHECK"},
        {"input": "A라인 상태 어때?", "expected": "CHECK"},

        {"input": "이번 주 불량률 추이", "expected": "TREND"},
        {"input": "월별 생산량 변화", "expected": "TREND"},
        {"input": "온도 추이 보여줘", "expected": "TREND"},

        {"input": "1호기랑 2호기 비교", "expected": "COMPARE"},
        {"input": "오늘이랑 어제 차이", "expected": "COMPARE"},
        {"input": "뭐가 더 나아?", "expected": "COMPARE"},

        {"input": "제일 문제인 설비", "expected": "RANK"},
        {"input": "불량 많은 순서대로", "expected": "RANK"},
        {"input": "생산량 top 5", "expected": "RANK"},

        # 분석 (Analysis)
        {"input": "왜 불량이 늘었어?", "expected": "FIND_CAUSE"},
        {"input": "생산량 떨어진 원인", "expected": "FIND_CAUSE"},

        {"input": "뭔가 이상한 거 없어?", "expected": "DETECT_ANOMALY"},
        {"input": "경고 뜬 설비 있어?", "expected": "DETECT_ANOMALY"},

        {"input": "납기 맞출 수 있어?", "expected": "PREDICT"},
        {"input": "오늘 목표 달성 가능해?", "expected": "PREDICT"},

        {"input": "1호기 멈추면 어떻게 돼?", "expected": "WHAT_IF"},
        {"input": "생산량 10% 늘리면?", "expected": "WHAT_IF"},

        # 액션 (Action)
        {"input": "일일 리포트 만들어줘", "expected": "REPORT"},
        {"input": "불량률 그래프 보여줘", "expected": "REPORT"},
        {"input": "차트로 보여줘", "expected": "REPORT"},

        {"input": "온도 60도 넘으면 알려줘", "expected": "NOTIFY"},
        {"input": "워크플로우 만들어줘", "expected": "NOTIFY"},
        {"input": "슬랙으로 알림 보내줘", "expected": "NOTIFY"},

        # 대화 제어 (Conversation)
        {"input": "응", "expected": "CONTINUE"},
        {"input": "더 자세히", "expected": "CONTINUE"},

        {"input": "그만", "expected": "STOP"},
        {"input": "취소해", "expected": "STOP"},

        {"input": "안녕", "expected": "SYSTEM"},
        {"input": "뭘 할 수 있어?", "expected": "SYSTEM"},
        {"input": "도움말", "expected": "SYSTEM"},
    ]

    classifier = V7IntentClassifier()
    results = classifier.test_patterns(test_cases)

    print("\n=== V7 Intent Classifier Test Results ===")
    for r in results:
        status = "✅" if r["passed"] else "❌"
        route = r.get("route_to", "N/A")
        print(f"{status} '{r['input'][:30]}...' → {r['actual']} (expected: {r['expected']}) [route: {route}]")

    passed = sum(1 for r in results if r["passed"])
    print(f"\nTotal: {passed}/{len(results)} passed")

    return results


# Legacy 테스트 함수 (하위호환)
def run_classifier_tests():
    """분류기 테스트 실행 (Legacy)"""
    return run_v7_classifier_tests()


if __name__ == "__main__":
    run_v7_classifier_tests()
