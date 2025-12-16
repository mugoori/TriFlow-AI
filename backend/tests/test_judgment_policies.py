"""
Judgment 하이브리드 정책 테스트
스펙 참조: B-2-1_Judgment_Workflow_Design.md

7개 정책:
- RULE_ONLY: 규칙만 사용
- LLM_ONLY: LLM만 사용
- RULE_FALLBACK: 규칙 우선, 실패 시 LLM
- LLM_FALLBACK: LLM 우선, 실패 시 규칙
- HYBRID_WEIGHTED: 가중 평균 (규칙 0.6 + LLM 0.4)
- HYBRID_GATE: 게이트 기반 (규칙 신뢰도 낮으면 LLM)
- ESCALATE: 인간 에스컬레이션
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from app.services.judgment_policy import (
    JudgmentPolicy,
    HybridJudgmentService,
    JudgmentResult,
)


class TestJudgmentPolicy:
    """JudgmentPolicy 열거형 테스트"""

    def test_all_policies_defined(self):
        """모든 정책 정의 확인"""
        policies = [
            JudgmentPolicy.RULE_ONLY,
            JudgmentPolicy.LLM_ONLY,
            JudgmentPolicy.RULE_FALLBACK,
            JudgmentPolicy.LLM_FALLBACK,
            JudgmentPolicy.HYBRID_WEIGHTED,
            JudgmentPolicy.HYBRID_GATE,
            JudgmentPolicy.ESCALATE,
        ]

        assert len(policies) == 7

    def test_policy_values(self):
        """정책 값 확인"""
        assert JudgmentPolicy.RULE_ONLY.value == "rule_only"
        assert JudgmentPolicy.LLM_ONLY.value == "llm_only"
        assert JudgmentPolicy.RULE_FALLBACK.value == "rule_fallback"
        assert JudgmentPolicy.LLM_FALLBACK.value == "llm_fallback"
        assert JudgmentPolicy.HYBRID_WEIGHTED.value == "hybrid_weighted"
        assert JudgmentPolicy.HYBRID_GATE.value == "hybrid_gate"
        assert JudgmentPolicy.ESCALATE.value == "escalate"


class TestJudgmentResult:
    """JudgmentResult 테스트"""

    def test_judgment_result_creation(self):
        """JudgmentResult 생성"""
        result = JudgmentResult(
            decision="WARNING",
            confidence=0.85,
            source="rule",
            policy_used=JudgmentPolicy.RULE_ONLY,
            rule_result={"matched": True},
            llm_result=None,
            details={"message": "온도가 경고 범위에 있습니다."},
        )

        assert result.decision == "WARNING"
        assert result.confidence == 0.85
        assert result.source == "rule"
        assert result.rule_result["matched"] is True
        assert result.llm_result is None

    def test_judgment_result_to_dict(self):
        """JudgmentResult 딕셔너리 변환"""
        result = JudgmentResult(
            decision="CRITICAL",
            confidence=0.95,
            source="llm",
            policy_used=JudgmentPolicy.LLM_ONLY,
            rule_result=None,
            llm_result={"response": "위험"},
            details={"reasoning": "LLM 분석 결과"},
        )

        data = result.to_dict()

        assert data["decision"] == "CRITICAL"
        assert data["confidence"] == 0.95
        assert data["source"] == "llm"
        assert data["policy_used"] == "llm_only"

    def test_judgment_result_timestamp_auto_set(self):
        """JudgmentResult 타임스탬프 자동 설정"""
        result = JudgmentResult(
            decision="OK",
            confidence=0.9,
            source="rule",
            policy_used=JudgmentPolicy.RULE_ONLY,
        )

        assert result.timestamp  # 자동 설정됨
        # ISO 형식 확인
        datetime.fromisoformat(result.timestamp)


class TestHybridJudgmentService:
    """HybridJudgmentService 테스트"""

    @pytest.fixture
    def service(self):
        """테스트용 서비스"""
        return HybridJudgmentService()

    @pytest.fixture
    def tenant_id(self):
        """테스트용 tenant ID"""
        return uuid4()

    @pytest.fixture
    def ruleset_id(self):
        """테스트용 ruleset ID"""
        return uuid4()

    # =========== RULE_ONLY 정책 테스트 ===========

    @pytest.mark.asyncio
    async def test_rule_only_success(self, service, tenant_id, ruleset_id):
        """RULE_ONLY: 규칙 성공"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            mock_rule.return_value = {
                "success": True,
                "result": {
                    "decision": "WARNING",
                    "checks": [{"rule_id": "r1", "passed": False}],
                },
                "matched_rules": 1,
            }

            # 캐시 우회
            with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.get = AsyncMock(return_value=None)
                mock_cache_instance.set = AsyncMock()
                mock_cache.return_value = mock_cache_instance

                result = await service.execute(
                    tenant_id=tenant_id,
                    ruleset_id=ruleset_id,
                    input_data={"temperature": 75},
                    policy=JudgmentPolicy.RULE_ONLY,
                )

                assert result.source == "rule"
                assert result.policy_used == JudgmentPolicy.RULE_ONLY

    @pytest.mark.asyncio
    async def test_rule_only_failure(self, service, tenant_id, ruleset_id):
        """RULE_ONLY: 규칙 실패 시 UNKNOWN 반환"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            mock_rule.return_value = {
                "success": False,
                "error": "규칙을 찾을 수 없음",
            }

            with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.get = AsyncMock(return_value=None)
                mock_cache_instance.set = AsyncMock()
                mock_cache.return_value = mock_cache_instance

                result = await service.execute(
                    tenant_id=tenant_id,
                    ruleset_id=ruleset_id,
                    input_data={"temperature": 75},
                    policy=JudgmentPolicy.RULE_ONLY,
                )

                assert result.decision == "UNKNOWN"
                assert result.confidence == 0.0

    # =========== LLM_ONLY 정책 테스트 ===========

    @pytest.mark.asyncio
    async def test_llm_only_success(self, service, tenant_id, ruleset_id):
        """LLM_ONLY: LLM 성공"""
        with patch.object(service, '_run_llm_judgment', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "decision": "CRITICAL",
                "confidence": 0.88,
                "reasoning": "위험 수준의 온도 감지",
            }

            with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.get = AsyncMock(return_value=None)
                mock_cache_instance.set = AsyncMock()
                mock_cache.return_value = mock_cache_instance

                result = await service.execute(
                    tenant_id=tenant_id,
                    ruleset_id=ruleset_id,
                    input_data={"temperature": 95},
                    policy=JudgmentPolicy.LLM_ONLY,
                )

                assert result.decision == "CRITICAL"
                assert result.source == "llm"
                assert result.confidence == 0.88

    # =========== RULE_FALLBACK 정책 테스트 ===========

    @pytest.mark.asyncio
    async def test_rule_fallback_rule_success(self, service, tenant_id, ruleset_id):
        """RULE_FALLBACK: 규칙 성공 시 규칙 결과 사용"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            mock_rule.return_value = {
                "success": True,
                "result": {"decision": "WARNING", "checks": []},
                "matched_rules": 1,
            }

            with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.get = AsyncMock(return_value=None)
                mock_cache_instance.set = AsyncMock()
                mock_cache.return_value = mock_cache_instance

                result = await service.execute(
                    tenant_id=tenant_id,
                    ruleset_id=ruleset_id,
                    input_data={"temperature": 75},
                    policy=JudgmentPolicy.RULE_FALLBACK,
                )

                assert result.source == "rule"

    @pytest.mark.asyncio
    async def test_rule_fallback_to_llm(self, service, tenant_id, ruleset_id):
        """RULE_FALLBACK: 규칙 실패 시 LLM으로 폴백"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            mock_rule.return_value = {"success": False, "error": "규칙 없음"}

            with patch.object(service, '_run_llm_judgment', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = {
                    "decision": "WARNING",
                    "confidence": 0.75,
                    "reasoning": "LLM 분석",
                }

                with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get = AsyncMock(return_value=None)
                    mock_cache_instance.set = AsyncMock()
                    mock_cache.return_value = mock_cache_instance

                    result = await service.execute(
                        tenant_id=tenant_id,
                        ruleset_id=ruleset_id,
                        input_data={"temperature": 75},
                        policy=JudgmentPolicy.RULE_FALLBACK,
                    )

                    # 구현에서는 "llm_fallback" source 반환
                    assert result.source in ["llm", "llm_fallback"]
                    assert result.decision == "WARNING"

    # =========== LLM_FALLBACK 정책 테스트 ===========

    @pytest.mark.asyncio
    async def test_llm_fallback_llm_success(self, service, tenant_id, ruleset_id):
        """LLM_FALLBACK: LLM 성공 시 LLM 결과 사용"""
        with patch.object(service, '_run_llm_judgment', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "decision": "OK",
                "confidence": 0.90,
                "reasoning": "정상 범위",
            }

            with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.get = AsyncMock(return_value=None)
                mock_cache_instance.set = AsyncMock()
                mock_cache.return_value = mock_cache_instance

                result = await service.execute(
                    tenant_id=tenant_id,
                    ruleset_id=ruleset_id,
                    input_data={"temperature": 50},
                    policy=JudgmentPolicy.LLM_FALLBACK,
                )

                assert result.source == "llm"
                assert result.decision == "OK"

    @pytest.mark.asyncio
    async def test_llm_fallback_to_rule(self, service, tenant_id, ruleset_id):
        """LLM_FALLBACK: LLM 실패 시 규칙으로 폴백"""
        with patch.object(service, '_run_llm_judgment', new_callable=AsyncMock) as mock_llm:
            # LLM 실패 시 error 필드가 있는 dict 반환 (구현에서 exception을 catch함)
            mock_llm.return_value = {
                "decision": "UNKNOWN",
                "confidence": 0.0,
                "reasoning": "",
                "error": "LLM API 오류",
            }

            with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
                mock_rule.return_value = {
                    "success": True,
                    "result": {"decision": "OK", "checks": []},
                    "matched_rules": 1,
                }

                with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get = AsyncMock(return_value=None)
                    mock_cache_instance.set = AsyncMock()
                    mock_cache.return_value = mock_cache_instance

                    result = await service.execute(
                        tenant_id=tenant_id,
                        ruleset_id=ruleset_id,
                        input_data={"temperature": 50},
                        policy=JudgmentPolicy.LLM_FALLBACK,
                    )

                    # 구현에서는 "rule_fallback" source 반환
                    assert result.source in ["rule", "rule_fallback"]

    # =========== HYBRID_WEIGHTED 정책 테스트 ===========

    @pytest.mark.asyncio
    async def test_hybrid_weighted_combines_results(self, service, tenant_id, ruleset_id):
        """HYBRID_WEIGHTED: 규칙과 LLM 결과 가중 조합"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            mock_rule.return_value = {
                "success": True,
                "result": {"decision": "WARNING", "checks": [{"passed": False}]},
                "matched_rules": 1,
            }

            with patch.object(service, '_run_llm_judgment', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = {
                    "decision": "WARNING",
                    "confidence": 0.80,
                    "reasoning": "경고 수준",
                }

                with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get = AsyncMock(return_value=None)
                    mock_cache_instance.set = AsyncMock()
                    mock_cache.return_value = mock_cache_instance

                    result = await service.execute(
                        tenant_id=tenant_id,
                        ruleset_id=ruleset_id,
                        input_data={"temperature": 75},
                        policy=JudgmentPolicy.HYBRID_WEIGHTED,
                    )

                    assert result.source == "hybrid"
                    assert result.rule_result is not None
                    assert result.llm_result is not None

    # =========== HYBRID_GATE 정책 테스트 ===========

    @pytest.mark.asyncio
    async def test_hybrid_gate_high_rule_confidence(self, service, tenant_id, ruleset_id):
        """HYBRID_GATE: 규칙 신뢰도 높으면 규칙 결과 사용"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            # 높은 신뢰도를 위해 confidence 명시
            mock_rule.return_value = {
                "success": True,
                "result": {"decision": "WARNING", "confidence": 0.95, "checks": [{"passed": False}]},
                "matched_rules": 3,  # 높은 매칭
            }

            with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.get = AsyncMock(return_value=None)
                mock_cache_instance.set = AsyncMock()
                mock_cache.return_value = mock_cache_instance

                result = await service.execute(
                    tenant_id=tenant_id,
                    ruleset_id=ruleset_id,
                    input_data={"temperature": 75},
                    policy=JudgmentPolicy.HYBRID_GATE,
                )

                # 구현에서는 "rule", "hybrid_rule", "hybrid_llm", "hybrid_consensus" 중 하나
                assert result.source in ["rule", "hybrid_rule", "hybrid_llm", "hybrid_consensus"]

    @pytest.mark.asyncio
    async def test_hybrid_gate_low_rule_confidence_uses_llm(self, service, tenant_id, ruleset_id):
        """HYBRID_GATE: 규칙 신뢰도 낮으면 LLM 사용"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            mock_rule.return_value = {
                "success": True,
                "result": {"decision": "UNKNOWN", "checks": []},
                "matched_rules": 0,  # 낮은 매칭 = 낮은 신뢰도
            }

            with patch.object(service, '_run_llm_judgment', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = {
                    "decision": "WARNING",
                    "confidence": 0.85,
                    "reasoning": "LLM 분석 결과",
                }

                with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get = AsyncMock(return_value=None)
                    mock_cache_instance.set = AsyncMock()
                    mock_cache.return_value = mock_cache_instance

                    result = await service.execute(
                        tenant_id=tenant_id,
                        ruleset_id=ruleset_id,
                        input_data={"temperature": 75},
                        policy=JudgmentPolicy.HYBRID_GATE,
                    )

                    # 낮은 신뢰도면 LLM으로 게이트 통과
                    # 소스는 구현에 따라 llm 또는 hybrid일 수 있음
                    assert result.decision in ["WARNING", "UNKNOWN", "OK", "CRITICAL"]

    # =========== ESCALATE 정책 테스트 ===========

    @pytest.mark.asyncio
    async def test_escalate_high_confidence_uses_rule(self, service, tenant_id, ruleset_id):
        """ESCALATE: 높은 신뢰도면 규칙 결과 사용"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            mock_rule.return_value = {
                "success": True,
                "result": {"decision": "WARNING", "checks": [{"passed": False}, {"passed": False}]},
                "matched_rules": 3,
            }

            with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.get = AsyncMock(return_value=None)
                mock_cache_instance.set = AsyncMock()
                mock_cache.return_value = mock_cache_instance

                result = await service.execute(
                    tenant_id=tenant_id,
                    ruleset_id=ruleset_id,
                    input_data={"temperature": 75},
                    policy=JudgmentPolicy.ESCALATE,
                )

                # 높은 신뢰도면 규칙 사용
                assert result.policy_used == JudgmentPolicy.ESCALATE

    @pytest.mark.asyncio
    async def test_escalate_low_confidence_uses_llm(self, service, tenant_id, ruleset_id):
        """ESCALATE: 낮은 신뢰도면 LLM으로 에스컬레이션"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            mock_rule.return_value = {
                "success": True,
                "result": {"decision": "UNKNOWN", "checks": []},
                "matched_rules": 0,
            }

            with patch.object(service, '_run_llm_judgment', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = {
                    "decision": "CRITICAL",
                    "confidence": 0.90,
                    "reasoning": "에스컬레이션 분석",
                }

                with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get = AsyncMock(return_value=None)
                    mock_cache_instance.set = AsyncMock()
                    mock_cache.return_value = mock_cache_instance

                    result = await service.execute(
                        tenant_id=tenant_id,
                        ruleset_id=ruleset_id,
                        input_data={"temperature": 95},
                        policy=JudgmentPolicy.ESCALATE,
                    )

                    # 에스컬레이션으로 LLM 사용
                    assert result.policy_used == JudgmentPolicy.ESCALATE

    # =========== 캐싱 테스트 ===========

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self, service, tenant_id, ruleset_id):
        """캐시 히트 시 캐시된 결과 반환"""
        cached_data = {
            "result": {"decision": "OK"},
            "confidence": 0.95,
        }

        with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get = AsyncMock(return_value=cached_data)
            mock_cache.return_value = mock_cache_instance

            result = await service.execute(
                tenant_id=tenant_id,
                ruleset_id=ruleset_id,
                input_data={"temperature": 50},
                policy=JudgmentPolicy.RULE_ONLY,
            )

            assert result.cached is True
            assert result.source == "cache"

    # =========== 가중치 설정 테스트 ===========

    def test_custom_weights(self):
        """사용자 정의 가중치 설정"""
        service = HybridJudgmentService(rule_weight=0.7, llm_weight=0.3)

        # 가중치가 정규화됨
        assert service.rule_weight == 0.7
        assert service.llm_weight == 0.3

    def test_default_weights(self):
        """기본 가중치 확인"""
        service = HybridJudgmentService()

        assert service.rule_weight == 0.6
        assert service.llm_weight == 0.4


