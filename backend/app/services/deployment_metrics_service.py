# -*- coding: utf-8 -*-
"""Deployment Metrics Service

Canary 배포 메트릭 수집 및 분석 서비스.

주요 기능:
- 시간 윈도우별 메트릭 집계
- v1/v2 성능 비교
- 통계적 유의성 판단
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Literal
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import RuleDeployment
from app.models.canary import DeploymentMetrics, CanaryExecutionLog

logger = logging.getLogger(__name__)


class DeploymentMetricsService:
    """배포 메트릭 서비스"""

    # 기본 윈도우 크기 (분)
    DEFAULT_WINDOW_MINUTES = 5

    def __init__(self, db: Session):
        self.db = db

    # ============================================
    # 메트릭 집계
    # ============================================

    def aggregate_metrics(
        self,
        deployment_id: UUID,
        tenant_id: UUID,
        *,
        window_minutes: int = DEFAULT_WINDOW_MINUTES,
    ) -> tuple[Optional[DeploymentMetrics], Optional[DeploymentMetrics]]:
        """
        현재 윈도우의 v1/v2 메트릭 집계.

        Returns:
            (stable_metrics, canary_metrics)
        """
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)

        stable_metrics = self._aggregate_version(
            deployment_id=deployment_id,
            tenant_id=tenant_id,
            version="v1",
            window_start=window_start,
            window_end=now,
        )

        canary_metrics = self._aggregate_version(
            deployment_id=deployment_id,
            tenant_id=tenant_id,
            version="v2",
            window_start=window_start,
            window_end=now,
        )

        return stable_metrics, canary_metrics

    def _aggregate_version(
        self,
        deployment_id: UUID,
        tenant_id: UUID,
        version: Literal["v1", "v2"],
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[DeploymentMetrics]:
        """특정 버전의 메트릭 집계"""
        # 윈도우 내 실행 로그 조회
        logs = self.db.query(CanaryExecutionLog).filter(
            CanaryExecutionLog.deployment_id == deployment_id,
            CanaryExecutionLog.canary_version == version,
            CanaryExecutionLog.created_at >= window_start,
            CanaryExecutionLog.created_at <= window_end,
        ).all()

        if not logs:
            return None

        # 집계
        sample_count = len(logs)
        success_count = sum(1 for log in logs if log.success)
        error_count = sample_count - success_count
        error_rate = error_count / sample_count if sample_count > 0 else 0

        # 레이턴시 계산
        latencies = [log.latency_ms for log in logs if log.latency_ms is not None]
        latency_p50, latency_p95, latency_p99, latency_avg = None, None, None, None

        if latencies:
            latencies_sorted = sorted(latencies)
            latency_avg = sum(latencies) // len(latencies)
            latency_p50 = self._percentile(latencies_sorted, 50)
            latency_p95 = self._percentile(latencies_sorted, 95)
            latency_p99 = self._percentile(latencies_sorted, 99)

        # 연속 실패 계산
        consecutive_failures = self._count_consecutive_failures(logs)

        # 메트릭 저장
        version_type = "stable" if version == "v1" else "canary"
        metrics = DeploymentMetrics(
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            version_type=version_type,
            sample_count=sample_count,
            success_count=success_count,
            error_count=error_count,
            error_rate=error_rate,
            latency_p50_ms=latency_p50,
            latency_p95_ms=latency_p95,
            latency_p99_ms=latency_p99,
            latency_avg_ms=latency_avg,
            consecutive_failures=consecutive_failures,
            window_start=window_start,
            window_end=window_end,
        )

        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)

        return metrics

    def _percentile(self, sorted_data: list[int], percentile: int) -> int:
        """퍼센타일 계산"""
        if not sorted_data:
            return 0
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = f + 1 if f < len(sorted_data) - 1 else f
        return (sorted_data[f] + sorted_data[c]) // 2

    def _count_consecutive_failures(self, logs: list[CanaryExecutionLog]) -> int:
        """최근 연속 실패 횟수"""
        # 최신 순으로 정렬
        sorted_logs = sorted(logs, key=lambda x: x.created_at, reverse=True)
        count = 0
        for log in sorted_logs:
            if not log.success:
                count += 1
            else:
                break
        return count

    # ============================================
    # 메트릭 비교
    # ============================================

    def compare_metrics(
        self,
        deployment_id: UUID,
        *,
        window_minutes: int = DEFAULT_WINDOW_MINUTES,
    ) -> dict:
        """
        v1/v2 메트릭 비교.

        Returns:
            {
                "deployment_id": ...,
                "stable": {...},
                "canary": {...},
                "error_rate_ratio": ...,
                "latency_p95_ratio": ...,
                "is_statistically_significant": ...,
                "should_halt": ...,
                "halt_reason": ...,
            }
        """
        deployment = self.db.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()

        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        # 최신 메트릭 조회
        stable_metrics = self._get_latest_metrics(deployment_id, "stable")
        canary_metrics = self._get_latest_metrics(deployment_id, "canary")

        result = {
            "deployment_id": str(deployment_id),
            "stable": stable_metrics.to_dict() if stable_metrics else None,
            "canary": canary_metrics.to_dict() if canary_metrics else None,
            "error_rate_ratio": None,
            "latency_p95_ratio": None,
            "is_statistically_significant": False,
            "should_halt": False,
            "halt_reason": None,
        }

        if not canary_metrics:
            return result

        # 통계적 유의성 확인
        min_samples = deployment.canary_min_samples
        if canary_metrics.sample_count >= min_samples:
            result["is_statistically_significant"] = True

        # 에러율 비율
        if stable_metrics and float(stable_metrics.error_rate) > 0:
            result["error_rate_ratio"] = (
                float(canary_metrics.error_rate) / float(stable_metrics.error_rate)
            )
        elif float(canary_metrics.error_rate) > 0:
            result["error_rate_ratio"] = float("inf")

        # 레이턴시 비율
        if (stable_metrics and stable_metrics.latency_p95_ms and
            stable_metrics.latency_p95_ms > 0 and canary_metrics.latency_p95_ms):
            result["latency_p95_ratio"] = (
                canary_metrics.latency_p95_ms / stable_metrics.latency_p95_ms
            )

        # Halt 판단
        halt_reason = self._should_halt(deployment, canary_metrics, stable_metrics)
        if halt_reason:
            result["should_halt"] = True
            result["halt_reason"] = halt_reason

        return result

    def _get_latest_metrics(
        self,
        deployment_id: UUID,
        version_type: Literal["stable", "canary"],
    ) -> Optional[DeploymentMetrics]:
        """최신 메트릭 조회"""
        return self.db.query(DeploymentMetrics).filter(
            DeploymentMetrics.deployment_id == deployment_id,
            DeploymentMetrics.version_type == version_type,
        ).order_by(DeploymentMetrics.window_end.desc()).first()

    def _should_halt(
        self,
        deployment: RuleDeployment,
        canary: DeploymentMetrics,
        stable: Optional[DeploymentMetrics],
    ) -> Optional[str]:
        """Canary 중단 판단"""
        config = deployment.canary_config
        min_samples = config.get("min_samples", 100)

        # 최소 샘플 미달
        if canary.sample_count < min_samples:
            return None

        # 1. 절대 에러율 임계값
        error_threshold = config.get("error_rate_threshold", 0.05)
        if float(canary.error_rate) > error_threshold:
            return f"절대 에러율 초과: {float(canary.error_rate)*100:.2f}% > {error_threshold*100}%"

        # 2. 상대 에러율 임계값
        relative_threshold = config.get("relative_error_threshold", 2.0)
        if stable and float(stable.error_rate) > 0:
            ratio = float(canary.error_rate) / float(stable.error_rate)
            if ratio > relative_threshold:
                return f"상대 에러율 초과: {ratio:.2f}x > {relative_threshold}x"

        # 3. P95 레이턴시 임계값
        latency_threshold = config.get("latency_p95_threshold", 1.5)
        if (stable and stable.latency_p95_ms and stable.latency_p95_ms > 0 and
            canary.latency_p95_ms):
            ratio = canary.latency_p95_ms / stable.latency_p95_ms
            if ratio > latency_threshold:
                return f"P95 레이턴시 초과: {ratio:.2f}x > {latency_threshold}x"

        # 4. 연속 실패 임계값
        consecutive_threshold = config.get("consecutive_failure_threshold", 5)
        if canary.consecutive_failures >= consecutive_threshold:
            return f"연속 실패: {canary.consecutive_failures}회 >= {consecutive_threshold}회"

        return None

    # ============================================
    # 건강 상태
    # ============================================

    def get_health_status(self, deployment_id: UUID) -> dict:
        """배포 건강 상태"""
        deployment = self.db.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()

        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        stable_metrics = self._get_latest_metrics(deployment_id, "stable")
        canary_metrics = self._get_latest_metrics(deployment_id, "canary")

        warnings = []
        errors = []

        # Circuit 상태 결정
        circuit_state = "closed"
        consecutive_failures = 0

        if canary_metrics:
            consecutive_failures = canary_metrics.consecutive_failures

            # 연속 실패가 임계값의 절반 이상이면 경고
            threshold = deployment.canary_config.get("consecutive_failure_threshold", 5)
            if consecutive_failures >= threshold:
                circuit_state = "open"
                errors.append(f"연속 실패 {consecutive_failures}회로 Circuit 열림")
            elif consecutive_failures >= threshold // 2:
                circuit_state = "half_open"
                warnings.append(f"연속 실패 {consecutive_failures}회 (경고)")

            # 에러율 경고
            error_rate = float(canary_metrics.error_rate)
            if error_rate > 0.03:  # 3% 이상이면 경고
                warnings.append(f"Canary 에러율 {error_rate*100:.2f}%")

        return {
            "deployment_id": str(deployment_id),
            "status": deployment.status,
            "is_healthy": len(errors) == 0,
            "circuit_state": circuit_state,
            "consecutive_failures": consecutive_failures,
            "stable_error_rate": float(stable_metrics.error_rate) if stable_metrics else None,
            "canary_error_rate": float(canary_metrics.error_rate) if canary_metrics else None,
            "warnings": warnings,
            "errors": errors,
            "last_checked_at": datetime.utcnow().isoformat(),
        }

    # ============================================
    # 기록 조회
    # ============================================

    def get_metrics_history(
        self,
        deployment_id: UUID,
        *,
        version_type: Optional[Literal["stable", "canary"]] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> list[DeploymentMetrics]:
        """메트릭 히스토리 조회"""
        since = datetime.utcnow() - timedelta(hours=hours)

        query = self.db.query(DeploymentMetrics).filter(
            DeploymentMetrics.deployment_id == deployment_id,
            DeploymentMetrics.window_end >= since,
        )

        if version_type:
            query = query.filter(DeploymentMetrics.version_type == version_type)

        return query.order_by(
            DeploymentMetrics.window_end.desc()
        ).limit(limit).all()

    def cleanup_old_metrics(self, days: int = 7) -> int:
        """오래된 메트릭 정리"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = self.db.query(DeploymentMetrics).filter(
            DeploymentMetrics.window_end < cutoff
        ).delete()
        self.db.commit()
        logger.info(f"Cleaned up {result} old metrics")
        return result
