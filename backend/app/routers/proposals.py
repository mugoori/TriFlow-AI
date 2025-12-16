"""
Proposed Rules Router
제안된 규칙 관리 API
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import ProposedRule, Tenant
from app.services.feedback_analyzer import FeedbackAnalyzer

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["proposals"])


# ============ Pydantic Schemas ============

class ProposalResponse(BaseModel):
    """제안 규칙 응답"""
    proposal_id: str
    rule_name: str
    rule_description: Optional[str]
    rhai_script: str
    source_type: str
    source_data: dict
    confidence: float
    status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_comment: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProposalListResponse(BaseModel):
    """제안 목록 응답"""
    total: int
    proposals: List[ProposalResponse]


class ProposalReviewRequest(BaseModel):
    """제안 검토 요청"""
    action: str = Field(..., description="approve 또는 reject")
    comment: Optional[str] = Field(None, description="검토 코멘트")


class AnalysisResponse(BaseModel):
    """분석 결과 응답"""
    status: str
    message: str
    patterns_found: int
    proposals_created: int
    patterns: Optional[List[dict]] = None
    proposal_ids: Optional[List[str]] = None


class ProposalStats(BaseModel):
    """제안 통계"""
    total: int
    pending: int
    approved: int
    rejected: int
    deployed: int


# ============ Helper Functions ============

def _proposal_to_response(proposal: ProposedRule) -> ProposalResponse:
    """ProposedRule -> ProposalResponse 변환"""
    return ProposalResponse(
        proposal_id=str(proposal.proposal_id),
        rule_name=proposal.rule_name,
        rule_description=proposal.rule_description,
        rhai_script=proposal.rhai_script,
        source_type=proposal.source_type,
        source_data=proposal.source_data or {},
        confidence=proposal.confidence,
        status=proposal.status,
        reviewed_by=str(proposal.reviewed_by) if proposal.reviewed_by else None,
        reviewed_at=proposal.reviewed_at,
        review_comment=proposal.review_comment,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


# ============ API Endpoints ============

@router.get("", response_model=ProposalListResponse)
async def list_proposals(
    status: Optional[str] = Query(None, description="필터: pending, approved, rejected, deployed"),
    source_type: Optional[str] = Query(None, description="필터: feedback_analysis, pattern_detection, simulation"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    제안된 규칙 목록 조회
    """
    query = db.query(ProposedRule)

    if status:
        query = query.filter(ProposedRule.status == status)
    if source_type:
        query = query.filter(ProposedRule.source_type == source_type)

    total = query.count()
    proposals = query.order_by(desc(ProposedRule.created_at)).offset(offset).limit(limit).all()

    return ProposalListResponse(
        total=total,
        proposals=[_proposal_to_response(p) for p in proposals],
    )


@router.get("/stats", response_model=ProposalStats)
async def get_proposal_stats(
    db: Session = Depends(get_db),
):
    """
    제안 통계 조회
    """
    total = db.query(ProposedRule).count()
    pending = db.query(ProposedRule).filter(ProposedRule.status == "pending").count()
    approved = db.query(ProposedRule).filter(ProposedRule.status == "approved").count()
    rejected = db.query(ProposedRule).filter(ProposedRule.status == "rejected").count()
    deployed = db.query(ProposedRule).filter(ProposedRule.status == "deployed").count()

    return ProposalStats(
        total=total,
        pending=pending,
        approved=approved,
        rejected=rejected,
        deployed=deployed,
    )


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
):
    """
    제안 상세 조회
    """
    try:
        p_uuid = UUID(proposal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal ID format")

    proposal = db.query(ProposedRule).filter(ProposedRule.proposal_id == p_uuid).first()

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    return _proposal_to_response(proposal)


@router.post("/{proposal_id}/review")
async def review_proposal(
    proposal_id: str,
    review: ProposalReviewRequest,
    db: Session = Depends(get_db),
):
    """
    제안 검토 (승인/거절)
    """
    try:
        p_uuid = UUID(proposal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal ID format")

    if review.action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    analyzer = FeedbackAnalyzer(db)

    if review.action == "approve":
        ruleset = analyzer.approve_proposal(
            proposal_id=p_uuid,
            comment=review.comment,
        )
        if ruleset:
            return {
                "status": "approved",
                "message": "제안이 승인되어 새 룰셋으로 배포되었습니다",
                "proposal_id": proposal_id,
                "ruleset_id": str(ruleset.ruleset_id),
                "ruleset_name": ruleset.name,
            }
        else:
            raise HTTPException(status_code=400, detail="승인 처리 실패")
    else:
        success = analyzer.reject_proposal(
            proposal_id=p_uuid,
            comment=review.comment,
        )
        if success:
            return {
                "status": "rejected",
                "message": "제안이 거절되었습니다",
                "proposal_id": proposal_id,
            }
        else:
            raise HTTPException(status_code=400, detail="거절 처리 실패")


@router.delete("/{proposal_id}")
async def delete_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
):
    """
    제안 삭제 (pending 상태만 가능)
    """
    try:
        p_uuid = UUID(proposal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal ID format")

    proposal = db.query(ProposedRule).filter(ProposedRule.proposal_id == p_uuid).first()

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if proposal.status != "pending":
        raise HTTPException(status_code=400, detail="처리된 제안은 삭제할 수 없습니다")

    db.delete(proposal)
    db.commit()

    return {"message": "Proposal deleted", "proposal_id": proposal_id}


@router.post("/analyze", response_model=AnalysisResponse)
async def run_analysis(
    days: int = Query(7, ge=1, le=30, description="분석 기간 (일)"),
    min_frequency: int = Query(2, ge=1, le=10, description="최소 패턴 빈도"),
    db: Session = Depends(get_db),
):
    """
    피드백 분석 실행 및 규칙 제안 생성
    """
    try:
        analyzer = FeedbackAnalyzer(db)

        # 패턴 분석
        patterns = analyzer.analyze_feedback_patterns(days=days, min_frequency=min_frequency)

        if not patterns:
            return AnalysisResponse(
                status="no_patterns",
                message="분석할 피드백 패턴이 없습니다",
                patterns_found=0,
                proposals_created=0,
            )

        # 테넌트 조회
        tenant = db.query(Tenant).first()
        if not tenant:
            return AnalysisResponse(
                status="error",
                message="테넌트를 찾을 수 없습니다",
                patterns_found=len(patterns),
                proposals_created=0,
            )

        # 규칙 제안 생성
        proposals = analyzer.generate_rule_proposals(patterns, tenant.tenant_id)

        # 저장
        saved = analyzer.save_proposals(proposals)

        return AnalysisResponse(
            status="success",
            message=f"{len(patterns)}개 패턴 발견, {len(saved)}개 규칙 제안 생성",
            patterns_found=len(patterns),
            proposals_created=len(saved),
            patterns=[p.to_dict() for p in patterns],
            proposal_ids=[str(p.proposal_id) for p in saved],
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
