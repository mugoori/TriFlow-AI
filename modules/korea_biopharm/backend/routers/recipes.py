from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User
from ..services.recipe_service import RecipeService

router = APIRouter()

@router.get("", summary="배합비 목록 조회")
async def get_recipes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    formulation_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """제품 목록 조회 (메타데이터) - 테넌트별 격리"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        return await service.get_recipes(page, page_size, formulation_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recipes: {str(e)}")

@router.get("/types", summary="제형 목록")
async def get_formulation_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """제형 목록 및 통계"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        return await service.get_formulation_types()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch formulation types: {str(e)}")

@router.get("/search", summary="배합비 검색")
async def search_recipes(
    q: str = Query(..., min_length=1),
    formulation_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """제품명/업체명으로 검색"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        return await service.search_recipes(q, formulation_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/detail/{filename:path}", summary="배합비 상세 조회")
async def get_recipe_detail(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """특정 제품의 배합비 상세 조회 (파일명)"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        result = await service.get_recipe_detail_by_filename(filename)
        if not result:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recipe: {str(e)}")

@router.get("/{recipe_id}", summary="배합비 상세 조회 (ID)")
async def get_recipe_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ID로 제품 배합비 상세 조회"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        result = await service.get_recipe_detail(recipe_id)
        if not result:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recipe: {str(e)}")
