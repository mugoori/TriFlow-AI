# -*- coding: utf-8 -*-
"""
Experiment Repository
실험 데이터 접근 계층
"""
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.core import Experiment
from app.repositories.base_repository import BaseRepository
from app.utils.errors import raise_not_found


class ExperimentRepository(BaseRepository[Experiment]):
    """실험 Repository"""
    
    def __init__(self, db: Session):
        super().__init__(db, Experiment)
    
    def get_by_id_or_404(self, experiment_id: UUID) -> Experiment:
        """ID로 실험 조회 (없으면 404)"""
        experiment = self.db.query(Experiment).filter(
            Experiment.experiment_id == experiment_id
        ).first()
        if not experiment:
            raise_not_found("Experiment", str(experiment_id))
        return experiment
    
    def get_by_tenant(self, tenant_id: UUID) -> List[Experiment]:
        """테넌트별 실험 목록"""
        return self.db.query(Experiment).filter(
            Experiment.tenant_id == tenant_id
        ).all()
    
    def get_active_experiments(self, tenant_id: UUID) -> List[Experiment]:
        """활성 실험 목록"""
        return self.db.query(Experiment).filter(
            Experiment.tenant_id == tenant_id,
            Experiment.status == 'active'
        ).all()
