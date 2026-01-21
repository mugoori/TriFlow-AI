# -*- coding: utf-8 -*-
"""
Workflow Repository
워크플로우 데이터 접근 계층
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.core import Workflow
from app.repositories.base_repository import BaseRepository
from app.utils.errors import raise_not_found


class WorkflowRepository(BaseRepository[Workflow]):
    """워크플로우 Repository"""
    
    def __init__(self, db: Session):
        super().__init__(db, Workflow)
    
    def get_by_id_or_404(self, workflow_id: UUID) -> Workflow:
        """ID로 워크플로우 조회 (없으면 404)"""
        workflow = self.db.query(Workflow).filter(
            Workflow.workflow_id == workflow_id
        ).first()
        if not workflow:
            raise_not_found("Workflow", str(workflow_id))
        return workflow
    
    def get_by_tenant(self, tenant_id: UUID) -> List[Workflow]:
        """테넌트별 워크플로우 목록"""
        return self.db.query(Workflow).filter(
            Workflow.tenant_id == tenant_id
        ).all()
    
    def get_active_workflows(self, tenant_id: UUID) -> List[Workflow]:
        """활성 워크플로우 목록"""
        return self.db.query(Workflow).filter(
            Workflow.tenant_id == tenant_id,
            Workflow.is_active == True
        ).all()
    
    def get_by_name(self, name: str, tenant_id: UUID) -> Optional[Workflow]:
        """이름으로 워크플로우 조회"""
        return self.db.query(Workflow).filter(
            Workflow.name == name,
            Workflow.tenant_id == tenant_id
        ).first()
    
    def name_exists(self, name: str, tenant_id: UUID) -> bool:
        """워크플로우 이름 중복 확인"""
        return self.get_by_name(name, tenant_id) is not None
