# -*- coding: utf-8 -*-
"""Canary Rollback Service

Canary 배포 롤백 및 Compensation 처리 서비스.

3가지 Compensation 전략:
1. ignore: v2 데이터 그대로 유지 (스키마 변경 없을 때)
2. mark_and_reprocess: v2 데이터 마킹 후 재처리 큐 등록
3. soft_delete: v2 데이터 소프트 삭제

롤백 흐름:
1. 배포 상태 변경 (canary -> rolled_back)
2. 이전 active 배포 복원
3. Compensation 전략 실행
4. 모든 할당 및 캐시 삭제
5. 알림 발송
"""
import logging
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import RuleDeployment
from app.models.canary import CanaryExecutionLog
from app.services.canary_assignment_service import CanaryAssignmentService

logger = logging.getLogger(__name__)

CompensationStrategy = Literal["ignore", "mark_and_reprocess", "soft_delete"]


class CanaryRollbackService:
    """Canary 롤백 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.assignment_service = CanaryAssignmentService(db)

    # ============================================
    # 롤백 실행
    # ============================================

    def execute_rollback(
        self,
        deployment_id: UUID,
        reason: str,
        *,
        compensation_strategy: Optional[CompensationStrategy] = None,
        triggered_by: Optional[str] = None,  # "auto", "manual", "circuit_breaker"
    ) -> dict:
        """
        롤백 실행.

        Returns:
            {
                "success": bool,
                "deployment_id": str,
                "previous_status": str,
                "rollback_to_version": int | None,
                "compensation_result": {...},
                "assignments_deleted": int,
                "executed_at": str,
            }
        """
        deployment = self.db.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()

        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        if deployment.status not in ("canary", "active"):
            raise ValueError(f"롤백 불가 상태입니다: {deployment.status}")

        previous_status = deployment.status

        # Compensation 전략 결정
        strategy = compensation_strategy or deployment.compensation_strategy or "ignore"

        # 1. 이전 active 배포 찾기
        previous_active = self.db.query(RuleDeployment).filter(
            RuleDeployment.ruleset_id == deployment.ruleset_id,
            RuleDeployment.deployment_id != deployment_id,
            RuleDeployment.status == "deprecated",
        ).order_by(RuleDeployment.deployed_at.desc()).first()

        # 2. Compensation 실행
        compensation_result = self._execute_compensation(
            deployment_id=deployment_id,
            strategy=strategy,
        )

        # 3. 배포 상태 변경
        deployment.status = "rolled_back"
        deployment.rolled_back_at = datetime.utcnow()
        deployment.rollback_reason = reason
        deployment.rollback_to = previous_active.version if previous_active else None

        # 메타데이터에 롤백 정보 추가
        metadata = deployment.deployment_metadata or {}
        metadata["rollback"] = {
            "reason": reason,
            "triggered_by": triggered_by or "unknown",
            "compensation_strategy": strategy,
            "previous_status": previous_status,
            "executed_at": datetime.utcnow().isoformat(),
        }
        deployment.deployment_metadata = metadata

        # 4. 이전 배포 복원
        if previous_active:
            previous_active.status = "active"
            logger.info(
                f"Restored previous deployment: {previous_active.deployment_id} "
                f"(version {previous_active.version})"
            )

        # 5. 할당 삭제
        assignments_deleted = self.assignment_service.delete_all_assignments(deployment_id)

        # 6. 캐시 무효화
        self.assignment_service.invalidate_deployment_cache(deployment_id)

        self.db.commit()
        self.db.refresh(deployment)

        logger.info(
            f"Rollback executed: deployment={deployment_id}, "
            f"reason={reason}, strategy={strategy}, "
            f"triggered_by={triggered_by}"
        )

        return {
            "success": True,
            "deployment_id": str(deployment_id),
            "previous_status": previous_status,
            "rollback_to_version": deployment.rollback_to,
            "compensation_result": compensation_result,
            "assignments_deleted": assignments_deleted,
            "executed_at": datetime.utcnow().isoformat(),
        }

    # ============================================
    # Compensation 전략
    # ============================================

    def _execute_compensation(
        self,
        deployment_id: UUID,
        strategy: CompensationStrategy,
    ) -> dict:
        """Compensation 전략 실행"""
        if strategy == "ignore":
            return self._compensation_ignore(deployment_id)
        elif strategy == "mark_and_reprocess":
            return self._compensation_mark_and_reprocess(deployment_id)
        elif strategy == "soft_delete":
            return self._compensation_soft_delete(deployment_id)
        else:
            raise ValueError(f"알 수 없는 Compensation 전략: {strategy}")

    def _compensation_ignore(self, deployment_id: UUID) -> dict:
        """ignore 전략: 아무 것도 하지 않음"""
        logger.info(f"Compensation strategy: ignore for {deployment_id}")
        return {
            "strategy": "ignore",
            "affected_count": 0,
            "message": "데이터 변경 없음",
        }

    def _compensation_mark_and_reprocess(self, deployment_id: UUID) -> dict:
        """mark_and_reprocess 전략: v2 데이터 마킹"""
        deployment = self.db.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()

        if not deployment:
            return {"strategy": "mark_and_reprocess", "affected_count": 0}

        # v2 실행 로그를 재처리 필요로 마킹
        affected = self.db.query(CanaryExecutionLog).filter(
            CanaryExecutionLog.deployment_id == deployment_id,
            CanaryExecutionLog.canary_version == "v2",
            CanaryExecutionLog.needs_reprocess == False,
        ).update({
            "needs_reprocess": True,
        })

        # JudgmentExecution 테이블의 관련 레코드도 마킹
        # (execution_metadata JSONB에 canary_version이 있는 경우)
        from sqlalchemy import text
        self.db.execute(text("""
            UPDATE core.judgment_executions
            SET execution_metadata = jsonb_set(
                COALESCE(execution_metadata, '{}'),
                '{needs_reprocess}',
                'true'
            )
            WHERE execution_metadata->>'canary_deployment_id' = :deployment_id
              AND execution_metadata->>'canary_version' = 'v2'
        """), {"deployment_id": str(deployment_id)})

        self.db.commit()

        logger.info(
            f"Compensation strategy: mark_and_reprocess for {deployment_id}, "
            f"marked {affected} execution logs"
        )

        return {
            "strategy": "mark_and_reprocess",
            "affected_count": affected,
            "message": f"{affected}개 실행 로그가 재처리 대기 상태로 마킹됨",
        }

    def _compensation_soft_delete(self, deployment_id: UUID) -> dict:
        """soft_delete 전략: v2 실행 로그 소프트 삭제"""
        # CanaryExecutionLog에 deleted_at 컬럼이 없으므로
        # 메타데이터에 deleted 플래그 추가
        affected = self.db.query(CanaryExecutionLog).filter(
            CanaryExecutionLog.deployment_id == deployment_id,
            CanaryExecutionLog.canary_version == "v2",
        ).count()

        # 실제로는 JSONB 메타데이터에 deleted 마킹
        self.db.query(CanaryExecutionLog).filter(
            CanaryExecutionLog.deployment_id == deployment_id,
            CanaryExecutionLog.canary_version == "v2",
        ).update({
            "rollback_safe": False,  # 롤백으로 인해 무효화됨
        }, synchronize_session=False)

        # JudgmentExecution도 마킹
        from sqlalchemy import text
        self.db.execute(text("""
            UPDATE core.judgment_executions
            SET execution_metadata = jsonb_set(
                COALESCE(execution_metadata, '{}'),
                '{soft_deleted}',
                'true'
            )
            WHERE execution_metadata->>'canary_deployment_id' = :deployment_id
              AND execution_metadata->>'canary_version' = 'v2'
        """), {"deployment_id": str(deployment_id)})

        self.db.commit()

        logger.info(
            f"Compensation strategy: soft_delete for {deployment_id}, "
            f"soft-deleted {affected} execution logs"
        )

        return {
            "strategy": "soft_delete",
            "affected_count": affected,
            "message": f"{affected}개 실행 로그가 소프트 삭제됨",
        }

    # ============================================
    # 재처리
    # ============================================

    def get_logs_to_reprocess(
        self,
        deployment_id: UUID,
        *,
        limit: int = 100,
    ) -> list[CanaryExecutionLog]:
        """재처리가 필요한 로그 조회"""
        return self.db.query(CanaryExecutionLog).filter(
            CanaryExecutionLog.deployment_id == deployment_id,
            CanaryExecutionLog.needs_reprocess == True,
            CanaryExecutionLog.reprocessed_at.is_(None),
        ).limit(limit).all()

    def mark_reprocessed(
        self,
        log_ids: list[UUID],
    ) -> int:
        """재처리 완료 마킹"""
        now = datetime.utcnow()
        affected = self.db.query(CanaryExecutionLog).filter(
            CanaryExecutionLog.log_id.in_(log_ids)
        ).update({
            "needs_reprocess": False,
            "reprocessed_at": now,
        }, synchronize_session=False)

        self.db.commit()
        return affected

    # ============================================
    # 롤백 조회
    # ============================================

    def get_rollback_history(
        self,
        tenant_id: UUID,
        *,
        ruleset_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RuleDeployment], int]:
        """롤백 이력 조회"""
        query = self.db.query(RuleDeployment).filter(
            RuleDeployment.tenant_id == tenant_id,
            RuleDeployment.status == "rolled_back",
        )

        if ruleset_id:
            query = query.filter(RuleDeployment.ruleset_id == ruleset_id)

        total = query.count()
        deployments = query.order_by(
            RuleDeployment.rolled_back_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()

        return deployments, total

    def get_rollback_stats(self, tenant_id: UUID) -> dict:
        """롤백 통계"""
        from sqlalchemy import func

        total_rollbacks = self.db.query(func.count(RuleDeployment.deployment_id)).filter(
            RuleDeployment.tenant_id == tenant_id,
            RuleDeployment.status == "rolled_back",
        ).scalar() or 0

        # 롤백 사유별 집계 (JSONB에서 triggered_by 추출)
        # 간단히 최근 롤백만 분석
        recent_rollbacks = self.db.query(RuleDeployment).filter(
            RuleDeployment.tenant_id == tenant_id,
            RuleDeployment.status == "rolled_back",
        ).order_by(RuleDeployment.rolled_back_at.desc()).limit(100).all()

        auto_count = sum(
            1 for d in recent_rollbacks
            if d.deployment_metadata.get("rollback", {}).get("triggered_by") == "auto"
        )
        manual_count = sum(
            1 for d in recent_rollbacks
            if d.deployment_metadata.get("rollback", {}).get("triggered_by") == "manual"
        )

        return {
            "total_rollbacks": total_rollbacks,
            "auto_rollbacks": auto_count,
            "manual_rollbacks": manual_count,
            "recent_count": len(recent_rollbacks),
        }
