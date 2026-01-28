from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Optional
from sqlalchemy.orm import Session
import logging

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User
from ..services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", summary="통합 검색")
async def search_products(
    query: str = Query(..., description="검색 키워드 (제품명 또는 원료명)"),
    search_internal: bool = Query(True, description="내부 DB 검색 여부"),
    search_api: bool = Query(True, description="공공 API 검색 여부"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    통합 검색 엔드포인트.
    query를 원료명으로 사용하여 내부 DB + 공공 API 검색.
    """
    try:
        service = SearchService(db, current_user.tenant_id)
        return await service.search_products(query, search_internal, search_api, limit)
    except Exception as e:
        logger.exception(f"[Search] Error: {e}")
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")


@router.get("/internal", summary="내부 DB 검색")
async def search_internal_recipes(
    ingredients: str = Query(..., description="쉼표로 구분된 원료명"),
    formulation_type: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    내부 DB에서 원료 조합으로 유사 제품 검색.
    ingredients: "비타민C,프로바이오틱스,유산균"
    """
    try:
        ingredient_list = [i.strip() for i in ingredients.split(",") if i.strip()]
        service = SearchService(db, current_user.tenant_id)
        return await service.search_internal(ingredient_list, formulation_type, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"내부 DB 검색 실패: {str(e)}")


@router.get("/external", summary="공공 API 검색")
async def search_external_products(
    ingredients: str = Query(..., description="쉼표로 구분된 원료명"),
    formulation_type: Optional[str] = None,
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    식품안전나라 API에서 원료 조합으로 유사 제품 검색.
    ingredients: "비타민C,프로바이오틱스"
    """
    try:
        ingredient_list = [i.strip() for i in ingredients.split(",") if i.strip()]
        service = SearchService(db, current_user.tenant_id)
        return await service.search_external(ingredient_list, formulation_type, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"공공 API 검색 실패: {str(e)}")


@router.get("/combined", summary="통합 검색 (내부+외부)")
async def search_combined(
    ingredients: str = Query(..., description="쉼표로 구분된 원료명"),
    formulation_type: Optional[str] = None,
    internal_limit: int = Query(5, ge=1, le=20),
    external_limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    내부 DB + 공공 API 통합 검색.
    """
    try:
        ingredient_list = [i.strip() for i in ingredients.split(",") if i.strip()]
        service = SearchService(db, current_user.tenant_id)
        return await service.search_combined(
            ingredient_list, formulation_type, internal_limit, external_limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통합 검색 실패: {str(e)}")
