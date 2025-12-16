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
from typing import Any, Dict, Optional
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
    """판단 결과"""
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
            return JudgmentResult(
                decision=self._extract_decision(rule_result),
                confidence=self._calculate_rule_confidence(rule_result),
                source="rule",
                policy_used=JudgmentPolicy.RULE_ONLY,
                rule_result=rule_result,
                details={"checks": rule_result.get("result", {}).get("checks", [])},
            )
        else:
            return JudgmentResult(
                decision="UNKNOWN",
                confidence=0.0,
                source="rule",
                policy_used=JudgmentPolicy.RULE_ONLY,
                rule_result=rule_result,
                details={"error": rule_result.get("error")},
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

        return JudgmentResult(
            decision=llm_result.get("decision", "UNKNOWN"),
            confidence=llm_result.get("confidence", 0.5),
            source="llm",
            policy_used=JudgmentPolicy.LLM_ONLY,
            llm_result=llm_result,
            details={"reasoning": llm_result.get("reasoning", "")},
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
        rule_confidence = self._calculate_rule_confidence(rule_result)

        # 2. 룰 신뢰도가 충분하면 룰 결과 사용
        if rule_result["success"] and rule_confidence >= self.RULE_CONFIDENCE_THRESHOLD:
            return JudgmentResult(
                decision=self._extract_decision(rule_result),
                confidence=rule_confidence,
                source="rule",
                policy_used=JudgmentPolicy.ESCALATE,
                rule_result=rule_result,
                details={"escalated": False},
            )

        # 3. 룰 불확실 → LLM으로 에스컬레이션
        logger.info(f"Escalating to LLM (rule confidence: {rule_confidence})")
        llm_result = await self._run_llm_judgment(tenant_id, input_data, context)

        return JudgmentResult(
            decision=llm_result.get("decision", "UNKNOWN"),
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
            return JudgmentResult(
                decision=self._extract_decision(rule_result),
                confidence=self._calculate_rule_confidence(rule_result),
                source="rule",
                policy_used=JudgmentPolicy.RULE_FALLBACK,
                rule_result=rule_result,
                details={"fallback_used": False},
            )

        # 3. 룰 실패 → LLM으로 폴백
        logger.info(f"Rule failed, falling back to LLM: {rule_result.get('error')}")
        llm_result = await self._run_llm_judgment(tenant_id, input_data, context)

        return JudgmentResult(
            decision=llm_result.get("decision", "UNKNOWN"),
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
            )

        # 3. LLM 실패 → 룰로 폴백
        logger.info(f"LLM failed or uncertain, falling back to Rule: {llm_error}")
        rule_result = await self._run_rule_engine(tenant_id, ruleset_id, input_data)

        if rule_result.get("success"):
            return JudgmentResult(
                decision=self._extract_decision(rule_result),
                confidence=self._calculate_rule_confidence(rule_result),
                source="rule_fallback",
                policy_used=JudgmentPolicy.LLM_FALLBACK,
                rule_result=rule_result,
                llm_result=llm_result,
                details={
                    "fallback_used": True,
                    "llm_error": llm_error,
                },
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
        rule_confidence = self._calculate_rule_confidence(rule_result)
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
        rule_confidence = self._calculate_rule_confidence(rule_result)
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

                return {
                    "success": True,
                    "ruleset_id": str(ruleset_id),
                    "ruleset_name": ruleset.name,
                    "result": result,
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

            # JSON 추출
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "decision": result.get("decision", "UNKNOWN"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "reasoning": result.get("reasoning", ""),
                    "raw_response": response_text,
                }

            return {
                "decision": "UNKNOWN",
                "confidence": 0.3,
                "reasoning": response_text,
                "error": "Failed to parse JSON response",
            }

        except Exception as e:
            logger.error(f"LLM judgment error: {e}")
            return {
                "decision": "UNKNOWN",
                "confidence": 0.0,
                "reasoning": "",
                "error": str(e),
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

    def _calculate_rule_confidence(self, rule_result: Dict[str, Any]) -> float:
        """룰 결과의 신뢰도 계산"""
        if not rule_result.get("success"):
            return 0.0

        result = rule_result.get("result", {})

        # 명시적 신뢰도가 있으면 사용
        if "confidence" in result:
            return float(result["confidence"])

        # checks 기반 신뢰도 계산
        checks = result.get("checks", [])
        if checks:
            # 체크 통과율 기반
            passed = sum(1 for c in checks if c.get("status") in ["OK", "NORMAL"])
            return 0.8 + (passed / len(checks)) * 0.2

        # 기본값: 룰이 성공적으로 실행되면 0.85
        return 0.85


# 전역 인스턴스
_hybrid_judgment_service: Optional[HybridJudgmentService] = None


def get_hybrid_judgment_service() -> HybridJudgmentService:
    """HybridJudgmentService 싱글톤 인스턴스"""
    global _hybrid_judgment_service
    if _hybrid_judgment_service is None:
        _hybrid_judgment_service = HybridJudgmentService()
    return _hybrid_judgment_service


def reset_hybrid_judgment_service():
    """테스트용 리셋"""
    global _hybrid_judgment_service
    _hybrid_judgment_service = None
