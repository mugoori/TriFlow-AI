# -*- coding: utf-8 -*-
"""Canary Monitor Task

백그라운드에서 Canary 배포를 모니터링하고 자동 롤백을 트리거하는 태스크.

실행 주기: 30초
동작:
1. 활성 Canary 배포 조회
2. 각 배포의 Circuit Breaker 상태 확인
3. 자동 롤백 조건 충족 시 롤백 실행
4. 경고 상태 시 알림 발송
"""
import asyncio
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import RuleDeployment
from app.utils.canary_circuit_breaker import CanaryCircuitBreaker, CanaryCircuitState
from app.services.canary_rollback_service import CanaryRollbackService
from app.services.deployment_metrics_service import DeploymentMetricsService

logger = logging.getLogger(__name__)

# 모니터링 간격 (초)
MONITOR_INTERVAL = 30

# 태스크 상태
_monitor_running = False
_monitor_task: Optional[asyncio.Task] = None


async def monitor_canary_deployments():
    """Canary 배포 모니터링 메인 루프"""
    global _monitor_running

    logger.info("Canary monitor task started")
    _monitor_running = True

    while _monitor_running:
        try:
            await _check_all_deployments()
        except Exception as e:
            logger.error(f"Canary monitor error: {e}", exc_info=True)

        await asyncio.sleep(MONITOR_INTERVAL)

    logger.info("Canary monitor task stopped")


async def _check_all_deployments():
    """모든 활성 Canary 배포 확인"""
    db: Session = SessionLocal()
    try:
        # 활성 Canary 배포 조회
        canary_deployments = db.query(RuleDeployment).filter(
            RuleDeployment.status == "canary",
        ).all()

        if not canary_deployments:
            return

        logger.debug(f"Checking {len(canary_deployments)} canary deployments")

        circuit_breaker = CanaryCircuitBreaker(db)
        rollback_service = CanaryRollbackService(db)
        metrics_service = DeploymentMetricsService(db)

        for deployment in canary_deployments:
            try:
                await _check_deployment(
                    deployment=deployment,
                    circuit_breaker=circuit_breaker,
                    rollback_service=rollback_service,
                    metrics_service=metrics_service,
                    db=db,
                )
            except Exception as e:
                logger.error(
                    f"Error checking deployment {deployment.deployment_id}: {e}",
                    exc_info=True,
                )
    finally:
        db.close()


async def _check_deployment(
    deployment: RuleDeployment,
    circuit_breaker: CanaryCircuitBreaker,
    rollback_service: CanaryRollbackService,
    metrics_service: DeploymentMetricsService,
    db: Session,
):
    """개별 배포 확인"""
    deployment_id = deployment.deployment_id
    tenant_id = deployment.tenant_id

    # 자동 롤백 비활성화 확인
    if not deployment.canary_auto_rollback_enabled:
        return

    # 메트릭 집계
    metrics_service.aggregate_metrics(deployment_id, tenant_id)

    # Circuit Breaker 상태 확인
    status = circuit_breaker.check(deployment_id, tenant_id)

    # 상태별 처리
    if status.state == CanaryCircuitState.CRITICAL and status.should_halt:
        # 자동 롤백 실행
        logger.warning(
            f"Auto-rollback triggered: deployment={deployment_id}, "
            f"reason={status.halt_reason}"
        )

        result = rollback_service.execute_rollback(
            deployment_id=deployment_id,
            reason=status.halt_reason or "Auto-rollback by circuit breaker",
            triggered_by="auto",
        )

        # 알림 발송 (TODO: 실제 알림 시스템 연동)
        await _send_rollback_notification(
            deployment=deployment,
            reason=status.halt_reason,
            result=result,
        )

    elif status.state == CanaryCircuitState.WARNING:
        # 경고 로깅
        logger.warning(
            f"Canary warning: deployment={deployment_id}, "
            f"warnings={status.warnings}"
        )
        # TODO: 경고 알림 발송


async def _send_rollback_notification(
    deployment: RuleDeployment,
    reason: Optional[str],
    result: dict,
):
    """롤백 알림 발송"""
    # TODO: 실제 알림 시스템 연동 (Slack, Email 등)
    logger.info(
        f"[NOTIFICATION] Canary auto-rollback completed:\n"
        f"  Deployment: {deployment.deployment_id}\n"
        f"  Ruleset: {deployment.ruleset_id}\n"
        f"  Reason: {reason}\n"
        f"  Rolled back to version: {result.get('rollback_to_version')}\n"
        f"  Compensation: {result.get('compensation_result', {}).get('strategy')}"
    )


# ============================================
# 태스크 관리
# ============================================

def start_monitor():
    """모니터 태스크 시작"""
    global _monitor_task

    if _monitor_task is not None and not _monitor_task.done():
        logger.warning("Canary monitor is already running")
        return

    _monitor_task = asyncio.create_task(monitor_canary_deployments())
    logger.info("Canary monitor task created")


def stop_monitor():
    """모니터 태스크 중지"""
    global _monitor_running, _monitor_task

    _monitor_running = False

    if _monitor_task is not None:
        _monitor_task.cancel()
        _monitor_task = None
        logger.info("Canary monitor task cancelled")


def is_monitor_running() -> bool:
    """모니터 실행 상태 확인"""
    return _monitor_running and _monitor_task is not None and not _monitor_task.done()


# ============================================
# 수동 실행 (테스트/디버그용)
# ============================================

async def check_deployment_manually(deployment_id):
    """특정 배포 수동 확인 (테스트용)"""
    from uuid import UUID

    if isinstance(deployment_id, str):
        deployment_id = UUID(deployment_id)

    db: Session = SessionLocal()
    try:
        deployment = db.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()

        if not deployment:
            return {"error": "배포를 찾을 수 없습니다"}

        circuit_breaker = CanaryCircuitBreaker(db)
        status = circuit_breaker.check(deployment_id, deployment.tenant_id)
        return status.to_dict()
    finally:
        db.close()