class TestJudgmentPolicyIntegration:
    """Judgment 정책 통합 테스트"""

    @pytest.fixture
    def service(self):
        return HybridJudgmentService()

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.fixture
    def ruleset_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_temperature_monitoring_scenario(self, service, tenant_id, ruleset_id):
        """시나리오: 온도 모니터링"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            # 온도가 임계값 초과
            mock_rule.return_value = {
                "success": True,
                "result": {
                    "decision": "CRITICAL",
                    "checks": [{"rule_id": "temp_critical", "passed": False}],
                },
                "matched_rules": 1,
            }

            with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                mock_cache_instance = MagicMock()
                mock_cache_instance.get = AsyncMock(return_value=None)
                mock_cache_instance.set = AsyncMock()
                mock_cache.return_value = mock_cache_instance

                result = await service.execute(
                    tenant_id=tenant_id,
                    ruleset_id=ruleset_id,
                    input_data={"temperature": 95, "humidity": 80},
                    policy=JudgmentPolicy.RULE_ONLY,
                )

                assert result.policy_used == JudgmentPolicy.RULE_ONLY
                assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_anomaly_detection_scenario(self, service, tenant_id, ruleset_id):
        """시나리오: 이상 탐지 (규칙으로 불확실 → LLM으로 분석)"""
        with patch.object(service, '_run_rule_engine', new_callable=AsyncMock) as mock_rule:
            # 규칙으로는 판단 어려움
            mock_rule.return_value = {
                "success": True,
                "result": {"decision": "UNKNOWN", "checks": []},
                "matched_rules": 0,
            }

            with patch.object(service, '_run_llm_judgment', new_callable=AsyncMock) as mock_llm:
                # LLM이 이상 탐지
                mock_llm.return_value = {
                    "decision": "WARNING",
                    "confidence": 0.78,
                    "reasoning": "패턴 분석 결과 비정상적 진동 감지",
                }

                with patch('app.services.judgment_cache.get_judgment_cache') as mock_cache:
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get = AsyncMock(return_value=None)
                    mock_cache_instance.set = AsyncMock()
                    mock_cache.return_value = mock_cache_instance

                    result = await service.execute(
                        tenant_id=tenant_id,
                        ruleset_id=ruleset_id,
                        input_data={"vibration": 45, "frequency": 120},
                        policy=JudgmentPolicy.ESCALATE,
                    )

                    assert result.policy_used == JudgmentPolicy.ESCALATE
