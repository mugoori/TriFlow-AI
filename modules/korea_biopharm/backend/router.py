"""
한국바이오팜 Module - API Router
"""
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# 하위 라우터들을 상대 경로로 import
try:
    from .routers import recipes, ingredients, search, prompt
    # from .routers import feedback  # 임시 비활성화 - PostgreSQL 마이그레이션 미완료

    router.include_router(recipes.router, prefix="/recipes", tags=["korea-biopharm-recipes"])
    router.include_router(ingredients.router, prefix="/ingredients", tags=["korea-biopharm-ingredients"])
    router.include_router(search.router, prefix="/search", tags=["korea-biopharm-search"])
    router.include_router(prompt.router, prefix="/prompt", tags=["korea-biopharm-prompt"])
    # router.include_router(feedback.router, prefix="/feedback", tags=["korea-biopharm-feedback"])  # 임시 비활성화

    logger.info("Korea Biopharm sub-routers loaded successfully (feedback disabled)")
except Exception as e:
    # 라우터 로드 실패 시 기본 엔드포인트만 제공
    logger.error(f"Failed to load korea_biopharm sub-routers: {e}", exc_info=True)

    @router.get("/")
    async def get_module_info():
        return {
            "module": "korea_biopharm",
            "name": "한국바이오팜",
            "status": "active",
            "message": f"Sub-routers not loaded: {str(e)}"
        }

@router.get("/test-db")
async def test_db():
    """Test DB connection"""
    try:
        from .config.settings import DB_PATH
        from .services.db_service import get_formulation_types
        
        db_exists = DB_PATH.exists() if hasattr(DB_PATH, 'exists') else False
        
        if not db_exists:
            return {
                "error": f"DB not found at {DB_PATH}",
                "db_path": str(DB_PATH)
            }
        
        types = get_formulation_types()
        return {
            "success": True,
            "db_path": str(DB_PATH),
            "db_exists": db_exists,
            "formulation_types": types
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
