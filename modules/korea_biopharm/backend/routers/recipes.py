from fastapi import APIRouter, HTTPException, Query, Depends, Body
from typing import Optional
from sqlalchemy.orm import Session
import logging

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User
from ..services.recipe_service import RecipeService
from ..models.schemas import (
    AIGeneratedRecipeCreate,
    AIGeneratedRecipeResponse,
    RecipeFeedbackCreate,
    RecipeFeedbackResponse,
    UnifiedRecipeListResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ===================================
# 기본 레시피 엔드포인트 (기존 DB)
# ===================================

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


# ===================================
# 통합 레시피 엔드포인트 (unified 먼저 정의)
# ===================================

@router.get("/unified", summary="통합 레시피 목록")
async def get_unified_recipes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_type: Optional[str] = Query(None, description="소스 타입 (db_existing, ai_generated, mes_imported)"),
    status: Optional[str] = Query(None, description="상태 (draft, approved, production)"),
    formulation_type: Optional[str] = None,
    q: Optional[str] = Query(None, description="검색어"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """통합 레시피 목록 조회 (기존 DB + AI 생성)"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        return await service.get_unified_recipes(
            page, page_size, source_type, status, formulation_type, q
        )
    except Exception as e:
        logger.exception(f"[UnifiedRecipes] Error: {e}")
        raise HTTPException(status_code=500, detail=f"통합 레시피 조회 실패: {str(e)}")


# ===================================
# AI 생성 레시피 엔드포인트 (ai-generated 먼저 정의)
# ===================================

@router.post("/ai-generated", summary="AI 레시피 저장")
async def create_ai_recipe(
    recipe_data: AIGeneratedRecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 생성 레시피 저장"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        # Pydantic 모델을 dict로 변환 (model_dump()가 중첩 모델도 자동 변환)
        data = recipe_data.model_dump()

        result = await service.create_ai_recipe(data, current_user.user_id)
        logger.info(f"[AI Recipe] Created: {result.get('recipe_id')} by user {current_user.user_id}")
        return result
    except Exception as e:
        logger.exception(f"[AI Recipe] Create error: {e}")
        raise HTTPException(status_code=500, detail=f"AI 레시피 저장 실패: {str(e)}")


@router.get("/ai-generated", summary="AI 레시피 목록")
async def get_ai_recipes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 생성 레시피 목록 조회"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        return await service.get_ai_recipes(page, page_size, status, source_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 레시피 목록 조회 실패: {str(e)}")


@router.get("/ai-generated/{recipe_id}", summary="AI 레시피 상세")
async def get_ai_recipe(
    recipe_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 레시피 상세 조회"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        result = await service.get_ai_recipe(recipe_id)
        if not result:
            raise HTTPException(status_code=404, detail="AI 레시피를 찾을 수 없습니다")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 레시피 조회 실패: {str(e)}")


@router.delete("/ai-generated/{recipe_id}", summary="AI 레시피 삭제")
async def delete_ai_recipe(
    recipe_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 레시피 삭제"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        deleted = await service.delete_ai_recipe(recipe_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="AI 레시피를 찾을 수 없습니다")
        logger.info(f"[AI Recipe] Deleted: {recipe_id} by user {current_user.user_id}")
        return {"message": "삭제되었습니다", "recipe_id": recipe_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 레시피 삭제 실패: {str(e)}")


@router.patch("/ai-generated/{recipe_id}/status", summary="AI 레시피 상태 변경")
async def update_ai_recipe_status(
    recipe_id: str,
    status: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 레시피 상태 변경 (draft, approved, production, archived)"""
    valid_statuses = ['draft', 'approved', 'production', 'archived']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 상태입니다. 허용: {valid_statuses}")

    try:
        service = RecipeService(db, current_user.tenant_id)
        approved_by = current_user.user_id if status == 'approved' else None
        result = await service.update_ai_recipe_status(recipe_id, status, approved_by)
        if not result:
            raise HTTPException(status_code=404, detail="AI 레시피를 찾을 수 없습니다")
        logger.info(f"[AI Recipe] Status changed: {recipe_id} -> {status}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상태 변경 실패: {str(e)}")


# ===================================
# 피드백 엔드포인트
# ===================================

@router.post("/ai-generated/{recipe_id}/feedback", summary="레시피 피드백 저장")
async def create_recipe_feedback(
    recipe_id: str,
    feedback: RecipeFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """레시피 피드백 저장"""
    if feedback.rating < 1 or feedback.rating > 5:
        raise HTTPException(status_code=400, detail="평점은 1-5 사이여야 합니다")

    try:
        service = RecipeService(db, current_user.tenant_id)

        # 레시피 존재 확인
        recipe = await service.get_ai_recipe(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="AI 레시피를 찾을 수 없습니다")

        result = await service.create_recipe_feedback(
            recipe_id, feedback.model_dump(), current_user.user_id
        )
        logger.info(f"[Feedback] Created for recipe {recipe_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"피드백 저장 실패: {str(e)}")


@router.get("/ai-generated/{recipe_id}/feedback", summary="레시피 피드백 조회")
async def get_recipe_feedback(
    recipe_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """레시피 피드백 목록 조회"""
    try:
        service = RecipeService(db, current_user.tenant_id)
        return await service.get_recipe_feedback(recipe_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"피드백 조회 실패: {str(e)}")


# ===================================
# ID 기반 조회 (마지막에 정의 - catch-all)
# ===================================

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
