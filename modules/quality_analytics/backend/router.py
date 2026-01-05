"""
품질 분석 Module - API Router
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User

router = APIRouter()


@router.get("/")
async def get_quality_analytics_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    품질 분석 모듈 정보 조회
    """
    return {
        "module": "quality_analytics",
        "name": "품질 분석",
        "status": "active",
        "tenant_id": str(current_user.tenant_id)
    }


@router.get("/config")
async def get_quality_analytics_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    품질 분석 모듈 설정 조회
    """
    # TODO: 모듈별 설정 구현
    return {
        "module": "quality_analytics",
        "config": {}
    }
