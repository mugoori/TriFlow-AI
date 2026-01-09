# -*- coding: utf-8 -*-
"""Canary Circuit Breaker

Canary 배포 전용 Circuit Breaker.

기존 circuit_breaker.py와 달리 DB 기반 메트릭을 사용하여
자동 롤백 판단을 수행합니다.

자동 롤백 조건 (하나라도 충족 시):
1. 절대 에러율 > 5%
2. 상대 에러율 > 2x (v1 대비)
3. P95 레이턴시 > 1.5x (v1 대비)
4. 연속 실패 >= 5회
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import RuleDeployment
from app.services.deployment_metrics_service import DeploymentMetricsService

logger = logging.getLogger(__name__)


class CanaryCircuitState(str, Enum):
    """Canary Circuit 상태"""
    HEALTHY = "healthy"          # 정상
    WARNING = "warning"          # 경고 (임계값 근접)
    CRITICAL = "critical"        # 위험 (자동 롤백 권장)
    HALTED = "halted"            # 중단됨


@dataclass
class CanaryCircuitConfig:
    """Canary Circuit Breaker 설정"""
    # 최소 샘플 수 (이 이상이어야 판단)
    min_samples: int = 100

    # 절대 에러율 임계값
    error_rate_threshold: float = 0.05  # 5%

    # 상대 에러율 임계값 (v1 대비)
    relative_error_threshold: float = 2.0  # 2x

    # P95 레이턴시 임계값 (v1 대비)
    latency_p95_threshold: float = 1.5  # 1.5x

    # 연속 실패 임계값
    consecutive_failure_threshold: int = 5

    # 경고 레벨 (임계값의 몇 % 이상이면 경고)
    warning_ratio: float = 0.7  # 70%

    @classmethod
    def from_deployment(cls, deployment: RuleDeployment) -> "CanaryCircuitConfig":
        """배포 설정에서 생성"""
        config = deployment.canary_config or {}
        return cls(
            min_samples=config.get("min_samples", 100),
            error_rate_threshold=config.get("error_rate_threshold", 0.05),
            relative_error_threshold=config.get("relative_error_threshold", 2.0),
            latency_p95_threshold=config.get("latency_p95_threshold", 1.5),
            consecutive_failure_threshold=config.get("consecutive_failure_threshold", 5),
        )


@dataclass
class CanaryCircuitStatus:
    """Canary Circuit 상태 정보"""
    deployment_id: UUID
    state: CanaryCircuitState
    should_halt: bool
    halt_reason: Optional[str]

    # 세부 정보
    canary_sample_count: int
    canary_error_rate: float
    stable_error_rate: Optional[float]
    error_rate_ratio: Optional[float]
    latency_p95_ratio: Optional[float]
    consecutive_failures: int

    # 경고
    warnings: list[str]

    checked_at: datetime

    def to_dict(self) -> dict:
        return {
            "deployment_id": str(self.deployment_id),
            "state": self.state.value,
            "should_halt": self.should_halt,
            "halt_reason": self.halt_reason,
            "canary_sample_count": self.canary_sample_count,
            "canary_error_rate": self.canary_error_rate,
            "stable_error_rate": self.stable_error_rate,
            "error_rate_ratio": self.error_rate_ratio,
            "latency_p95_ratio": self.latency_p95_ratio,
            "consecutive_failures": self.consecutive_failures,
            "warnings": self.warnings,
            "checked_at": self.checked_at.isoformat(),
        }


class CanaryCircuitBreaker:
    """Canary 배포 Circuit Breaker"""

    def __init__(self, db: Session):
        self.db = db
        self.metrics_service = DeploymentMetricsService(db)

    def check(
        self,
        deployment_id: UUID,
        tenant_id: UUID,
        *,
        config: Optional[CanaryCircuitConfig] = None,
    ) -> CanaryCircuitStatus:
        """
        Canary 배포 상태 확인.

        메트릭을 집계하고 Circuit 상태를 판단합니다.
        """
        deployment = self.db.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()

        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        if not deployment.is_canary_active:
            return CanaryCircuitStatus(
                deployment_id=deployment_id,
                state=CanaryCircuitState.HALTED,
                should_halt=False,
                halt_reason=None,
                canary_sample_count=0,
                canary_error_rate=0.0,
                stable_error_rate=None,
                error_rate_ratio=None,
                latency_p95_ratio=None,
                consecutive_failures=0,
                warnings=[],
                checked_at=datetime.utcnow(),
            )

        # 설정 로드
        if config is None:
            config = CanaryCircuitConfig.from_deployment(deployment)

        # 메트릭 집계
        stable_metrics, canary_metrics = self.metrics_service.aggregate_metrics(
            deployment_id=deployment_id,
            tenant_id=tenant_id,
        )

        # 기본값
        canary_sample_count = 0
        canary_error_rate = 0.0
        stable_error_rate = None
        error_rate_ratio = None
        latency_p95_ratio = None
        consecutive_failures = 0
        warnings: list[str] = []
        halt_reason: Optional[str] = None
        state = CanaryCircuitState.HEALTHY

        if canary_metrics:
            canary_sample_count = canary_metrics.sample_count
            canary_error_rate = float(canary_metrics.error_rate)
            consecutive_failures = canary_metrics.consecutive_failures

        if stable_metrics:
            stable_error_rate = float(stable_metrics.error_rate)

        # 최소 샘플 미달 시 판단 보류
        if canary_sample_count < config.min_samples:
            return CanaryCircuitStatus(
                deployment_id=deployment_id,
                state=CanaryCircuitState.HEALTHY,
                should_halt=False,
                halt_reason=None,
                canary_sample_count=canary_sample_count,
                canary_error_rate=canary_error_rate,
                stable_error_rate=stable_error_rate,
                error_rate_ratio=None,
                latency_p95_ratio=None,
                consecutive_failures=consecutive_failures,
                warnings=[f"샘플 수 부족: {canary_sample_count}/{config.min_samples}"],
                checked_at=datetime.utcnow(),
            )

        # 1. 절대 에러율 체크
        if canary_error_rate > config.error_rate_threshold:
            halt_reason = (
                f"절대 에러율 초과: {canary_error_rate*100:.2f}% > "
                f"{config.error_rate_threshold*100}%"
            )
            state = CanaryCircuitState.CRITICAL
        elif canary_error_rate > config.error_rate_threshold * config.warning_ratio:
            warnings.append(
                f"에러율 경고: {canary_error_rate*100:.2f}% "
                f"(임계값: {config.error_rate_threshold*100}%)"
            )
            state = CanaryCircuitState.WARNING

        # 2. 상대 에러율 체크
        if stable_error_rate is not None and stable_error_rate > 0:
            error_rate_ratio = canary_error_rate / stable_error_rate
            if error_rate_ratio > config.relative_error_threshold and not halt_reason:
                halt_reason = (
                    f"상대 에러율 초과: {error_rate_ratio:.2f}x > "
                    f"{config.relative_error_threshold}x"
                )
                state = CanaryCircuitState.CRITICAL
            elif (error_rate_ratio > config.relative_error_threshold * config.warning_ratio
                  and state != CanaryCircuitState.CRITICAL):
                warnings.append(
                    f"상대 에러율 경고: {error_rate_ratio:.2f}x "
                    f"(임계값: {config.relative_error_threshold}x)"
                )
                if state == CanaryCircuitState.HEALTHY:
                    state = CanaryCircuitState.WARNING

        # 3. P95 레이턴시 체크
        if (stable_metrics and canary_metrics and
            stable_metrics.latency_p95_ms and stable_metrics.latency_p95_ms > 0 and
            canary_metrics.latency_p95_ms):
            latency_p95_ratio = canary_metrics.latency_p95_ms / stable_metrics.latency_p95_ms
            if latency_p95_ratio > config.latency_p95_threshold and not halt_reason:
                halt_reason = (
                    f"P95 레이턴시 초과: {latency_p95_ratio:.2f}x > "
                    f"{config.latency_p95_threshold}x"
                )
                state = CanaryCircuitState.CRITICAL
            elif (latency_p95_ratio > config.latency_p95_threshold * config.warning_ratio
                  and state != CanaryCircuitState.CRITICAL):
                warnings.append(
                    f"P95 레이턴시 경고: {latency_p95_ratio:.2f}x "
                    f"(임계값: {config.latency_p95_threshold}x)"
                )
                if state == CanaryCircuitState.HEALTHY:
                    state = CanaryCircuitState.WARNING

        # 4. 연속 실패 체크
        if consecutive_failures >= config.consecutive_failure_threshold and not halt_reason:
            halt_reason = (
                f"연속 실패: {consecutive_failures}회 >= "
                f"{config.consecutive_failure_threshold}회"
            )
            state = CanaryCircuitState.CRITICAL
        elif (consecutive_failures >= config.consecutive_failure_threshold * config.warning_ratio
              and state != CanaryCircuitState.CRITICAL):
            warnings.append(
                f"연속 실패 경고: {consecutive_failures}회 "
                f"(임계값: {config.consecutive_failure_threshold}회)"
            )
            if state == CanaryCircuitState.HEALTHY:
                state = CanaryCircuitState.WARNING

        return CanaryCircuitStatus(
            deployment_id=deployment_id,
            state=state,
            should_halt=halt_reason is not None,
            halt_reason=halt_reason,
            canary_sample_count=canary_sample_count,
            canary_error_rate=canary_error_rate,
            stable_error_rate=stable_error_rate,
            error_rate_ratio=error_rate_ratio,
            latency_p95_ratio=latency_p95_ratio,
            consecutive_failures=consecutive_failures,
            warnings=warnings,
            checked_at=datetime.utcnow(),
        )

    def should_halt(
        self,
        deployment_id: UUID,
        tenant_id: UUID,
    ) -> tuple[bool, Optional[str]]:
        """
        Canary 중단 필요 여부 간단 확인.

        Returns:
            (should_halt, reason)
        """
        status = self.check(deployment_id, tenant_id)
        return status.should_halt, status.halt_reason
