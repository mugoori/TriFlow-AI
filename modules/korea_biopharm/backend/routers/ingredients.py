from fastapi import APIRouter, Query, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User
from ..services.ingredient_service import IngredientService

router = APIRouter()

@router.get("", summary="원료 목록 조회")
async def get_materials(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모든 원료 목록 조회"""
    try:
        service = IngredientService(db, current_user.tenant_id)
        return await service.get_all_materials()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch materials: {str(e)}")

@router.get("/search", summary="원료 검색")
async def search_materials(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """원료명 검색"""
    import traceback
    import sys
    print(f"[DEBUG] Searching for: {q}", file=sys.stderr, flush=True)
    try:
        service = IngredientService(db, current_user.tenant_id)
        print(f"[DEBUG] Service created", file=sys.stderr, flush=True)
        result = await service.search_materials(q)
        print(f"[DEBUG] Search result count: {len(result)}", file=sys.stderr, flush=True)
        return result
    except Exception as e:
        error_msg = f"Search failed: {str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] Ingredient search error:\n{error_msg}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=error_msg)
