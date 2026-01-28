"""
Recipe Service - PostgreSQL Version
- 기존 DB 레시피 조회
- AI 생성 레시피 저장/조회
- 통합 레시피 뷰 조회
"""
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional, Dict, Any

from . import db_service


class RecipeService:
    """
    배합비 서비스
    - PostgreSQL 사용
    - 테넌트 격리
    """

    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def get_recipes(
        self,
        page: int = 1,
        page_size: int = 20,
        formulation_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """배합비 목록 조회 (페이징)"""
        return db_service.get_all_recipes(self.db, self.tenant_id, page, page_size, formulation_type)

    async def get_formulation_types(self) -> List[Dict[str, Any]]:
        """제형 목록 및 통계"""
        return db_service.get_formulation_types(self.db, self.tenant_id)

    async def search_recipes(
        self,
        query: str,
        formulation_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """제품 검색"""
        return db_service.search_recipes(self.db, self.tenant_id, query, formulation_type, page, page_size)

    async def search_by_ingredients(
        self,
        ingredients: List[str],
        formulation_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """원료로 배합비 검색"""
        return db_service.search_by_ingredients(self.db, self.tenant_id, ingredients, formulation_type, limit)

    async def get_recipe_detail_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """배합비 상세 조회 (파일명)"""
        return db_service.get_recipe_detail(self.db, self.tenant_id, filename)

    async def get_recipe_detail(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        """배합비 상세 조회 (ID)"""
        return db_service.get_recipe_detail_by_id(self.db, self.tenant_id, recipe_id)

    # ===================================
    # AI 생성 레시피 관련 메서드
    # ===================================

    async def create_ai_recipe(
        self,
        recipe_data: Dict[str, Any],
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """AI 생성 레시피 저장"""
        return db_service.create_ai_recipe(self.db, self.tenant_id, user_id, recipe_data)

    async def get_ai_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """AI 레시피 상세 조회"""
        return db_service.get_ai_recipe_by_id(self.db, self.tenant_id, recipe_id)

    async def get_ai_recipes(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        source_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """AI 레시피 목록 조회"""
        return db_service.get_ai_recipes(
            self.db, self.tenant_id, page, page_size, status, source_type
        )

    async def delete_ai_recipe(self, recipe_id: str) -> bool:
        """AI 레시피 삭제"""
        return db_service.delete_ai_recipe(self.db, self.tenant_id, recipe_id)

    async def update_ai_recipe_status(
        self,
        recipe_id: str,
        status: str,
        approved_by: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """AI 레시피 상태 업데이트"""
        return db_service.update_ai_recipe_status(
            self.db, self.tenant_id, recipe_id, status, approved_by
        )

    # ===================================
    # 통합 레시피 관련 메서드
    # ===================================

    async def get_unified_recipes(
        self,
        page: int = 1,
        page_size: int = 20,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        formulation_type: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """통합 레시피 조회 (기존 DB + AI 생성)"""
        return db_service.get_unified_recipes(
            self.db, self.tenant_id, page, page_size,
            source_type, status, formulation_type, search_query
        )

    # ===================================
    # 피드백 관련 메서드
    # ===================================

    async def create_recipe_feedback(
        self,
        recipe_id: str,
        feedback_data: Dict[str, Any],
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """레시피 피드백 생성"""
        return db_service.create_recipe_feedback(
            self.db, self.tenant_id, recipe_id, user_id, feedback_data
        )

    async def get_recipe_feedback(self, recipe_id: str) -> List[Dict[str, Any]]:
        """레시피 피드백 조회"""
        return db_service.get_recipe_feedback(self.db, self.tenant_id, recipe_id)
