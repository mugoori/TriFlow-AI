# -*- coding: utf-8 -*-
"""Deployments Router

Canary 배포 관리 API.

엔드포인트:
- POST   /deployments                    # 배포 생성
- GET    /deployments/{id}               # 배포 조회
- PUT    /deployments/{id}               # 배포 수정
- DELETE /deployments/{id}               # 배포 삭제
- POST   /deployments/{id}/start-canary  # Canary 시작
- POST   /deployments/{id}/promote       # 100% 승격
- POST   /deployments/{id}/rollback      # 롤백
- PUT    /deployments/{id}/traffic       # 트래픽 비율 조정
- GET    /deployments/{id}/assignments   # Sticky 할당 목록
- GET    /deployments/{id}/metrics       # 메트릭 조회
- GET    /deployments/{id}/comparison    # v1 vs v2 비교
- GET    /deployments/{id}/health        # 건강 상태

권한:
- deployments:read - 모든 역할 (viewer 이상)
- deployments:create - approver 이상
- deployments:approve - approver 이상 (start-canary, promote)
- deployments:rollback - approver 이상
- deployments:delete - admin만
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.services.canary_deployment_service import CanaryDeploymentService
from app.services.canary_assignment_service import CanaryAssignmentService
from app.services.canary_rollback_service import CanaryRollbackService
from app.services.deployment_metrics_service import DeploymentMetricsService
from app.utils.canary_circuit_breaker import CanaryCircuitBreaker
from app.services.rbac_service import (
    check_permission,
    require_admin,
)
from app.utils.errors import require_tenant_access
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentUpdate,
    DeploymentResponse,
    StartCanaryRequest,
    UpdateTrafficRequest,
    RollbackRequest,
    AssignmentListResponse,
    AssignmentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deployments", tags=["deployments"])


# ============================================
# 배포 CRUD
# ============================================

@router.post("", response_model=DeploymentResponse)
async def create_deployment(
    request: DeploymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "create")),
):
    """배포 생성 (approver 이상)"""
    service = CanaryDeploymentService(db)
    try:
        deployment = service.create_deployment(
            tenant_id=current_user.tenant_id,
            request=request,
            created_by=current_user.user_id,
        )
        return DeploymentResponse.model_validate(deployment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[DeploymentResponse])
async def list_deployments(
    ruleset_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "read")),
):
    """배포 목록 조회 (viewer 이상)"""
    service = CanaryDeploymentService(db)
    deployments, _ = service.list_deployments(
        tenant_id=current_user.tenant_id,
        ruleset_id=ruleset_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return [DeploymentResponse.model_validate(d) for d in deployments]


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "read")),
):
    """배포 조회 (viewer 이상)"""
    service = CanaryDeploymentService(db)
    deployment = require_tenant_access(
        service.get_deployment(deployment_id),
        current_user.tenant_id,
        "배포",
    )
    return DeploymentResponse.model_validate(deployment)


@router.put("/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: UUID,
    request: DeploymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "create")),
):
    """배포 수정 (draft 상태에서만, approver 이상)"""
    service = CanaryDeploymentService(db)
    require_tenant_access(
        service.get_deployment(deployment_id),
        current_user.tenant_id,
        "배포",
    )

    try:
        updated = service.update_deployment(deployment_id, request)
        return DeploymentResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{deployment_id}")
async def delete_deployment(
    deployment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin),
):
    """배포 삭제 (admin만)"""
    service = CanaryDeploymentService(db)
    require_tenant_access(
        service.get_deployment(deployment_id),
        current_user.tenant_id,
        "배포",
    )

    try:
        service.delete_deployment(deployment_id)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Canary 라이프사이클
# ============================================

@router.post("/{deployment_id}/start-canary", response_model=DeploymentResponse)
async def start_canary(
    deployment_id: UUID,
    request: StartCanaryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "approve")),
):
    """Canary 배포 시작 (approver 이상)"""
    service = CanaryDeploymentService(db)
    deployment = service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    try:
        updated = service.start_canary(
            deployment_id=deployment_id,
            canary_pct=request.canary_pct,
            canary_target_filter=request.canary_target_filter,
            approver_id=current_user.user_id,
        )
        return DeploymentResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{deployment_id}/traffic", response_model=DeploymentResponse)
async def update_traffic(
    deployment_id: UUID,
    request: UpdateTrafficRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "approve")),
):
    """트래픽 비율 조정 (approver 이상)"""
    service = CanaryDeploymentService(db)
    deployment = service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    try:
        updated = service.update_traffic(deployment_id, request.canary_pct)
        return DeploymentResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/promote", response_model=DeploymentResponse)
async def promote_deployment(
    deployment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "approve")),
):
    """Canary를 100% 승격 (approver 이상)"""
    service = CanaryDeploymentService(db)
    deployment = service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    try:
        updated = service.promote(deployment_id)
        return DeploymentResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: UUID,
    request: RollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "rollback")),
):
    """롤백 (approver 이상)"""
    service = CanaryRollbackService(db)

    # 권한 확인
    deployment_service = CanaryDeploymentService(db)
    deployment = deployment_service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    try:
        result = service.execute_rollback(
            deployment_id=deployment_id,
            reason=request.reason,
            compensation_strategy=request.compensation_strategy,
            triggered_by="manual",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# 할당 관리
# ============================================

@router.get("/{deployment_id}/assignments", response_model=AssignmentListResponse)
async def list_assignments(
    deployment_id: UUID,
    identifier_type: Optional[str] = Query(None),
    version: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sticky 할당 목록"""
    # 권한 확인
    deployment_service = CanaryDeploymentService(db)
    deployment = deployment_service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    assignment_service = CanaryAssignmentService(db)
    assignments, total = assignment_service.list_assignments(
        deployment_id=deployment_id,
        identifier_type=identifier_type,
        version=version,
        page=page,
        page_size=page_size,
    )

    return AssignmentListResponse(
        assignments=[AssignmentResponse.model_validate(a) for a in assignments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{deployment_id}/assignments/stats")
async def get_assignment_stats(
    deployment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """할당 통계"""
    deployment_service = CanaryDeploymentService(db)
    deployment = deployment_service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    assignment_service = CanaryAssignmentService(db)
    return assignment_service.get_assignment_stats(deployment_id)


# ============================================
# 메트릭
# ============================================

@router.get("/{deployment_id}/metrics")
async def get_metrics(
    deployment_id: UUID,
    version_type: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """메트릭 히스토리 조회"""
    deployment_service = CanaryDeploymentService(db)
    deployment = deployment_service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    metrics_service = DeploymentMetricsService(db)
    metrics = metrics_service.get_metrics_history(
        deployment_id=deployment_id,
        version_type=version_type,
        hours=hours,
    )
    return [m.to_dict() for m in metrics]


@router.get("/{deployment_id}/comparison")
async def compare_metrics(
    deployment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """v1 vs v2 메트릭 비교"""
    deployment_service = CanaryDeploymentService(db)
    deployment = deployment_service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    metrics_service = DeploymentMetricsService(db)
    try:
        return metrics_service.compare_metrics(deployment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{deployment_id}/health")
async def get_health(
    deployment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """배포 건강 상태"""
    deployment_service = CanaryDeploymentService(db)
    deployment = deployment_service.get_deployment(deployment_id)
    if not deployment or deployment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="배포를 찾을 수 없습니다")

    circuit_breaker = CanaryCircuitBreaker(db)
    try:
        status = circuit_breaker.check(deployment_id, current_user.tenant_id)
        return status.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# 롤백 이력
# ============================================

@router.get("/rollback-history")
async def get_rollback_history(
    ruleset_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "read")),
):
    """롤백 이력 조회 (viewer 이상)"""
    rollback_service = CanaryRollbackService(db)
    deployments, total = rollback_service.get_rollback_history(
        tenant_id=current_user.tenant_id,
        ruleset_id=ruleset_id,
        page=page,
        page_size=page_size,
    )
    return {
        "deployments": [DeploymentResponse.model_validate(d) for d in deployments],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/rollback-stats")
async def get_rollback_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_permission("deployments", "read")),
):
    """롤백 통계 (viewer 이상)"""
    rollback_service = CanaryRollbackService(db)
    return rollback_service.get_rollback_stats(current_user.tenant_id)
