# -*- coding: utf-8 -*-
"""
Auto Execution Router

Trust-based 자동 실행 시스템 API 엔드포인트.

엔드포인트:
- GET    /api/v2/auto-execution/matrix                - Decision Matrix 조회
- PUT    /api/v2/auto-execution/matrix/{trust}/{risk} - Decision Matrix 업데이트
- POST   /api/v2/auto-execution/matrix/reset          - 기본값으로 리셋
- GET    /api/v2/auto-execution/risks                 - Action Risk 정의 목록
- POST   /api/v2/auto-execution/risks                 - Action Risk 정의 생성
- PUT    /api/v2/auto-execution/risks/{action_type}   - Action Risk 정의 업데이트
- DELETE /api/v2/auto-execution/risks/{action_type}   - Action Risk 정의 삭제
- POST   /api/v2/auto-execution/evaluate              - 실행 결정 평가
- GET    /api/v2/auto-execution/logs                  - 실행 로그 조회
- GET    /api/v2/auto-execution/pending               - 승인 대기 목록
- POST   /api/v2/auto-execution/logs/{log_id}/approve - 승인 처리
- GET    /api/v2/auto-execution/stats                 - 실행 통계
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.models import User
from app.services.decision_matrix_service import DecisionMatrixService
from app.services.action_risk_evaluator import ActionRiskEvaluator
from app.services.auto_execution_router import AutoExecutionRouter
from app.schemas.auto_execution import (
    DecisionMatrixEntry,
    DecisionMatrixUpdateRequest,
    DecisionMatrixResponse,
    ActionRiskDefinitionCreate,
    ActionRiskDefinitionUpdate,
    ActionRiskDefinitionResponse,
    ExecutionEvaluateRequest,
    ExecutionEvaluateResponse,
    AutoExecutionLogResponse,
    AutoExecutionLogListResponse,
    PendingApprovalResponse,
    ApprovalActionRequest,
    ExecutionStatsResponse,
    RiskSummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Decision Matrix 엔드포인트
# ============================================

@router.get("/matrix", response_model=DecisionMatrixResponse)
async def get_decision_matrix(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Decision Matrix 조회

    테넌트의 Trust Level × Risk Level → Decision 매핑 조회
    """
    service = DecisionMatrixService(db)

    # 기본 매트릭스가 없으면 초기화
    entries = service.get_matrix(current_user.tenant_id)
    if not entries:
        service.initialize_default_matrix(current_user.tenant_id, created_by=current_user.user_id)
        entries = service.get_matrix(current_user.tenant_id)

    summary = service.get_matrix_summary(current_user.tenant_id)

    return DecisionMatrixResponse(
        tenant_id=str(current_user.tenant_id),
        entries=[DecisionMatrixEntry(
            matrix_id=str(e.matrix_id),
            trust_level=e.trust_level,
            risk_level=e.risk_level,
            decision=e.decision,
            min_trust_score=float(e.min_trust_score) if e.min_trust_score else None,
            max_consecutive_failures=e.max_consecutive_failures,
            require_recent_success=e.require_recent_success,
            cooldown_seconds=e.cooldown_seconds,
            description=e.description,
            is_active=e.is_active,
        ) for e in entries],
        summary=summary,
    )


