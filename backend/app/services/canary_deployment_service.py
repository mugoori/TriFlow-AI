# -*- coding: utf-8 -*-
"""Canary Deployment Service

Canary 배포 관리 서비스.

주요 기능:
- 배포 생성/조회/수정
- Canary 시작/승격/롤백
- 트래픽 비율 조정
- AssignmentService와 연동
"""
import logging
from datetime import datetime
from typing import Optional, Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import RuleDeployment, Ruleset
from app.models.canary import CanaryAssignment, CanaryExecutionLog
from app.services.canary_assignment_service import CanaryAssignmentService
from app.schemas.deployment import (
    CanaryConfig,
    DeploymentCreate,
    DeploymentUpdate,
    CompensationStrategy,
)

logger = logging.getLogger(__name__)

DeploymentStatus = Literal["draft", "canary", "active", "rolled_back", "deprecated"]


class CanaryDeploymentService:
    """Canary 배포 관리 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.assignment_service = CanaryAssignmentService(db)

    # ============================================
    # 배포 CRUD
    # ============================================

    def create_deployment(
        self,
        tenant_id: UUID,
        request: DeploymentCreate,
        *,
        created_by: Optional[UUID] = None,
    ) -> RuleDeployment:
        """배포 생성"""
        # Ruleset 존재 확인
        ruleset = self.db.query(Ruleset).filter(
            Ruleset.ruleset_id == request.ruleset_id,
            Ruleset.tenant_id == tenant_id,
        ).first()
        if not ruleset:
            raise ValueError("Ruleset을 찾을 수 없습니다")

        deployment = RuleDeployment(
            tenant_id=tenant_id,
            ruleset_id=request.ruleset_id,
            version=request.version,
            status="draft",
            changelog=request.changelog,
            canary_config=request.canary_config.model_dump() if request.canary_config else {},
            compensation_strategy=request.compensation_strategy,
            deployment_metadata={"created_by": str(created_by)} if created_by else {},
        )
        self.db.add(deployment)
        self.db.commit()
        self.db.refresh(deployment)

        logger.info(f"Created deployment: {deployment.deployment_id}")
        return deployment

    def get_deployment(self, deployment_id: UUID) -> Optional[RuleDeployment]:
        """배포 조회"""
        return self.db.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()

    def get_deployment_by_ruleset(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
        status: Optional[DeploymentStatus] = None,
    ) -> Optional[RuleDeployment]:
        """Ruleset의 배포 조회"""
        query = self.db.query(RuleDeployment).filter(
            RuleDeployment.tenant_id == tenant_id,
            RuleDeployment.ruleset_id == ruleset_id,
        )
        if status:
            query = query.filter(RuleDeployment.status == status)
        return query.order_by(RuleDeployment.created_at.desc()).first()

    def list_deployments(
        self,
        tenant_id: UUID,
        *,
        ruleset_id: Optional[UUID] = None,
        status: Optional[DeploymentStatus] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[RuleDeployment], int]:
        """배포 목록 조회"""
        query = self.db.query(RuleDeployment).filter(
            RuleDeployment.tenant_id == tenant_id
        )

        if ruleset_id:
            query = query.filter(RuleDeployment.ruleset_id == ruleset_id)
        if status:
            query = query.filter(RuleDeployment.status == status)

        total = query.count()
        deployments = query.order_by(
            RuleDeployment.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()

        return deployments, total

    def update_deployment(
        self,
        deployment_id: UUID,
        request: DeploymentUpdate,
    ) -> RuleDeployment:
        """배포 수정 (draft 상태에서만)"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        if deployment.status != "draft":
            raise ValueError("draft 상태에서만 수정할 수 있습니다")

        if request.changelog is not None:
            deployment.changelog = request.changelog
        if request.canary_config is not None:
            deployment.canary_config = request.canary_config.model_dump()
        if request.compensation_strategy is not None:
            deployment.compensation_strategy = request.compensation_strategy

        self.db.commit()
        self.db.refresh(deployment)
        return deployment

    def delete_deployment(self, deployment_id: UUID) -> bool:
        """배포 삭제 (draft 상태에서만)"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return False

        if deployment.status not in ("draft", "rolled_back"):
            raise ValueError("draft 또는 rolled_back 상태에서만 삭제할 수 있습니다")

        self.db.delete(deployment)
        self.db.commit()
        return True

    # ============================================
    # Canary 라이프사이클
    # ============================================

    def start_canary(
        self,
        deployment_id: UUID,
        canary_pct: float,
        *,
        canary_target_filter: Optional[dict[str, Any]] = None,
        approver_id: Optional[UUID] = None,
    ) -> RuleDeployment:
        """Canary 배포 시작"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        if deployment.status != "draft":
            raise ValueError("draft 상태에서만 Canary를 시작할 수 있습니다")

        if not 0 < canary_pct <= 1:
            raise ValueError("canary_pct는 0 초과 1 이하여야 합니다")

        # 같은 Ruleset에 이미 canary 상태인 배포가 있는지 확인
        existing_canary = self.db.query(RuleDeployment).filter(
            RuleDeployment.ruleset_id == deployment.ruleset_id,
            RuleDeployment.status == "canary",
            RuleDeployment.deployment_id != deployment_id,
        ).first()
        if existing_canary:
            raise ValueError(
                f"이미 Canary 상태인 배포가 있습니다: {existing_canary.deployment_id}"
            )

        deployment.status = "canary"
        deployment.canary_pct = canary_pct
        deployment.canary_target_filter = canary_target_filter
        deployment.started_at = datetime.utcnow()
        deployment.approver_id = approver_id
        deployment.approved_at = datetime.utcnow() if approver_id else None

        self.db.commit()
        self.db.refresh(deployment)

        logger.info(
            f"Started canary deployment: {deployment_id}, "
            f"canary_pct={canary_pct*100}%"
        )
        return deployment

    def update_traffic(
        self,
        deployment_id: UUID,
        canary_pct: float,
    ) -> RuleDeployment:
        """트래픽 비율 조정"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        if deployment.status != "canary":
            raise ValueError("canary 상태에서만 트래픽을 조정할 수 있습니다")

        if not 0 <= canary_pct <= 1:
            raise ValueError("canary_pct는 0 이상 1 이하여야 합니다")

        old_pct = deployment.canary_pct
        deployment.canary_pct = canary_pct

        # 비율이 0이 되면 캐시 무효화 (기존 할당 유지, 신규만 영향)
        # 비율이 변경되어도 기존 Sticky Session 할당은 유지됨

        self.db.commit()
        self.db.refresh(deployment)

        logger.info(
            f"Updated canary traffic: {deployment_id}, "
            f"{old_pct*100 if old_pct else 0}% -> {canary_pct*100}%"
        )
        return deployment

    def promote(self, deployment_id: UUID) -> RuleDeployment:
        """Canary를 100% 승격 (active 상태로 전환)"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        if deployment.status != "canary":
            raise ValueError("canary 상태에서만 승격할 수 있습니다")

        # 기존 active 배포를 deprecated로 변경
        self.db.query(RuleDeployment).filter(
            RuleDeployment.ruleset_id == deployment.ruleset_id,
            RuleDeployment.status == "active",
        ).update({"status": "deprecated"})

        deployment.status = "active"
        deployment.canary_pct = 1.0  # 100%
        deployment.promoted_at = datetime.utcnow()
        deployment.deployed_at = datetime.utcnow()

        # 모든 할당 삭제 (더 이상 필요 없음)
        self.assignment_service.delete_all_assignments(deployment_id)

        # 캐시 무효화
        self.assignment_service.invalidate_deployment_cache(deployment_id)

        self.db.commit()
        self.db.refresh(deployment)

        logger.info(f"Promoted canary to active: {deployment_id}")
        return deployment

    def rollback(
        self,
        deployment_id: UUID,
        reason: str,
        *,
        compensation_strategy: Optional[CompensationStrategy] = None,
    ) -> RuleDeployment:
        """Canary 롤백"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError("배포를 찾을 수 없습니다")

        if deployment.status not in ("canary", "active"):
            raise ValueError("canary 또는 active 상태에서만 롤백할 수 있습니다")

        # 이전 active 버전 찾기
        previous_active = self.db.query(RuleDeployment).filter(
            RuleDeployment.ruleset_id == deployment.ruleset_id,
            RuleDeployment.status == "deprecated",
        ).order_by(RuleDeployment.deployed_at.desc()).first()

        deployment.status = "rolled_back"
        deployment.rolled_back_at = datetime.utcnow()
        deployment.rollback_reason = reason
        deployment.rollback_to = previous_active.version if previous_active else None

        if compensation_strategy:
            deployment.compensation_strategy = compensation_strategy

        # 이전 배포를 active로 복원
        if previous_active:
            previous_active.status = "active"

        # 모든 할당 삭제
        self.assignment_service.delete_all_assignments(deployment_id)

        # 캐시 무효화
        self.assignment_service.invalidate_deployment_cache(deployment_id)

        self.db.commit()
        self.db.refresh(deployment)

        logger.info(
            f"Rolled back deployment: {deployment_id}, "
            f"reason={reason}, rollback_to_version={deployment.rollback_to}"
        )
        return deployment

    # ============================================
    # 실행 로그
    # ============================================

    def record_execution(
        self,
        deployment_id: UUID,
        tenant_id: UUID,
        canary_version: Literal["v1", "v2"],
        success: bool,
        *,
        execution_id: Optional[UUID] = None,
        latency_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        rollback_safe: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CanaryExecutionLog:
        """실행 로그 기록"""
        log = CanaryExecutionLog(
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            execution_id=execution_id,
            canary_version=canary_version,
            success=success,
            latency_ms=latency_ms,
            error_message=error_message,
            rollback_safe=rollback_safe,
            execution_metadata=metadata or {},
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_execution_logs(
        self,
        deployment_id: UUID,
        *,
        version: Optional[Literal["v1", "v2"]] = None,
        success: Optional[bool] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[CanaryExecutionLog], int]:
        """실행 로그 조회"""
        query = self.db.query(CanaryExecutionLog).filter(
            CanaryExecutionLog.deployment_id == deployment_id
        )

        if version:
            query = query.filter(CanaryExecutionLog.canary_version == version)
        if success is not None:
            query = query.filter(CanaryExecutionLog.success == success)

        total = query.count()
        logs = query.order_by(
            CanaryExecutionLog.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()

        return logs, total

    # ============================================
    # 유틸리티
    # ============================================

    def get_active_deployment(
        self,
        tenant_id: UUID,
        ruleset_id: UUID,
    ) -> Optional[RuleDeployment]:
        """활성 배포 조회 (active 또는 canary)"""
        return self.db.query(RuleDeployment).filter(
            RuleDeployment.tenant_id == tenant_id,
            RuleDeployment.ruleset_id == ruleset_id,
            RuleDeployment.status.in_(["active", "canary"]),
        ).order_by(RuleDeployment.created_at.desc()).first()

    def get_canary_deployments(
        self,
        tenant_id: UUID,
    ) -> list[RuleDeployment]:
        """활성 Canary 배포 목록"""
        return self.db.query(RuleDeployment).filter(
            RuleDeployment.tenant_id == tenant_id,
            RuleDeployment.status == "canary",
        ).all()

    def is_canary_active(self, deployment_id: UUID) -> bool:
        """Canary 활성 상태 확인"""
        deployment = self.get_deployment(deployment_id)
        return deployment is not None and deployment.is_canary_active
