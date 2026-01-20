from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User
from ..services.feedback_service import FeedbackService

router = APIRouter()


class FeedbackCreate(BaseModel):
    recipe_id: int
    rating: int  # 1-5
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    recipe_id: int
    rating: int
    comment: Optional[str]
    created_at: str


@router.post("", summary="피드백 저장")
async def create_feedback(
    feedback: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """피드백 저장"""
    try:
        service = FeedbackService(db, current_user.tenant_id)
        return await service.create_feedback(
            feedback.recipe_id,
            feedback.rating,
            feedback.comment
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"피드백 저장 실패: {str(e)}")


@router.get("", response_model=List[FeedbackResponse], summary="피드백 목록 조회")
async def get_all_feedback(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모든 피드백 조회"""
    try:
        service = FeedbackService(db, current_user.tenant_id)
        feedbacks = await service.get_all_feedback(skip, limit)
        return [
            FeedbackResponse(
                id=fb["id"],
                recipe_id=fb["recipe_id"],
                rating=fb["rating"],
                comment=fb["comment"],
                created_at=fb["created_at"]
            )
            for fb in feedbacks
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"피드백 조회 실패: {str(e)}")


@router.get("/stats", summary="피드백 통계")
async def get_feedback_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """피드백 통계"""
    try:
        service = FeedbackService(db, current_user.tenant_id)
        return await service.get_feedback_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")
