"""
Feedback Router
사용자 피드백 수집 API
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import FeedbackLog, Tenant

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["feedback"])


# ============ Pydantic Schemas ============

class FeedbackCreate(BaseModel):
    """피드백 생성 요청"""
    feedback_type: str = Field(..., description="positive, negative, correction")
    original_output: Optional[dict] = Field(None, description="AI 원본 응답")
    corrected_output: Optional[dict] = Field(None, description="사용자 수정 답변")
    feedback_text: Optional[str] = Field(None, description="피드백 코멘트")
    context_data: Optional[dict] = Field(default_factory=dict, description="추가 컨텍스트")
    message_id: Optional[str] = Field(None, description="연관 메시지 ID")
    agent_type: Optional[str] = Field(None, description="응답한 에이전트 타입")


class FeedbackResponse(BaseModel):
    """피드백 응답"""
    feedback_id: str
    feedback_type: str
    original_output: Optional[dict]
    corrected_output: Optional[dict]
    feedback_text: Optional[str]
    context_data: dict
    is_processed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackStats(BaseModel):
    """피드백 통계"""
    total: int
    positive: int
    negative: int
    correction: int
    unprocessed: int


# ============ Helper Functions ============

def _get_default_tenant(db: Session) -> Tenant:
    """기본 테넌트 조회 또는 생성"""
    tenant = db.query(Tenant).first()
    if not tenant:
        tenant = Tenant(
            tenant_id=uuid4(),
            name="Default Tenant",
            is_active=True,
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def _feedback_to_response(feedback: FeedbackLog) -> FeedbackResponse:
    """FeedbackLog -> FeedbackResponse 변환"""
    return FeedbackResponse(
        feedback_id=str(feedback.feedback_id),
        feedback_type=feedback.feedback_type,
        original_output=feedback.original_output,
        corrected_output=feedback.corrected_output,
        feedback_text=feedback.comment,  # 모델에서는 comment 속성으로 정의됨
        context_data=feedback.context_data or {},
        is_processed=feedback.is_processed,
        created_at=feedback.created_at,
    )


# ============ API Endpoints ============

@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    feedback_data: FeedbackCreate,
    db: Session = Depends(get_db),
):
    """
    피드백 생성
    - feedback_type: positive, negative, correction
    """
    # 유효한 feedback_type 검증
    valid_types = ["positive", "negative", "correction"]
    if feedback_data.feedback_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback_type. Must be one of: {valid_types}"
        )

    tenant = _get_default_tenant(db)

    # context_data에 추가 정보 포함
    context = feedback_data.context_data or {}
    if feedback_data.message_id:
        context["message_id"] = feedback_data.message_id
    if feedback_data.agent_type:
        context["agent_type"] = feedback_data.agent_type

    feedback = FeedbackLog(
        feedback_id=uuid4(),
        tenant_id=tenant.tenant_id,
        feedback_type=feedback_data.feedback_type,
        original_output=feedback_data.original_output,
        corrected_output=feedback_data.corrected_output,
        comment=feedback_data.feedback_text,  # 모델에서는 comment 속성으로 정의됨
        context_data=context,
        is_processed=False,
        created_at=datetime.utcnow(),
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    logger.info(f"Feedback created: {feedback.feedback_id} ({feedback.feedback_type})")

    return _feedback_to_response(feedback)


@router.get("", response_model=List[FeedbackResponse])
async def list_feedback(
    feedback_type: Optional[str] = Query(None, description="필터: positive, negative, correction"),
    is_processed: Optional[bool] = Query(None, description="처리 여부 필터"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    피드백 목록 조회
    """
    query = db.query(FeedbackLog)

    if feedback_type:
        query = query.filter(FeedbackLog.feedback_type == feedback_type)
    if is_processed is not None:
        query = query.filter(FeedbackLog.is_processed == is_processed)

    feedbacks = query.order_by(desc(FeedbackLog.created_at)).offset(offset).limit(limit).all()

    return [_feedback_to_response(f) for f in feedbacks]


@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    db: Session = Depends(get_db),
):
    """
    피드백 통계 조회
    """
    total = db.query(FeedbackLog).count()
    positive = db.query(FeedbackLog).filter(FeedbackLog.feedback_type == "positive").count()
    negative = db.query(FeedbackLog).filter(FeedbackLog.feedback_type == "negative").count()
    correction = db.query(FeedbackLog).filter(FeedbackLog.feedback_type == "correction").count()
    unprocessed = db.query(FeedbackLog).filter(FeedbackLog.is_processed == False).count()

    return FeedbackStats(
        total=total,
        positive=positive,
        negative=negative,
        correction=correction,
        unprocessed=unprocessed,
    )


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: str,
    db: Session = Depends(get_db),
):
    """
    피드백 상세 조회
    """
    try:
        fb_uuid = UUID(feedback_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid feedback ID format")

    feedback = db.query(FeedbackLog).filter(FeedbackLog.feedback_id == fb_uuid).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return _feedback_to_response(feedback)


@router.patch("/{feedback_id}/process")
async def mark_as_processed(
    feedback_id: str,
    db: Session = Depends(get_db),
):
    """
    피드백을 처리됨으로 마킹
    """
    try:
        fb_uuid = UUID(feedback_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid feedback ID format")

    feedback = db.query(FeedbackLog).filter(FeedbackLog.feedback_id == fb_uuid).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.is_processed = True
    feedback.processed_at = datetime.utcnow()
    db.commit()

    return {"message": "Feedback marked as processed", "feedback_id": feedback_id}


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    db: Session = Depends(get_db),
):
    """
    피드백 삭제
    """
    try:
        fb_uuid = UUID(feedback_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid feedback ID format")

    feedback = db.query(FeedbackLog).filter(FeedbackLog.feedback_id == fb_uuid).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    db.delete(feedback)
    db.commit()

    return {"message": "Feedback deleted", "feedback_id": feedback_id}
