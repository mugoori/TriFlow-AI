"""
Ingredient Service - TriFlow 통합 패턴
"""
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from . import db_service


class IngredientService:
    """원료 서비스"""

    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def get_all_materials(self) -> List[str]:
        """모든 원료 목록"""
        return db_service.get_materials(self.db, self.tenant_id)

    async def search_materials(self, query: str) -> List[str]:
        """원료 검색"""
        return db_service.search_materials(self.db, self.tenant_id, query)
