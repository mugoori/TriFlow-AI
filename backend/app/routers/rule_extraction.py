# -*- coding: utf-8 -*-
"""Rule Extraction Router

Decision Tree 기반 규칙 추출 API.

LRN-FR-030 스펙 참조
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User
from app.services.rule_extraction_service import RuleExtractionService
from app.schemas.rule_extraction import (
    RuleExtractionRequest,
    RuleExtractionResponse,
    CandidateResponse,
    CandidateListResponse,
    TestRequest,
    TestResponse,
    TestResultDetail,
    ApproveRequest,
    ApproveResponse,
    RejectRequest,
    ExtractionStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rule-extraction", tags=["rule-extraction"])


# ============================================
# 규칙 추출
# ============================================


@router.post(
    "/extract",
    response_model=RuleExtractionResponse,
    summary="Decision Tree 학습 및 규칙 생성",
    description="승인된 샘플에서 Decision Tree를 학습하고 Rhai 규칙을 자동 생성합니다.",
)
async def extract_rules(
    request: RuleExtractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """규칙 추출 API"""
    try:
        service = RuleExtractionService(db)
        candidate, metrics, feature_importance = service.extract_rules(
            tenant_id=current_user.tenant_id,
            request=request,
        )

        # 메타데이터에서 추가 정보 추출
        meta = candidate.candidate_metadata or {}

        return RuleExtractionResponse(
            candidate_id=candidate.candidate_id,
            samples_used=meta.get("samples_used", 0),
            tree_depth=meta.get("tree_depth", 0),
            feature_count=meta.get("feature_count", 0),
            class_count=len(meta.get("class_names", [])),
            metrics=metrics,
            rhai_preview=candidate.generated_rule[:500] if candidate.generated_rule else "",
            feature_importance=feature_importance,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Rule extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"규칙 추출 실패: {str(e)}",
        )


# ============================================
# 후보 관리
# ============================================


@router.get(
    "/candidates",
    response_model=CandidateListResponse,
    summary="규칙 후보 목록",
)
async def list_candidates(
    status: Optional[str] = Query(None, description="필터: pending, approved, rejected, testing"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """후보 목록 조회"""
    service = RuleExtractionService(db)
    candidates, total = service.list_candidates(
        tenant_id=current_user.tenant_id,
        status=status,
        page=page,
        page_size=page_size,
    )

    return CandidateListResponse(
        items=[
            CandidateResponse(
                candidate_id=c.candidate_id,
                tenant_id=c.tenant_id,
                ruleset_id=c.ruleset_id,
                generated_rule=c.generated_rule,
                generation_method=c.generation_method,
                coverage=c.coverage or 0,
                precision=c.precision or 0,
                recall=c.recall or 0,
                f1_score=c.f1_score or 0,
                approval_status=c.approval_status,
                test_results=c.test_results,
                rejection_reason=c.rejection_reason,
                created_at=c.created_at,
                updated_at=None,
                approved_at=c.approved_at,
                approved_by=c.approver_id,
            )
            for c in candidates
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateResponse,
    summary="규칙 후보 상세",
)
async def get_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """후보 상세 조회"""
    service = RuleExtractionService(db)
    candidate = service.get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="후보를 찾을 수 없습니다",
        )

    # 테넌트 권한 확인
    if candidate.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다",
        )

    return CandidateResponse(
        candidate_id=candidate.candidate_id,
        tenant_id=candidate.tenant_id,
        ruleset_id=candidate.ruleset_id,
        generated_rule=candidate.generated_rule,
        generation_method=candidate.generation_method,
        coverage=candidate.coverage or 0,
        precision=candidate.precision or 0,
        recall=candidate.recall or 0,
        f1_score=candidate.f1_score or 0,
        approval_status=candidate.approval_status,
        test_results=candidate.test_results,
        rejection_reason=candidate.rejection_reason,
        created_at=candidate.created_at,
        updated_at=None,
        approved_at=candidate.approved_at,
        approved_by=candidate.approver_id,
    )


@router.delete(
    "/candidates/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="규칙 후보 삭제",
)
async def delete_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """후보 삭제"""
    service = RuleExtractionService(db)
    candidate = service.get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="후보를 찾을 수 없습니다",
        )

    if candidate.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다",
        )

    service.delete_candidate(candidate_id)


# ============================================
# 테스트/승인/거절
# ============================================


@router.post(
    "/candidates/{candidate_id}/test",
    response_model=TestResponse,
    summary="규칙 후보 테스트",
)
async def test_candidate(
    candidate_id: UUID,
    request: TestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """후보 규칙 테스트 실행"""
    service = RuleExtractionService(db)
    candidate = service.get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="후보를 찾을 수 없습니다",
        )

    if candidate.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다",
        )

    try:
        result = service.test_candidate(
            candidate_id=candidate_id,
            test_samples=request.test_samples,
        )

        return TestResponse(
            total=result["total"],
            passed=result["passed"],
            failed=result["failed"],
            accuracy=result["accuracy"],
            execution_time_ms=result["execution_time_ms"],
            details=[
                TestResultDetail(**d) for d in result["details"]
            ],
        )

    except Exception as e:
        logger.exception(f"Test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"테스트 실패: {str(e)}",
        )


@router.post(
    "/candidates/{candidate_id}/approve",
    response_model=ApproveResponse,
    summary="규칙 후보 승인",
    description="후보를 승인하고 ProposedRule을 생성합니다.",
)
async def approve_candidate(
    candidate_id: UUID,
    request: ApproveRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """후보 승인 → ProposedRule 생성"""
    service = RuleExtractionService(db)
    candidate = service.get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="후보를 찾을 수 없습니다",
        )

    if candidate.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다",
        )

    try:
        rule_name = request.rule_name if request else None
        description = request.description if request else None

        proposal = service.approve_candidate(
            candidate_id=candidate_id,
            approver_id=current_user.user_id,
            rule_name=rule_name,
            description=description,
        )

        return ApproveResponse(
            proposal_id=proposal.proposal_id,
            rule_name=proposal.rule_name,
            confidence=proposal.confidence,
            status=proposal.status,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/candidates/{candidate_id}/reject",
    response_model=CandidateResponse,
    summary="규칙 후보 거절",
)
async def reject_candidate(
    candidate_id: UUID,
    request: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """후보 거절"""
    service = RuleExtractionService(db)
    candidate = service.get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="후보를 찾을 수 없습니다",
        )

    if candidate.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다",
        )

    try:
        updated = service.reject_candidate(
            candidate_id=candidate_id,
            reason=request.reason,
        )

        return CandidateResponse(
            candidate_id=updated.candidate_id,
            tenant_id=updated.tenant_id,
            ruleset_id=updated.ruleset_id,
            generated_rule=updated.generated_rule,
            generation_method=updated.generation_method,
            coverage=updated.coverage or 0,
            precision=updated.precision or 0,
            recall=updated.recall or 0,
            f1_score=updated.f1_score or 0,
            approval_status=updated.approval_status,
            test_results=updated.test_results,
            rejection_reason=updated.rejection_reason,
            created_at=updated.created_at,
            updated_at=None,
            approved_at=updated.approved_at,
            approved_by=updated.approver_id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================
# 통계
# ============================================


@router.get(
    "/stats",
    response_model=ExtractionStats,
    summary="규칙 추출 통계",
)
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """추출 통계 조회"""
    service = RuleExtractionService(db)
    stats = service.get_stats(current_user.tenant_id)

    return ExtractionStats(**stats)
