from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User
from ..models.schemas import PromptRequest, PromptResponse
from ..services.prompt_service import generate_formulation_prompt, generate_and_execute_recipe

router = APIRouter()


@router.post("/generate", response_model=PromptResponse, summary="배합비 추천 프롬프트 생성")
async def generate_prompt(
    request: PromptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    배합비 추천 프롬프트 생성.
    공공API 검색 결과를 similar_products_api에 포함하여 요청.
    """
    try:
        prompt = generate_formulation_prompt(request)

        return PromptResponse(
            prompt=prompt,
            similar_products_count=len(request.similar_products_api) if request.similar_products_api else 0,
            generated_at=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프롬프트 생성 실패: {str(e)}")

@router.post("/generate-recipe", summary="AI 배합비 자동 생성")
async def generate_recipe(
    request: PromptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI 배합비 자동 생성 (3가지 옵션)
    - TriFlow Claude API 사용
    - 내부 DB 검색 (SQL MCP)
    - 구조화된 배합비 반환
    """
    try:
        result = await generate_and_execute_recipe(
            request.product_info.dict(),
            [ing.dict() for ing in request.ingredient_requirements],
            request.constraints.dict() if request.constraints else {},
            [p.dict() for p in request.similar_products_api] if request.similar_products_api else []
        )
        return result
    except Exception as e:
        import traceback
        error_detail = f"배합비 생성 실패: {str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] {error_detail}")  # 디버깅용
        raise HTTPException(status_code=500, detail=error_detail)
