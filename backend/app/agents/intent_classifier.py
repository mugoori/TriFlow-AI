# ===================================================
# TriFlow AI - Hybrid Intent Classifier
# 하이브리드 Intent 분류기 (규칙 기반 + LLM fallback)
# ===================================================
"""
하이브리드 Intent 분류기

1차: 규칙 기반 분류 (정규식 패턴 매칭)
   - 명확한 패턴은 빠르고 정확하게 분류
   - 우선순위 기반으로 충돌 해결

2차: LLM 분류 (MetaRouterAgent)
   - 규칙으로 분류되지 않은 애매한 경우
   - 문맥 이해가 필요한 복잡한 요청
"""

import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from .routing_rules import ROUTING_RULES, get_sorted_rules

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """분류 결과"""
    intent: str
    confidence: float
    source: str  # "rule_engine" or "llm"
    matched_pattern: Optional[str] = None
    matched_keyword: Optional[str] = None
    all_matches: Optional[List[Dict]] = None


class IntentClassifier:
    """
    하이브리드 Intent 분류기

    사용법:
        classifier = IntentClassifier()
        result = classifier.classify("11월달 센서 데이터 보여줘")

        if result:
            print(f"Intent: {result.intent}, Source: {result.source}")
        else:
            # LLM으로 분류 필요
            pass
    """

    def __init__(self):
        self.rules = ROUTING_RULES
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """정규식 패턴 사전 컴파일"""
        for intent, rule in self.rules.items():
            patterns = rule.get("patterns", [])
            self._compiled_patterns[intent] = [
                re.compile(pattern, re.IGNORECASE | re.UNICODE)
                for pattern in patterns
            ]
        logger.info(f"Compiled patterns for {len(self._compiled_patterns)} intents")

    def classify(self, text: str) -> Optional[ClassificationResult]:
        """
        텍스트를 분류하여 Intent 반환

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

        # 모든 Intent에 대해 패턴 매칭 시도
        for intent, compiled_patterns in self._compiled_patterns.items():
            rule = self.rules[intent]
            priority = rule.get("priority", 0)

            for pattern in compiled_patterns:
                match = pattern.search(text)
                if match:
                    all_matches.append({
                        "intent": intent,
                        "priority": priority,
                        "pattern": pattern.pattern,
                        "matched_text": match.group(),
                    })

        if not all_matches:
            logger.debug(f"No rule match for: '{text[:50]}...'")
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
                f"Multiple matches with same priority {best_match['priority']}: "
                f"{[m['intent'] for m in same_priority_matches]}"
            )

        result = ClassificationResult(
            intent=best_match["intent"],
            confidence=0.95,  # 규칙 기반은 높은 신뢰도
            source="rule_engine",
            matched_pattern=best_match["pattern"],
            all_matches=all_matches,
        )

        logger.info(
            f"Rule-based classification: '{text[:30]}...' → {result.intent} "
            f"(pattern: {best_match['pattern'][:40]}...)"
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

        for intent, rule in get_sorted_rules():
            keywords = rule.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return ClassificationResult(
                        intent=intent,
                        confidence=0.7,  # 키워드 매칭은 낮은 신뢰도
                        source="keyword_match",
                        matched_keyword=keyword,
                    )

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

        return {
            "input": text,
            "pattern_result": {
                "intent": result.intent if result else None,
                "confidence": result.confidence if result else 0,
                "matched_pattern": result.matched_pattern if result else None,
                "all_matches": result.all_matches if result else [],
            } if result else None,
            "keyword_result": {
                "intent": keyword_result.intent if keyword_result else None,
                "confidence": keyword_result.confidence if keyword_result else 0,
                "matched_keyword": keyword_result.matched_keyword if keyword_result else None,
            } if keyword_result else None,
            "final_intent": result.intent if result else (
                keyword_result.intent if keyword_result else "llm_required"
            ),
        }

    def test_patterns(self, test_cases: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        테스트 케이스 일괄 실행

        Args:
            test_cases: [{"input": "...", "expected": "judgment"}, ...]

        Returns:
            테스트 결과 목록
        """
        results = []
        for case in test_cases:
            text = case.get("input", "")
            expected = case.get("expected", "")

            result = self.classify(text)
            actual = result.intent if result else "llm_required"

            results.append({
                "input": text,
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
                "matched_pattern": result.matched_pattern if result else None,
            })

        passed = sum(1 for r in results if r["passed"])
        logger.info(f"Test results: {passed}/{len(results)} passed")

        return results


# 싱글톤 인스턴스
intent_classifier = IntentClassifier()


# 테스트용 함수
def run_classifier_tests():
    """분류기 테스트 실행"""
    test_cases = [
        # Judgment (데이터 조회)
        {"input": "11월달 센서 데이터 보여줘", "expected": "judgment"},
        {"input": "A라인 온도 데이터 확인", "expected": "judgment"},
        {"input": "현재 공장 상태 알려줘", "expected": "judgment"},
        {"input": "지난주 압력 데이터 조회해줘", "expected": "judgment"},
        {"input": "LINE_A 상태 어때?", "expected": "judgment"},

        # BI (차트/분석)
        {"input": "11월달 센서 데이터 차트로 보여줘", "expected": "bi"},
        {"input": "온도 추이 그래프 만들어줘", "expected": "bi"},
        {"input": "라인별 불량률 비교 대시보드", "expected": "bi"},
        {"input": "지난달 생산량 통계 분석해줘", "expected": "bi"},

        # Workflow
        {"input": "새 워크플로우 만들어줘", "expected": "workflow"},
        {"input": "자동화 설정해줘", "expected": "workflow"},

        # Learning
        {"input": "온도 80도 넘으면 경고 규칙 만들어줘", "expected": "learning"},
        {"input": "새 룰셋 생성해줘", "expected": "learning"},

        # General
        {"input": "안녕", "expected": "general"},
        {"input": "넌 뭐야?", "expected": "general"},
    ]

    classifier = IntentClassifier()
    results = classifier.test_patterns(test_cases)

    print("\n=== Intent Classifier Test Results ===")
    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"{status} '{r['input'][:30]}...' → {r['actual']} (expected: {r['expected']})")

    passed = sum(1 for r in results if r["passed"])
    print(f"\nTotal: {passed}/{len(results)} passed")

    return results


if __name__ == "__main__":
    run_classifier_tests()
