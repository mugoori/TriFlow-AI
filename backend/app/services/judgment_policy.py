"""
Judgment 하이브리드 정책 서비스
스펙 참조: B-6, B-2-1

하이브리드 정책 (7개):
- RULE_ONLY: 룰만 사용 (속도 우선)
- LLM_ONLY: LLM만 사용 (유연성 우선)
- RULE_FALLBACK: 룰 우선, 룰 실패/오류 시 LLM으로 폴백
- LLM_FALLBACK: LLM 우선, LLM 실패/오류 시 룰로 폴백
- HYBRID_WEIGHTED: 룰 + LLM 가중 조합 (기본)
- HYBRID_GATE: 룰 신뢰도 기반 게이트 (신뢰도 낮으면 LLM)
- ESCALATE: 룰 우선, 불확실 시 LLM으로 에스컬레이션

V2 업데이트 (2025-12-16):
- RULE_FALLBACK, LLM_FALLBACK, HYBRID_GATE 추가
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class JudgmentPolicy(str, Enum):
    """
    판단 정책 유형

    스펙 (B-2-1) 기준 6개 정책:
    - RULE_ONLY: 룰만 사용 (속도 우선)
    - LLM_ONLY: LLM만 사용 (유연성 우선)
    - RULE_FALLBACK: 룰 우선, 룰 실패/오류 시 LLM으로 폴백
    - LLM_FALLBACK: LLM 우선, LLM 실패/오류 시 룰로 폴백
    - HYBRID_WEIGHTED: 룰 + LLM 가중 조합 (기본)
    - HYBRID_GATE: 룰 신뢰도 기반 게이트 (신뢰도 낮으면 LLM)
    - ESCALATE: 룰 우선, 불확실 시 LLM으로 에스컬레이션 (HYBRID_GATE 유사)
    """
    RULE_ONLY = "rule_only"
    LLM_ONLY = "llm_only"
    RULE_FALLBACK = "rule_fallback"
    LLM_FALLBACK = "llm_fallback"
    HYBRID_WEIGHTED = "hybrid_weighted"
    HYBRID_GATE = "hybrid_gate"
    ESCALATE = "escalate"


@dataclass
class JudgmentResult:
    """
    판단 결과

    V1 Gap 수정 (2026-01-05):
    - explanation: 판단 근거 설명 (감사 추적용)
    - evidence: 판단에 사용된 증거 목록
    - feature_importance: 입력 필드별 중요도 (스펙 JUD-FR-050)
    """
    decision: str  # OK, WARNING, CRITICAL, UNKNOWN
    confidence: float  # 0.0 ~ 1.0
    source: str  # rule, llm, hybrid
    policy_used: JudgmentPolicy
    details: Dict[str, Any] = field(default_factory=dict)
    rule_result: Optional[Dict[str, Any]] = None
    llm_result: Optional[Dict[str, Any]] = None
    execution_time_ms: int = 0
    cached: bool = False
    timestamp: str = ""
    # V1 Gap 수정: 판단 근거 및 증거
    explanation: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    feature_importance: Optional[Dict[str, float]] = None
    recommended_actions: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "source": self.source,
            "policy_used": self.policy_used.value,
            "details": self.details,
            "rule_result": self.rule_result,
            "llm_result": self.llm_result,
            "execution_time_ms": self.execution_time_ms,
            "cached": self.cached,
            "timestamp": self.timestamp,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "feature_importance": self.feature_importance,
            "recommended_actions": self.recommended_actions,
        }


class HybridJudgmentService:
    """
    하이브리드 판단 서비스

    룰 엔진과 LLM을 조합하여 판단 수행
    """

    # 신뢰도 임계값
    RULE_CONFIDENCE_THRESHOLD = 0.8  # 룰 신뢰도가 이 이상이면 룰 결과 사용
    LLM_CONFIDENCE_THRESHOLD = 0.7   # LLM 신뢰도가 이 이상이면 LLM 결과 사용
    ESCALATION_THRESHOLD = 0.6       # 이 미만이면 에스컬레이션

    # 가중치 (HYBRID_WEIGHTED 정책용)
    DEFAULT_RULE_WEIGHT = 0.6
    DEFAULT_LLM_WEIGHT = 0.4

    def __init__(
        self,
        rule_weight: float = None,
        llm_weight: float = None,
    ):
        self.rule_weight = rule_weight or self.DEFAULT_RULE_WEIGHT
        self.llm_weight = llm_weight or self.DEFAULT_LLM_WEIGHT

        # 가중치 정규화
        total = self.rule_weight + self.llm_weight
        self.rule_weight /= total
        self.llm_weight /= total

    async def execute(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
        policy: JudgmentPolicy = JudgmentPolicy.HYBRID_WEIGHTED,
        context: Dict[str, Any] = None,
    ) -> JudgmentResult:
        """
        하이브리드 판단 실행

        Args:
            tenant_id: 테넌트 ID
            ruleset_id: Ruleset ID
            input_data: 입력 데이터 (센서 값 등)
            policy: 판단 정책
            context: 추가 컨텍스트 (라인 코드, 시간대 등)

        Returns:
            JudgmentResult
        """
        import time
        start_time = time.time()

        # 캐시 확인
        from app.services.judgment_cache import get_judgment_cache
        cache = get_judgment_cache()
        cached_result = await cache.get(tenant_id, ruleset_id, input_data)

        if cached_result:
            return JudgmentResult(
                decision=cached_result["result"].get("decision", "UNKNOWN"),
                confidence=cached_result["confidence"],
                source="cache",
                policy_used=policy,
                details=cached_result["result"],
                cached=True,
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

        # 정책별 실행
        if policy == JudgmentPolicy.RULE_ONLY:
            result = await self._execute_rule_only(tenant_id, ruleset_id, input_data)
        elif policy == JudgmentPolicy.LLM_ONLY:
            result = await self._execute_llm_only(tenant_id, input_data, context)
        elif policy == JudgmentPolicy.RULE_FALLBACK:
            result = await self._execute_rule_fallback(tenant_id, ruleset_id, input_data, context)
        elif policy == JudgmentPolicy.LLM_FALLBACK:
            result = await self._execute_llm_fallback(tenant_id, ruleset_id, input_data, context)
        elif policy == JudgmentPolicy.HYBRID_GATE:
            result = await self._execute_hybrid_gate(tenant_id, ruleset_id, input_data, context)
        elif policy == JudgmentPolicy.ESCALATE:
            result = await self._execute_escalate(tenant_id, ruleset_id, input_data, context)
        else:  # HYBRID_WEIGHTED
            result = await self._execute_hybrid_weighted(tenant_id, ruleset_id, input_data, context)

        result.execution_time_ms = int((time.time() - start_time) * 1000)

        # 결과 캐싱 (신뢰도가 높은 경우만)
        if result.confidence >= 0.7:
            await cache.set(
                tenant_id,
                ruleset_id,
                input_data,
                result.to_dict(),
                result.confidence,
            )

        return result

    async def _execute_rule_only(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
    ) -> JudgmentResult:
        """
        룰만 사용하여 판단
        """
        rule_result = await self._run_rule_engine(tenant_id, ruleset_id, input_data)

        if rule_result["success"]:
            decision = self._extract_decision(rule_result)
            return JudgmentResult(
                decision=decision,
                confidence=self._calculate_rule_confidence(rule_result, input_data),
                source="rule",
                policy_used=JudgmentPolicy.RULE_ONLY,
                rule_result=rule_result,
                details={"checks": rule_result.get("result", {}).get("checks", [])},
                explanation=self._generate_explanation(
                    decision=decision,
                    source="rule",
                    rule_result=rule_result,
                    policy=JudgmentPolicy.RULE_ONLY,
                ),
                evidence=self._extract_evidence(input_data, rule_result=rule_result),
                feature_importance=self._calculate_feature_importance(
                    input_data, decision, rule_result=rule_result
                ),
                recommended_actions=self._generate_recommended_actions(
                    decision, rule_result=rule_result
                ),
            )
        else:
            return JudgmentResult(
                decision="UNKNOWN",
                confidence=0.0,
                source="rule",
                policy_used=JudgmentPolicy.RULE_ONLY,
                rule_result=rule_result,
                details={"error": rule_result.get("error")},
                explanation=self._generate_explanation(
                    decision="UNKNOWN",
                    source="rule",
                    rule_result=rule_result,
                    policy=JudgmentPolicy.RULE_ONLY,
                ),
                evidence=self._extract_evidence(input_data, rule_result=rule_result),
            )

    async def _execute_llm_only(
        self,
        tenant_id: UUID,
        input_data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> JudgmentResult:
        """
        LLM만 사용하여 판단
        """
        llm_result = await self._run_llm_judgment(tenant_id, input_data, context)
        decision = llm_result.get("decision", "UNKNOWN")

        return JudgmentResult(
            decision=decision,
            confidence=llm_result.get("confidence", 0.5),
            source="llm",
            policy_used=JudgmentPolicy.LLM_ONLY,
            llm_result=llm_result,
            details={"reasoning": llm_result.get("reasoning", "")},
            explanation=self._generate_explanation(
                decision=decision,
                source="llm",
                llm_result=llm_result,
                policy=JudgmentPolicy.LLM_ONLY,
            ),
            evidence=self._extract_evidence(input_data, llm_result=llm_result),
            feature_importance=self._calculate_feature_importance(
                input_data, decision, llm_result=llm_result
            ),
            recommended_actions=self._generate_recommended_actions(
                decision, llm_result=llm_result
            ),
        )

    async def _execute_escalate(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> JudgmentResult:
        """
        룰 우선, 불확실 시 LLM으로 에스컬레이션
        """
        # 1. 먼저 룰 실행
        rule_result = await self._run_rule_engine(tenant_id, ruleset_id, input_data)
        rule_confidence = self._calculate_rule_confidence(rule_result, input_data)

        # 2. 룰 신뢰도가 충분하면 룰 결과 사용
        if rule_result["success"] and rule_confidence >= self.RULE_CONFIDENCE_THRESHOLD:
            decision = self._extract_decision(rule_result)
            return JudgmentResult(
                decision=decision,
                confidence=rule_confidence,
                source="rule",
                policy_used=JudgmentPolicy.ESCALATE,
                rule_result=rule_result,
                details={"escalated": False},
                explanation=self._generate_explanation(
                    decision=decision,
                    source="rule",
                    rule_result=rule_result,
                    policy=JudgmentPolicy.ESCALATE,
                ),
                evidence=self._extract_evidence(input_data, rule_result=rule_result),
            )

        # 3. 룰 불확실 → LLM으로 에스컬레이션
        logger.info(f"Escalating to LLM (rule confidence: {rule_confidence})")
        llm_result = await self._run_llm_judgment(tenant_id, input_data, context)
        decision = llm_result.get("decision", "UNKNOWN")

        return JudgmentResult(
            decision=decision,
            confidence=llm_result.get("confidence", 0.5),
            source="llm_escalated",
            policy_used=JudgmentPolicy.ESCALATE,
            rule_result=rule_result,
            llm_result=llm_result,
            details={
                "escalated": True,
                "rule_confidence": rule_confidence,
                "reasoning": llm_result.get("reasoning", ""),
            },
            explanation=self._generate_explanation(
                decision=decision,
                source="llm_escalated",
                rule_result=rule_result,
                llm_result=llm_result,
                policy=JudgmentPolicy.ESCALATE,
            ),
            evidence=self._extract_evidence(input_data, rule_result=rule_result, llm_result=llm_result),
        )

    async def _execute_rule_fallback(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> JudgmentResult:
        """
        룰 우선, 룰 실패/오류 시 LLM으로 폴백

        ESCALATE와의 차이점:
        - ESCALATE: 룰 "신뢰도 낮음" → LLM
        - RULE_FALLBACK: 룰 "실패/오류" → LLM
        """
        # 1. 먼저 룰 실행
        rule_result = await self._run_rule_engine(tenant_id, ruleset_id, input_data)

        # 2. 룰 성공 시 룰 결과 사용
        if rule_result.get("success"):
            decision = self._extract_decision(rule_result)
            return JudgmentResult(
                decision=decision,
                confidence=self._calculate_rule_confidence(rule_result, input_data),
                source="rule",
                policy_used=JudgmentPolicy.RULE_FALLBACK,
                rule_result=rule_result,
                details={"fallback_used": False},
                explanation=self._generate_explanation(
                    decision=decision,
                    source="rule",
                    rule_result=rule_result,
                    policy=JudgmentPolicy.RULE_FALLBACK,
                ),
                evidence=self._extract_evidence(input_data, rule_result=rule_result),
            )

        # 3. 룰 실패 → LLM으로 폴백
        logger.info(f"Rule failed, falling back to LLM: {rule_result.get('error')}")
        llm_result = await self._run_llm_judgment(tenant_id, input_data, context)
        decision = llm_result.get("decision", "UNKNOWN")

        return JudgmentResult(
            decision=decision,
            confidence=llm_result.get("confidence", 0.5),
            source="llm_fallback",
            policy_used=JudgmentPolicy.RULE_FALLBACK,
            rule_result=rule_result,
            llm_result=llm_result,
            details={
                "fallback_used": True,
                "rule_error": rule_result.get("error"),
                "reasoning": llm_result.get("reasoning", ""),
            },
            explanation=self._generate_explanation(
                decision=decision,
                source="llm_fallback",
                rule_result=rule_result,
                llm_result=llm_result,
                policy=JudgmentPolicy.RULE_FALLBACK,
            ),
            evidence=self._extract_evidence(input_data, rule_result=rule_result, llm_result=llm_result),
        )

    async def _execute_llm_fallback(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> JudgmentResult:
        """
        LLM 우선, LLM 실패/오류 시 룰로 폴백

        LLM API 장애 또는 응답 파싱 실패 시 룰 사용
        """
        # 1. 먼저 LLM 실행
        llm_result = await self._run_llm_judgment(tenant_id, input_data, context)

        # 2. LLM 성공 및 유효한 결정이면 LLM 결과 사용
        llm_decision = llm_result.get("decision", "UNKNOWN")
        llm_confidence = llm_result.get("confidence", 0.0)
        llm_error = llm_result.get("error")

        if not llm_error and llm_decision != "UNKNOWN" and llm_confidence > 0:
            return JudgmentResult(
                decision=llm_decision,
                confidence=llm_confidence,
                source="llm",
                policy_used=JudgmentPolicy.LLM_FALLBACK,
                llm_result=llm_result,
                details={
                    "fallback_used": False,
                    "reasoning": llm_result.get("reasoning", ""),
                },
                explanation=self._generate_explanation(
                    decision=llm_decision,
                    source="llm",
                    llm_result=llm_result,
                    policy=JudgmentPolicy.LLM_FALLBACK,
                ),
                evidence=self._extract_evidence(input_data, llm_result=llm_result),
            )

        # 3. LLM 실패 → 룰로 폴백
        logger.info(f"LLM failed or uncertain, falling back to Rule: {llm_error}")
        rule_result = await self._run_rule_engine(tenant_id, ruleset_id, input_data)

        if rule_result.get("success"):
            decision = self._extract_decision(rule_result)
            return JudgmentResult(
                decision=decision,
                confidence=self._calculate_rule_confidence(rule_result, input_data),
                source="rule_fallback",
                policy_used=JudgmentPolicy.LLM_FALLBACK,
                rule_result=rule_result,
                llm_result=llm_result,
                details={
                    "fallback_used": True,
                    "llm_error": llm_error,
                },
                explanation=self._generate_explanation(
                    decision=decision,
                    source="rule_fallback",
                    rule_result=rule_result,
                    llm_result=llm_result,
                    policy=JudgmentPolicy.LLM_FALLBACK,
                ),
                evidence=self._extract_evidence(input_data, rule_result=rule_result, llm_result=llm_result),
            )
        else:
            # 둘 다 실패
            return JudgmentResult(
                decision="UNKNOWN",
                confidence=0.0,
                source="none",
                policy_used=JudgmentPolicy.LLM_FALLBACK,
                rule_result=rule_result,
                llm_result=llm_result,
                details={
                    "fallback_used": True,
                    "llm_error": llm_error,
                    "rule_error": rule_result.get("error"),
                    "both_failed": True,
                },
                explanation=self._generate_explanation(
                    decision="UNKNOWN",
                    source="none",
                    rule_result=rule_result,
                    llm_result=llm_result,
                    policy=JudgmentPolicy.LLM_FALLBACK,
                ),
                evidence=self._extract_evidence(input_data, rule_result=rule_result, llm_result=llm_result),
            )

    async def _execute_hybrid_gate(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> JudgmentResult:
        """
        룰 신뢰도 기반 게이트

        1. 룰 실행 → 신뢰도 계산
        2. 신뢰도가 GATE_THRESHOLD 이상이면 룰 결과 사용
        3. 신뢰도가 낮으면 LLM "병렬" 호출 → 두 결과 비교
        4. 결과가 일치하면 신뢰도 보너스
        5. 결과가 다르면 신뢰도 높은 쪽 선택

        ESCALATE와의 차이점:
        - ESCALATE: 순차적 (룰 → 필요시 LLM)
        - HYBRID_GATE: 게이트 기반 병렬 (신뢰도 낮으면 LLM도 호출)
        """
        GATE_THRESHOLD = 0.85  # 이 이상이면 룰만 사용

        # 1. 먼저 룰 실행
        rule_result = await self._run_rule_engine(tenant_id, ruleset_id, input_data)
        rule_confidence = self._calculate_rule_confidence(rule_result, input_data)
        rule_decision = self._extract_decision(rule_result)

        # 2. 룰 신뢰도가 게이트 임계값 이상이면 룰 결과만 사용
        if rule_result.get("success") and rule_confidence >= GATE_THRESHOLD:
            return JudgmentResult(
                decision=rule_decision,
                confidence=rule_confidence,
                source="rule",
                policy_used=JudgmentPolicy.HYBRID_GATE,
                rule_result=rule_result,
                details={
                    "gate_passed": True,
                    "rule_confidence": rule_confidence,
                    "gate_threshold": GATE_THRESHOLD,
                },
                explanation=self._generate_explanation(
                    decision=rule_decision,
                    source="rule",
                    rule_result=rule_result,
                    policy=JudgmentPolicy.HYBRID_GATE,
                ),
                evidence=self._extract_evidence(input_data, rule_result=rule_result),
            )

        # 3. 신뢰도 낮음 → LLM도 호출
        logger.info(f"Gate not passed (rule confidence: {rule_confidence}), calling LLM")
        llm_result = await self._run_llm_judgment(tenant_id, input_data, context)
        llm_confidence = llm_result.get("confidence", 0.5)
        llm_decision = llm_result.get("decision", "UNKNOWN")

        # 4. 두 결과 비교
        if rule_decision == llm_decision and rule_decision != "UNKNOWN":
            # 일치 → 신뢰도 보너스
            combined_confidence = min(
                (rule_confidence + llm_confidence) / 2 * 1.15,
                1.0
            )
            return JudgmentResult(
                decision=rule_decision,
                confidence=round(combined_confidence, 3),
                source="hybrid_consensus",
                policy_used=JudgmentPolicy.HYBRID_GATE,
                rule_result=rule_result,
                llm_result=llm_result,
                details={
                    "gate_passed": False,
                    "consensus": True,
                    "rule_confidence": rule_confidence,
                    "llm_confidence": llm_confidence,
                    "gate_threshold": GATE_THRESHOLD,
                },
                explanation=self._generate_explanation(
                    decision=rule_decision,
                    source="hybrid_consensus",
                    rule_result=rule_result,
                    llm_result=llm_result,
                    policy=JudgmentPolicy.HYBRID_GATE,
                ),
                evidence=self._extract_evidence(input_data, rule_result=rule_result, llm_result=llm_result),
            )

        # 5. 불일치 → 신뢰도 높은 쪽 선택
        if rule_confidence >= llm_confidence:
            final_decision = rule_decision
            primary_source = "rule"
            final_confidence = rule_confidence
        else:
            final_decision = llm_decision
            primary_source = "llm"
            final_confidence = llm_confidence

        # 불일치 패널티
        final_confidence = final_confidence * 0.9

        return JudgmentResult(
            decision=final_decision,
            confidence=round(final_confidence, 3),
            source=f"hybrid_{primary_source}",
            policy_used=JudgmentPolicy.HYBRID_GATE,
            rule_result=rule_result,
            llm_result=llm_result,
            details={
                "gate_passed": False,
                "consensus": False,
                "rule_decision": rule_decision,
                "llm_decision": llm_decision,
                "rule_confidence": rule_confidence,
                "llm_confidence": llm_confidence,
                "primary_source": primary_source,
                "disagreement_penalty_applied": True,
                "gate_threshold": GATE_THRESHOLD,
            },
            explanation=self._generate_explanation(
                decision=final_decision,
                source=f"hybrid_{primary_source}",
                rule_result=rule_result,
                llm_result=llm_result,
                policy=JudgmentPolicy.HYBRID_GATE,
            ),
            evidence=self._extract_evidence(input_data, rule_result=rule_result, llm_result=llm_result),
        )

    async def _execute_hybrid_weighted(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> JudgmentResult:
        """
        룰 + LLM 가중 조합
        """
        import asyncio

        # 병렬 실행
        rule_task = self._run_rule_engine(tenant_id, ruleset_id, input_data)
        llm_task = self._run_llm_judgment(tenant_id, input_data, context)

        rule_result, llm_result = await asyncio.gather(rule_task, llm_task)

        # 신뢰도 계산
        rule_confidence = self._calculate_rule_confidence(rule_result, input_data)
        llm_confidence = llm_result.get("confidence", 0.5)

        # 결정 추출
        rule_decision = self._extract_decision(rule_result)
        llm_decision = llm_result.get("decision", "UNKNOWN")

        # 가중 조합
        combined_confidence = (
            rule_confidence * self.rule_weight +
            llm_confidence * self.llm_weight
        )

        # 결정 선택 (신뢰도 높은 쪽 우선)
        if rule_confidence >= llm_confidence:
            final_decision = rule_decision
            primary_source = "rule"
        else:
            final_decision = llm_decision
            primary_source = "llm"

        # 결정이 일치하면 신뢰도 보너스
        if rule_decision == llm_decision and rule_decision != "UNKNOWN":
            combined_confidence = min(combined_confidence * 1.1, 1.0)

        return JudgmentResult(
            decision=final_decision,
            confidence=round(combined_confidence, 3),
            source="hybrid",
            policy_used=JudgmentPolicy.HYBRID_WEIGHTED,
            rule_result=rule_result,
            llm_result=llm_result,
            details={
                "rule_confidence": rule_confidence,
                "llm_confidence": llm_confidence,
                "rule_decision": rule_decision,
                "llm_decision": llm_decision,
                "primary_source": primary_source,
                "weights": {"rule": self.rule_weight, "llm": self.llm_weight},
            },
            explanation=self._generate_explanation(
                decision=final_decision,
                source="hybrid",
                rule_result=rule_result,
                llm_result=llm_result,
                policy=JudgmentPolicy.HYBRID_WEIGHTED,
            ),
            evidence=self._extract_evidence(input_data, rule_result=rule_result, llm_result=llm_result),
            feature_importance=self._calculate_feature_importance(
                input_data, final_decision, rule_result=rule_result, llm_result=llm_result
            ),
            recommended_actions=self._generate_recommended_actions(
                final_decision, rule_result=rule_result, llm_result=llm_result
            ),
        )

    async def _run_rule_engine(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Rhai 룰 엔진 실행
        """
        try:
            from app.database import get_db_context
            from app.models.core import Ruleset
            from app.tools.rhai import RhaiEngine

            with get_db_context() as db:
                ruleset = db.query(Ruleset).filter(
                    Ruleset.ruleset_id == ruleset_id
                ).first()

                if not ruleset:
                    return {"success": False, "error": f"Ruleset {ruleset_id} not found"}

                if not ruleset.is_active:
                    return {"success": False, "error": f"Ruleset {ruleset_id} is inactive"}

                rhai_engine = RhaiEngine()
                result = rhai_engine.execute(
                    script=ruleset.rhai_script,
                    context={"input": input_data},
                )

                # V1 Gap 수정: ruleset_version, matched_rules, confidence 추가
                return {
                    "success": True,
                    "ruleset_id": str(ruleset_id),
                    "ruleset_name": ruleset.name,
                    "ruleset_version": ruleset.version,  # V1 Gap 수정
                    "result": result,
                    "matched_rules": result.get("matched_rules", []),  # V1 Gap 수정
                    "confidence": self._calculate_rule_confidence({"success": True, "result": result}),  # V1 Gap 수정
                }

        except Exception as e:
            logger.error(f"Rule engine error: {e}")
            return {"success": False, "error": str(e)}

    async def _run_llm_judgment(
        self,
        tenant_id: UUID,
        input_data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        LLM 기반 판단
        """
        try:
            from anthropic import Anthropic
            from app.config import settings

            client = Anthropic(api_key=settings.anthropic_api_key)

            # 프롬프트 구성
            system_prompt = """당신은 제조 공정 분석 전문가입니다.
센서 데이터를 분석하여 공정 상태를 판단합니다.

출력 형식 (JSON):
{
    "decision": "OK" | "WARNING" | "CRITICAL",
    "confidence": 0.0-1.0,
    "reasoning": "판단 근거 설명"
}

판단 기준:
- OK: 모든 센서값이 정상 범위
- WARNING: 일부 센서가 경고 수준 (임계값 근접)
- CRITICAL: 하나 이상의 센서가 위험 수준 초과
"""

            user_message = f"""다음 센서 데이터를 분석하고 공정 상태를 판단하세요:

센서 데이터:
{self._format_sensor_data(input_data)}

{self._format_context(context) if context else ""}

JSON 형식으로 응답하세요."""

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            # 응답 파싱
            response_text = response.content[0].text
            import json
            import re

            # V1 Gap 수정: 사용된 모델 정보 기록
            model_used = "claude-sonnet-4-5-20250929"

            # JSON 추출
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "decision": result.get("decision", "UNKNOWN"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "reasoning": result.get("reasoning", ""),
                    "raw_response": response_text,
                    "model": model_used,  # V1 Gap 수정
                }

            return {
                "decision": "UNKNOWN",
                "confidence": 0.3,
                "reasoning": response_text,
                "error": "Failed to parse JSON response",
                "model": model_used,  # V1 Gap 수정
            }

        except Exception as e:
            logger.error(f"LLM judgment error: {e}")
            return {
                "decision": "UNKNOWN",
                "confidence": 0.0,
                "reasoning": "",
                "error": str(e),
                "model": "unknown",  # V1 Gap 수정
            }

    def _format_sensor_data(self, input_data: Dict[str, Any]) -> str:
        """센서 데이터 포맷팅"""
        lines = []
        for key, value in input_data.items():
            if isinstance(value, (int, float)):
                lines.append(f"- {key}: {value}")
        return "\n".join(lines) if lines else str(input_data)

    def _format_context(self, context: Dict[str, Any]) -> str:
        """컨텍스트 포맷팅"""
        if not context:
            return ""
        lines = ["추가 컨텍스트:"]
        for key, value in context.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _extract_decision(self, rule_result: Dict[str, Any]) -> str:
        """룰 결과에서 결정 추출"""
        if not rule_result.get("success"):
            return "UNKNOWN"

        result = rule_result.get("result", {})

        # 상태 필드 확인
        status = result.get("status") or result.get("action")
        if status:
            status_upper = str(status).upper()
            if status_upper in ["CRITICAL", "STOP_LINE", "ALERT"]:
                return "CRITICAL"
            elif status_upper in ["WARNING", "HIGH", "NOTIFY"]:
                return "WARNING"
            elif status_upper in ["OK", "NORMAL", "NONE", "LOG"]:
                return "OK"

        # checks 필드 확인
        checks = result.get("checks", [])
        if checks:
            statuses = [c.get("status", "").upper() for c in checks]
            if "CRITICAL" in statuses:
                return "CRITICAL"
            elif "WARNING" in statuses or "HIGH" in statuses:
                return "WARNING"
            return "OK"

        return "UNKNOWN"

    def _calculate_rule_confidence(
        self,
        rule_result: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        룰 결과의 신뢰도 계산 (스펙 개선)

        스펙 요구사항: Rule 매치 강도 + 데이터 품질 + 히스토리 정확도

        구현:
        - Rule 매치 강도 (40%): 체크 통과율, 명시적 신뢰도
        - 데이터 품질 (30%): 입력 데이터 완전성, 범위 내 여부
        - 히스토리 정확도 (30%): 과거 실행 통계 (향후 DB 조회)

        Returns:
            0.0 ~ 1.0
        """
        if not rule_result.get("success"):
            return 0.0

        result = rule_result.get("result", {})

        # 1. Rule 매치 강도 (40%)
        rule_match_strength = 0.5  # 기본값

        # 명시적 신뢰도가 있으면 사용
        if "confidence" in result:
            rule_match_strength = float(result["confidence"])
        # checks 기반 계산
        elif "checks" in result:
            checks = result.get("checks", [])
            if checks:
                # 체크 통과율
                passed = sum(1 for c in checks if c.get("status") in ["OK", "NORMAL"])
                total = len(checks)
                pass_rate = passed / total if total > 0 else 0.5

                # 심각도 가중치
                critical_count = sum(1 for c in checks if c.get("status") == "CRITICAL")
                warning_count = sum(1 for c in checks if c.get("status") in ["WARNING", "HIGH"])

                if critical_count > 0:
                    rule_match_strength = min(0.95, 0.7 + pass_rate * 0.25)
                elif warning_count > 0:
                    rule_match_strength = min(0.85, 0.6 + pass_rate * 0.25)
                else:
                    rule_match_strength = min(0.90, 0.5 + pass_rate * 0.4)

        # 2. 데이터 품질 (30%)
        data_quality_score = 0.7  # 기본값

        if input_data:
            # 필수 필드 완전성
            numeric_fields = {k: v for k, v in input_data.items() if isinstance(v, (int, float))}
            total_fields = len(input_data)
            numeric_ratio = len(numeric_fields) / total_fields if total_fields > 0 else 0

            # None 값 체크
            non_null_ratio = sum(1 for v in input_data.values() if v is not None) / total_fields if total_fields > 0 else 0

            # 범위 내 여부 (간단한 휴리스틱)
            in_range_count = 0
            for key, value in numeric_fields.items():
                if isinstance(value, (int, float)):
                    # 합리적인 범위 체크 (센서 데이터 가정)
                    if key == "temperature" and 0 <= value <= 150:
                        in_range_count += 1
                    elif key == "pressure" and 0 <= value <= 20:
                        in_range_count += 1
                    elif key == "humidity" and 0 <= value <= 100:
                        in_range_count += 1
                    elif 0 <= value <= 1000000:  # 일반 범위
                        in_range_count += 1

            in_range_ratio = in_range_count / len(numeric_fields) if numeric_fields else 1.0

            # 데이터 품질 점수 계산
            data_quality_score = (
                non_null_ratio * 0.4 +
                numeric_ratio * 0.3 +
                in_range_ratio * 0.3
            )

        # 3. 히스토리 정확도 (30%) - 실제 DB 조회
        historical_accuracy = self._get_historical_accuracy_sync(tenant_id, ruleset_id)

        # 최종 신뢰도 = 가중 합계
        final_confidence = (
            rule_match_strength * 0.4 +
            data_quality_score * 0.3 +
            historical_accuracy * 0.3
        )

        return round(min(final_confidence, 1.0), 3)

    def _get_historical_accuracy_sync(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
    ) -> float:
        """
        룰셋의 히스토리 정확도 조회 (실제 DB 기반)

        과거 실행 기록의 피드백을 기반으로 정확도 계산
        - 긍정 피드백: 1.0
        - 부정 피드백: 0.0
        - 피드백 없음: 0.5 (중립)

        Returns:
            0.0 ~ 1.0 (히스토리 정확도)
        """
        try:
            from app.database import get_db_context
            from sqlalchemy import text

            with get_db_context() as db:
                # 최근 30일간 피드백 기반 정확도
                query = text("""
                    SELECT
                        COUNT(*) as total_executions,
                        COUNT(f.feedback_id) as feedback_count,
                        AVG(CASE
                            WHEN f.feedback_type = 'positive' THEN 1.0
                            WHEN f.feedback_type = 'negative' THEN 0.0
                            ELSE 0.5
                        END) as accuracy_rate,
                        SUM(CASE WHEN f.feedback_type = 'positive' THEN 1 ELSE 0 END) as positive_count,
                        SUM(CASE WHEN f.feedback_type = 'negative' THEN 1 ELSE 0 END) as negative_count
                    FROM core.judgment_executions je
                    LEFT JOIN core.feedbacks f ON f.judgment_execution_id = je.execution_id
                    WHERE je.tenant_id = :tenant_id
                      AND je.ruleset_id = :ruleset_id
                      AND je.created_at >= NOW() - INTERVAL '30 days'
                """)

                result = db.execute(
                    query,
                    {
                        "tenant_id": str(tenant_id),
                        "ruleset_id": str(ruleset_id),
                    },
                ).fetchone()

                if result:
                    total = result.total_executions or 0
                    feedback_count = result.feedback_count or 0
                    accuracy_rate = result.accuracy_rate
                    positive_count = result.positive_count or 0
                    negative_count = result.negative_count or 0

                    # 실행 기록이 없으면 기본값
                    if total == 0:
                        logger.debug(f"No execution history for ruleset {ruleset_id}, using default 0.75")
                        return 0.75

                    # 피드백이 충분하면 (10개 이상) 실제 정확도 사용
                    if feedback_count >= 10 and accuracy_rate is not None:
                        logger.debug(
                            f"Historical accuracy for ruleset {ruleset_id}: {accuracy_rate:.3f} "
                            f"(based on {feedback_count} feedbacks: {positive_count}+ / {negative_count}-)"
                        )
                        return float(accuracy_rate)

                    # 피드백이 적으면 (1-9개) 기본값과 혼합
                    if feedback_count > 0 and accuracy_rate is not None:
                        # 피드백 비율에 따라 가중 평균
                        feedback_weight = min(feedback_count / 10, 1.0)
                        blended_accuracy = float(accuracy_rate) * feedback_weight + 0.75 * (1 - feedback_weight)
                        logger.debug(
                            f"Blended accuracy for ruleset {ruleset_id}: {blended_accuracy:.3f} "
                            f"({feedback_count} feedbacks, weight={feedback_weight:.2f})"
                        )
                        return blended_accuracy

                    # 피드백 없으면 기본값
                    logger.debug(f"No feedback for ruleset {ruleset_id}, using default 0.75")
                    return 0.75

                # 기본값
                return 0.75

        except Exception as e:
            logger.warning(f"Failed to get historical accuracy for ruleset {ruleset_id}, using default: {e}")
            return 0.75

    def _generate_explanation(
        self,
        decision: str,
        source: str,
        rule_result: Optional[Dict[str, Any]] = None,
        llm_result: Optional[Dict[str, Any]] = None,
        policy: JudgmentPolicy = None,
    ) -> Dict[str, Any]:
        """
        판단 근거 설명 생성 (V1 Gap 수정)

        스펙 요구사항:
        - 사용자에게 판단 근거를 제시
        - 감사 추적을 위한 상세 기록
        """
        explanation = {
            "summary": "",
            "decision_factors": [],
            "source_details": {},
        }

        # 결정 요약
        decision_desc = {
            "OK": "정상 상태입니다.",
            "WARNING": "주의가 필요한 상태입니다.",
            "CRITICAL": "즉각적인 조치가 필요합니다.",
            "UNKNOWN": "판단을 내릴 수 없습니다.",
        }
        explanation["summary"] = decision_desc.get(decision, "알 수 없는 상태입니다.")

        # 소스별 상세 설명
        if source in ["rule", "rule_fallback"]:
            explanation["source_details"]["type"] = "rule_based"
            if rule_result and rule_result.get("success"):
                result = rule_result.get("result", {})
                checks = result.get("checks", [])
                if checks:
                    for check in checks:
                        explanation["decision_factors"].append({
                            "factor": check.get("name", "unknown"),
                            "status": check.get("status", "unknown"),
                            "value": check.get("value"),
                            "threshold": check.get("threshold"),
                        })
                explanation["source_details"]["ruleset_id"] = rule_result.get("ruleset_id")
                explanation["source_details"]["ruleset_name"] = rule_result.get("ruleset_name")

        elif source in ["llm", "llm_fallback", "llm_escalated"]:
            explanation["source_details"]["type"] = "llm_based"
            if llm_result:
                explanation["decision_factors"].append({
                    "factor": "llm_reasoning",
                    "reasoning": llm_result.get("reasoning", ""),
                })
                explanation["source_details"]["model"] = llm_result.get("model", "unknown")

        elif source in ["hybrid", "hybrid_consensus", "hybrid_rule", "hybrid_llm"]:
            explanation["source_details"]["type"] = "hybrid"
            if rule_result and rule_result.get("success"):
                explanation["decision_factors"].append({
                    "factor": "rule_decision",
                    "decision": self._extract_decision(rule_result),
                    "confidence": self._calculate_rule_confidence(rule_result, input_data),
                })
            if llm_result:
                explanation["decision_factors"].append({
                    "factor": "llm_decision",
                    "decision": llm_result.get("decision"),
                    "confidence": llm_result.get("confidence"),
                    "reasoning": llm_result.get("reasoning", ""),
                })

        # 정책 정보
        if policy:
            explanation["policy"] = policy.value

        return explanation

    def _extract_evidence(
        self,
        input_data: Dict[str, Any],
        rule_result: Optional[Dict[str, Any]] = None,
        llm_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        판단에 사용된 증거 데이터 추출 (스펙 JUD-FR-050)

        스펙 요구사항:
        - 판단 근거가 된 데이터 포인트 기록
        - 히스토리 비교 데이터
        - 임계값 정보
        - 유사 케이스 참조

        Returns:
            {
                "input_values": {...},
                "calculated_metrics": {...},
                "thresholds": {...},
                "historical_avg": {...},
                "similar_cases_count": N,
                "rule_checks": [...],
                "data_refs": [...]
            }
        """
        evidence = {
            "input_values": {},
            "calculated_metrics": {},
            "thresholds": {},
            "historical_avg": {},
            "similar_cases_count": 0,
            "rule_checks": [],
            "data_refs": [],
        }

        # 1. 입력 데이터 기록
        for key, value in input_data.items():
            if isinstance(value, (int, float, str, bool)):
                evidence["input_values"][key] = value

        # 2. 계산된 메트릭 (룰에서 계산된 값들)
        if rule_result and rule_result.get("success"):
            result = rule_result.get("result", {})

            # 불량률, OEE 등 계산된 값
            for key in ["defect_rate", "oee", "availability", "performance", "quality"]:
                if key in result:
                    evidence["calculated_metrics"][key] = result[key]

            # 룰 체크 결과
            checks = result.get("checks", [])
            for check in checks:
                evidence["rule_checks"].append({
                    "name": check.get("name", "unknown"),
                    "status": check.get("status", "unknown"),
                    "value": check.get("value"),
                    "threshold": check.get("threshold"),
                    "passed": check.get("status") in ["OK", "NORMAL", "PASS"],
                })

                # 임계값 기록
                if check.get("threshold") is not None:
                    evidence["thresholds"][check.get("name", "unknown")] = check["threshold"]

        # 3. 히스토리 평균 및 유사 케이스 (실제 DB 조회)
        historical_data = self._get_historical_evidence(input_data, rule_result)
        if historical_data:
            evidence["historical_avg"] = historical_data.get("averages", {})
            evidence["similar_cases_count"] = historical_data.get("similar_count", 0)

        # 4. 데이터 참조 (룰셋, 프롬프트 등)
        if rule_result:
            evidence["data_refs"].append({
                "type": "ruleset",
                "id": rule_result.get("ruleset_id"),
                "name": rule_result.get("ruleset_name"),
                "version": rule_result.get("ruleset_version"),
            })

        if llm_result and llm_result.get("model"):
            evidence["data_refs"].append({
                "type": "llm_model",
                "model": llm_result.get("model"),
            })

        return evidence

    def _get_historical_evidence(
        self,
        input_data: Dict[str, Any],
        rule_result: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        히스토리 증거 데이터 조회 (실제 DB 기반)

        최근 7일간 평균값 및 유사 케이스 개수 조회

        Returns:
            {
                "averages": {"defect_rate_7d": 0.012, "temperature_7d": 68.5},
                "similar_count": 23
            }
        """
        try:
            from app.database import get_db_context
            from sqlalchemy import text

            # 계산된 메트릭에서 defect_rate 찾기
            if not rule_result or not rule_result.get("success"):
                return None

            result = rule_result.get("result", {})
            has_defect_rate = "defect_rate" in result

            if not has_defect_rate:
                return None

            with get_db_context() as db:
                # 최근 7일 평균 defect_rate 조회
                query = text("""
                    SELECT
                        AVG((input_data->>'defect_rate')::numeric) as avg_defect_rate,
                        AVG((input_data->>'temperature')::numeric) as avg_temperature,
                        COUNT(*) as similar_count
                    FROM core.judgment_executions
                    WHERE tenant_id = :tenant_id
                      AND created_at >= NOW() - INTERVAL '7 days'
                      AND input_data->>'defect_rate' IS NOT NULL
                """)

                hist_result = db.execute(
                    query,
                    {"tenant_id": str(rule_result.get("tenant_id", ""))},
                ).fetchone()

                if hist_result:
                    averages = {}

                    if hist_result.avg_defect_rate is not None:
                        averages["defect_rate_7d"] = round(float(hist_result.avg_defect_rate), 4)

                    if hist_result.avg_temperature is not None:
                        averages["temperature_7d"] = round(float(hist_result.avg_temperature), 2)

                    similar_count = hist_result.similar_count or 0

                    return {
                        "averages": averages,
                        "similar_count": similar_count,
                    }

                return None

        except Exception as e:
            logger.debug(f"Failed to get historical evidence: {e}")
            return None

    def _calculate_feature_importance(
        self,
        input_data: Dict[str, Any],
        decision: str,
        rule_result: Optional[Dict[str, Any]] = None,
        llm_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """
        Feature Importance 계산 (스펙 JUD-FR-050)

        판단에 영향을 준 입력 필드의 중요도 계산
        (간단한 휴리스틱 기반, 추후 SHAP values로 개선 가능)

        Returns:
            {
                "temperature": 0.45,
                "pressure": 0.30,
                "defect_count": 0.25,
                ...
            }
        """
        importance = {}

        # 1. 룰 체크 기반 중요도
        if rule_result and rule_result.get("success"):
            result = rule_result.get("result", {})
            checks = result.get("checks", [])

            total_checks = len(checks)
            if total_checks > 0:
                for check in checks:
                    field_name = check.get("name", "unknown")
                    # 체크 실패한 필드가 더 중요
                    if check.get("status") in ["CRITICAL", "WARNING", "HIGH"]:
                        importance[field_name] = 0.8 / total_checks
                    elif check.get("status") in ["OK", "NORMAL"]:
                        importance[field_name] = 0.2 / total_checks

        # 2. 입력 데이터의 기본 중요도 (평균 분배)
        numeric_fields = {k: v for k, v in input_data.items() if isinstance(v, (int, float))}
        if numeric_fields and not importance:
            base_importance = 1.0 / len(numeric_fields)
            for key in numeric_fields:
                importance[key] = base_importance

        # 3. 정규화 (합계가 1.0이 되도록)
        total = sum(importance.values())
        if total > 0:
            importance = {k: round(v / total, 3) for k, v in importance.items()}

        return importance


# 전역 인스턴스
_hybrid_judgment_service: Optional[HybridJudgmentService] = None


def get_hybrid_judgment_service() -> HybridJudgmentService:
    """HybridJudgmentService 싱글톤 인스턴스"""
    global _hybrid_judgment_service
    if _hybrid_judgment_service is None:
        _hybrid_judgment_service = HybridJudgmentService()
    return _hybrid_judgment_service


    def _generate_recommended_actions(
        self,
        decision: str,
        rule_result: Optional[Dict[str, Any]] = None,
        llm_result: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        추천 조치 생성 (스펙 JUD-FR-050)

        결정에 따라 구체적이고 실행 가능한 액션 리스트 생성

        Returns:
            [
                {
                    "priority": "immediate|high|medium|low",
                    "action": "라인 A 생산 중단",
                    "reason": "불량률 임계 초과"
                },
                ...
            ]
        """
        actions = []

        # 1. 결정별 기본 액션
        if decision == "CRITICAL":
            actions.append({
                "priority": "immediate",
                "action": "생산 라인 즉시 중단",
                "reason": "치명적 상태 감지"
            })
            actions.append({
                "priority": "high",
                "action": "설비 점검 및 원인 분석",
                "reason": "문제 해결 필요"
            })
        elif decision == "WARNING":
            actions.append({
                "priority": "high",
                "action": "설비 상태 모니터링 강화",
                "reason": "경고 수준 감지"
            })
            actions.append({
                "priority": "medium",
                "action": "최근 생산 배치 재검사",
                "reason": "품질 확인 필요"
            })
        elif decision == "OK":
            actions.append({
                "priority": "low",
                "action": "정상 운영 지속",
                "reason": "모든 지표 정상"
            })

        # 2. 룰 결과 기반 상세 액션
        if rule_result and rule_result.get("success"):
            result = rule_result.get("result", {})
            checks = result.get("checks", [])

            for check in checks:
                if check.get("status") in ["CRITICAL", "HIGH"]:
                    field = check.get("name", "unknown")
                    value = check.get("value")
                    threshold = check.get("threshold")

                    actions.append({
                        "priority": "high",
                        "action": f"{field} 값 조정 필요",
                        "reason": f"현재 {value}, 임계값 {threshold} 초과",
                        "field": field,
                        "current_value": value,
                        "threshold": threshold,
                    })

        # 3. LLM 결과 기반 액션 (있으면)
        if llm_result and llm_result.get("reasoning"):
            reasoning = llm_result.get("reasoning", "")
            if "점검" in reasoning or "inspect" in reasoning.lower():
                actions.append({
                    "priority": "medium",
                    "action": "설비 정밀 점검",
                    "reason": "AI 분석 결과 이상 징후 감지"
                })

        # 중복 제거 (priority 기준 정렬)
        priority_order = {"immediate": 0, "high": 1, "medium": 2, "low": 3}
        actions.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))

        return actions


def reset_hybrid_judgment_service():
    """테스트용 리셋"""
    global _hybrid_judgment_service
    _hybrid_judgment_service = None
