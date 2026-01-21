# -*- coding: utf-8 -*-
"""
Ruleset Repository
룰셋 데이터 접근 계층
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.core import Ruleset
from app.repositories.base_repository import BaseRepository
from app.utils.errors import raise_not_found


class RulesetRepository(BaseRepository[Ruleset]):
    """룰셋 Repository"""
    
    def __init__(self, db: Session):
        super().__init__(db, Ruleset)
    
    def get_by_id_or_404(self, ruleset_id: UUID) -> Ruleset:
        """ID로 룰셋 조회 (없으면 404)"""
        ruleset = self.db.query(Ruleset).filter(
            Ruleset.ruleset_id == ruleset_id
        ).first()
        if not ruleset:
            raise_not_found("Ruleset", str(ruleset_id))
        return ruleset
    
    def get_by_tenant(self, tenant_id: UUID) -> List[Ruleset]:
        """테넌트별 룰셋 목록"""
        return self.db.query(Ruleset).filter(
            Ruleset.tenant_id == tenant_id
        ).all()
    
    def get_active_rulesets(self, tenant_id: UUID) -> List[Ruleset]:
        """활성 룰셋 목록"""
        return self.db.query(Ruleset).filter(
            Ruleset.tenant_id == tenant_id,
            Ruleset.is_active == True
        ).all()
    
    def get_by_name(self, name: str, tenant_id: UUID) -> Optional[Ruleset]:
        """이름으로 룰셋 조회"""
        return self.db.query(Ruleset).filter(
            Ruleset.name == name,
            Ruleset.tenant_id == tenant_id
        ).first()
