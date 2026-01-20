"""
Recipe Service - PostgreSQL Version
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