@router.put("/matrix/{trust_level}/{risk_level}", response_model=DecisionMatrixEntry)
async def update_decision_matrix_entry(
    trust_level: int,
    risk_level: str,
    request: DecisionMatrixUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Decision Matrix 엔트리 업데이트

    특정 Trust Level × Risk Level 조합의 결정을 변경
    """
    if trust_level < 0 or trust_level > 3:
        raise HTTPException(status_code=400, detail="Trust level must be 0-3")

    if risk_level not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        raise HTTPException(status_code=400, detail="Invalid risk level")

    if request.decision and request.decision not in ["auto_execute", "require_approval", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid decision")

    service = DecisionMatrixService(db)
    entry = service.update_matrix_entry(
        tenant_id=current_user.tenant_id,
        trust_level=trust_level,
        risk_level=risk_level,
        decision=request.decision,
        min_trust_score=request.min_trust_score,
        max_consecutive_failures=request.max_consecutive_failures,
        require_recent_success=request.require_recent_success,
        cooldown_seconds=request.cooldown_seconds,
        description=request.description,
    )

    return DecisionMatrixEntry(
        matrix_id=str(entry.matrix_id),
        trust_level=entry.trust_level,
        risk_level=entry.risk_level,
        decision=entry.decision,
        min_trust_score=float(entry.min_trust_score) if entry.min_trust_score else None,
        max_consecutive_failures=entry.max_consecutive_failures,
        require_recent_success=entry.require_recent_success,
        cooldown_seconds=entry.cooldown_seconds,
        description=entry.description,
        is_active=entry.is_active,
    )


@router.post("/matrix/reset")
async def reset_decision_matrix(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Decision Matrix 기본값으로 리셋
    """
    service = DecisionMatrixService(db)
    updated = service.reset_to_default(current_user.tenant_id)

    return {"success": True, "updated_entries": updated}


# ============================================
# Action Risk 엔드포인트
# ============================================

@router.get("/risks", response_model=list[ActionRiskDefinitionResponse])
async def get_risk_definitions(
    category: Optional[str] = Query(None, description="카테고리 필터"),
    risk_level: Optional[str] = Query(None, description="위험도 필터"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Action Risk 정의 목록 조회
    """
    service = ActionRiskEvaluator(db)
    definitions = service.get_definitions(
        tenant_id=current_user.tenant_id,
        category=category,
        risk_level=risk_level,
    )

    return [
        ActionRiskDefinitionResponse(
            risk_def_id=str(d.risk_def_id),
            tenant_id=str(d.tenant_id),
            action_type=d.action_type,
            action_pattern=d.action_pattern,
            category=d.category,
            risk_level=d.risk_level,
            risk_score=d.risk_score,
            reversible=d.reversible,
            affects_production=d.affects_production,
            affects_finance=d.affects_finance,
            affects_compliance=d.affects_compliance,
            description=d.description,
            priority=d.priority,
            is_active=d.is_active,
            created_at=d.created_at.isoformat() if d.created_at else None,
        )
        for d in definitions
    ]


@router.post("/risks", response_model=ActionRiskDefinitionResponse)
async def create_risk_definition(
    request: ActionRiskDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Action Risk 정의 생성
    """
    if request.risk_level not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        raise HTTPException(status_code=400, detail="Invalid risk level")

    service = ActionRiskEvaluator(db)

    # 이미 존재하는지 확인
    existing = service.get_definition(current_user.tenant_id, request.action_type)
    if existing:
        raise HTTPException(status_code=409, detail="Action type already exists")

    definition = service.create_definition(
        tenant_id=current_user.tenant_id,
        action_type=request.action_type,
        risk_level=request.risk_level,
        action_pattern=request.action_pattern,
        category=request.category,
        risk_score=request.risk_score,
        reversible=request.reversible,
        affects_production=request.affects_production,
        affects_finance=request.affects_finance,
        affects_compliance=request.affects_compliance,
        description=request.description,
        priority=request.priority,
    )

    return ActionRiskDefinitionResponse(
        risk_def_id=str(definition.risk_def_id),
        tenant_id=str(definition.tenant_id),
        action_type=definition.action_type,
        action_pattern=definition.action_pattern,
        category=definition.category,
        risk_level=definition.risk_level,
        risk_score=definition.risk_score,
        reversible=definition.reversible,
        affects_production=definition.affects_production,
        affects_finance=definition.affects_finance,
        affects_compliance=definition.affects_compliance,
        description=definition.description,
        priority=definition.priority,
        is_active=definition.is_active,
        created_at=definition.created_at.isoformat() if definition.created_at else None,
    )


@router.put("/risks/{action_type}", response_model=ActionRiskDefinitionResponse)
async def update_risk_definition(
    action_type: str,
    request: ActionRiskDefinitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Action Risk 정의 업데이트
    """
    if request.risk_level and request.risk_level not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        raise HTTPException(status_code=400, detail="Invalid risk level")

    service = ActionRiskEvaluator(db)
    definition = service.update_definition(
        tenant_id=current_user.tenant_id,
        action_type=action_type,
        risk_level=request.risk_level,
        action_pattern=request.action_pattern,
        category=request.category,
        risk_score=request.risk_score,
        reversible=request.reversible,
        affects_production=request.affects_production,
        affects_finance=request.affects_finance,
        affects_compliance=request.affects_compliance,
        description=request.description,
        priority=request.priority,
    )

    if not definition:
        raise HTTPException(status_code=404, detail="Action type not found")

    return ActionRiskDefinitionResponse(
        risk_def_id=str(definition.risk_def_id),
        tenant_id=str(definition.tenant_id),
        action_type=definition.action_type,
        action_pattern=definition.action_pattern,
        category=definition.category,
        risk_level=definition.risk_level,
        risk_score=definition.risk_score,
        reversible=definition.reversible,
        affects_production=definition.affects_production,
        affects_finance=definition.affects_finance,
        affects_compliance=definition.affects_compliance,
        description=definition.description,
        priority=definition.priority,
        is_active=definition.is_active,
        created_at=definition.created_at.isoformat() if definition.created_at else None,
    )


@router.delete("/risks/{action_type}")
async def delete_risk_definition(
    action_type: str,
    hard_delete: bool = Query(False, description="완전 삭제 여부"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Action Risk 정의 삭제
    """
    service = ActionRiskEvaluator(db)
    success = service.delete_definition(
        tenant_id=current_user.tenant_id,
        action_type=action_type,
        soft_delete=not hard_delete,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Action type not found")

    return {"success": True, "action_type": action_type}


@router.post("/risks/initialize")
async def initialize_default_risks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    기본 Action Risk 정의 초기화
    """
    service = ActionRiskEvaluator(db)
    created = service.initialize_defaults(current_user.tenant_id)

    return {"success": True, "created_count": len(created)}


# ============================================
# Execution 평가 엔드포인트
# ============================================

@router.post("/evaluate", response_model=ExecutionEvaluateResponse)
async def evaluate_execution(
    request: ExecutionEvaluateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    실행 결정 평가

    Trust Level과 Risk Level을 기반으로 자동 실행 가능 여부 평가
    """
    from decimal import Decimal

    router_service = AutoExecutionRouter(db)

    ruleset_id = UUID(request.ruleset_id) if request.ruleset_id else None
    trust_score = Decimal(str(request.trust_score_override)) if request.trust_score_override else None

    decision, reason, context = router_service.evaluate(
        tenant_id=current_user.tenant_id,
        action_type=request.action_type,
        ruleset_id=ruleset_id,
        trust_level_override=request.trust_level_override,
        trust_score_override=trust_score,
    )

    return ExecutionEvaluateResponse(
        decision=decision,
        reason=reason,
        trust_level=context.get("trust_level", 0),
        trust_level_name=context.get("trust_level_name", "Unknown"),
        trust_score=context.get("trust_score"),
        risk_level=context.get("risk_level", "MEDIUM"),
        risk_score=context.get("risk_score"),
        risk_info=context.get("risk_info"),
        can_auto_execute=decision == "auto_execute",
    )


# ============================================
# Execution Log 엔드포인트
# ============================================

@router.get("/logs", response_model=AutoExecutionLogListResponse)
async def get_execution_logs(
    ruleset_id: Optional[str] = Query(None, description="룰셋 ID 필터"),
    workflow_id: Optional[str] = Query(None, description="워크플로우 ID 필터"),
    decision: Optional[str] = Query(None, description="결정 필터"),
    status: Optional[str] = Query(None, description="상태 필터"),
    limit: int = Query(50, ge=1, le=100, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    자동 실행 로그 조회
    """
    router_service = AutoExecutionRouter(db)
    logs = router_service.get_logs(
        tenant_id=current_user.tenant_id,
        ruleset_id=UUID(ruleset_id) if ruleset_id else None,
        workflow_id=UUID(workflow_id) if workflow_id else None,
        decision=decision,
        status=status,
        limit=limit,
        offset=offset,
    )

    return AutoExecutionLogListResponse(
        logs=[
            AutoExecutionLogResponse(
                log_id=str(log.log_id),
                tenant_id=str(log.tenant_id),
                workflow_id=str(log.workflow_id) if log.workflow_id else None,
                instance_id=str(log.instance_id) if log.instance_id else None,
                node_id=log.node_id,
                ruleset_id=str(log.ruleset_id) if log.ruleset_id else None,
                action_type=log.action_type,
                action_params=log.action_params,
                trust_level=log.trust_level,
                trust_score=float(log.trust_score) if log.trust_score else None,
                risk_level=log.risk_level,
                risk_score=log.risk_score,
                decision=log.decision,
                decision_reason=log.decision_reason,
                execution_status=log.execution_status,
                execution_result=log.execution_result,
                approval_id=str(log.approval_id) if log.approval_id else None,
                approved_by=str(log.approved_by) if log.approved_by else None,
                approved_at=log.approved_at.isoformat() if log.approved_at else None,
                error_message=log.error_message,
                latency_ms=log.latency_ms,
                created_at=log.created_at.isoformat() if log.created_at else None,
                executed_at=log.executed_at.isoformat() if log.executed_at else None,
            )
            for log in logs
        ],
        total=len(logs),  # 실제 구현에서는 별도 count 쿼리 필요
        limit=limit,
        offset=offset,
    )


@router.get("/pending", response_model=list[PendingApprovalResponse])
async def get_pending_approvals(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    승인 대기 목록 조회
    """
    router_service = AutoExecutionRouter(db)
    logs = router_service.get_pending_approvals(
        tenant_id=current_user.tenant_id,
        limit=limit,
    )

    trust_names = {0: "Proposed", 1: "Alert Only", 2: "Low Risk Auto", 3: "Full Auto"}

    return [
        PendingApprovalResponse(
            log_id=str(log.log_id),
            action_type=log.action_type,
            action_params=log.action_params,
            trust_level=log.trust_level,
            trust_level_name=trust_names.get(log.trust_level, "Unknown"),
            risk_level=log.risk_level,
            decision_reason=log.decision_reason,
            workflow_id=str(log.workflow_id) if log.workflow_id else None,
            ruleset_id=str(log.ruleset_id) if log.ruleset_id else None,
            created_at=log.created_at.isoformat() if log.created_at else None,
        )
        for log in logs
    ]


@router.post("/logs/{log_id}/action")
async def process_approval_action(
    log_id: str,
    request: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    승인/거부 처리
    """
    if request.action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    router_service = AutoExecutionRouter(db)

    if request.action == "approve":
        # 실제 구현에서는 executor 함수를 전달해야 함
        # 여기서는 승인 마킹만 수행
        log = router_service.get_log(UUID(log_id))
        if not log:
            raise HTTPException(status_code=404, detail="Log not found")

        log.mark_approved(str(current_user.user_id))
        log.execution_status = "approved"
        db.commit()

        return {"success": True, "action": "approved", "log_id": log_id}
    else:
        success = router_service.reject_after_approval(
            log_id=UUID(log_id),
            rejected_by=current_user.user_id,
            reason=request.reason,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Log not found or already processed")

        return {"success": True, "action": "rejected", "log_id": log_id}


# ============================================
# Stats 엔드포인트
# ============================================

@router.get("/stats", response_model=ExecutionStatsResponse)
async def get_execution_stats(
    ruleset_id: Optional[str] = Query(None, description="룰셋 ID 필터"),
    days: int = Query(7, ge=1, le=90, description="통계 기간 (일)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    실행 통계 조회
    """
    router_service = AutoExecutionRouter(db)
    stats = router_service.get_execution_stats(
        tenant_id=current_user.tenant_id,
        ruleset_id=UUID(ruleset_id) if ruleset_id else None,
        days=days,
    )

    return ExecutionStatsResponse(
        total=stats["total"],
        by_decision=stats["by_decision"],
        by_status=stats["by_status"],
        auto_execution_rate=stats["auto_execution_rate"],
        avg_latency_ms=stats["avg_latency_ms"],
    )


@router.get("/risks/summary", response_model=RiskSummaryResponse)
async def get_risk_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    위험도 요약 조회
    """
    service = ActionRiskEvaluator(db)
    summary = service.get_risk_summary(current_user.tenant_id)

    return RiskSummaryResponse(
        total=summary["total"],
        by_level=summary["by_level"],
        by_category=summary["by_category"],
    )
