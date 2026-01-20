"""
Search Service - TriFlow 통합 패턴
"""
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Dict, Any, Optional
from datetime import datetime

from . import db_service
from . import foodsafety_api


class SearchService:
    """통합 검색 서비스"""

    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def search_products(
        self,
        query: str,
        search_internal: bool = True,
        search_api: bool = True,
        limit: int = 10
    ) -> Dict[str, Any]:
        """통합 검색 엔드포인트 - query를 원료명으로 사용"""
        # query를 원료 리스트로 변환 (쉼표 구분 또는 단일 키워드)
        ingredient_list = [i.strip() for i in query.split(",") if i.strip()]

        result = {
            "internal_results": [],
            "api_results": [],
            "query": query,
            "searched_at": datetime.now().isoformat()
        }

        # 내부 DB 검색
        if search_internal:
            result["internal_results"] = db_service.search_by_ingredients(
                ingredient_list, None, limit
            )

        # 공공 API 검색
        if search_api:
            result["api_results"] = await foodsafety_api.search_by_ingredients(
                ingredient_list, None, limit
            )

        return result

    async def search_internal(
        self,
        ingredients: List[str],
        formulation_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """내부 DB 검색"""
        return db_service.search_by_ingredients(
            ingredients,
            formulation_type,
            limit
        )

    async def search_external(
        self,
        ingredients: List[str],
        formulation_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """공공 API 검색"""
        return await foodsafety_api.search_by_ingredients(
            ingredients,
            formulation_type,
            limit
        )

    async def search_combined(
        self,
        ingredients: List[str],
        formulation_type: Optional[str] = None,
        internal_limit: int = 5,
        external_limit: int = 5
    ) -> Dict[str, Any]:
        """통합 검색 (내부 + 외부)"""
        internal = db_service.search_by_ingredients(
            ingredients, formulation_type, internal_limit
        )
        external = await foodsafety_api.search_by_ingredients(
            ingredients, formulation_type, external_limit
        )

        return {
            "internal": internal,
            "external": external,
            "query": {
                "ingredients": ingredients,
                "formulation_type": formulation_type
            }
        }
