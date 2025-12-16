"""
Experiment Service
A/B 테스트 실험 관리 서비스
"""
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import (
    Experiment,
    ExperimentVariant,
    ExperimentAssignment,
    ExperimentMetric,
    Ruleset,
)

import logging
logger = logging.getLogger(__name__)


class ExperimentService:
    """A/B 테스트 실험 서비스"""

    def __init__(self, db: Session):
        self.db = db

    # ============ Experiment CRUD ============

    def create_experiment(
        self,
        tenant_id: UUID,
        name: str,
        description: Optional[str] = None,
        hypothesis: Optional[str] = None,
        traffic_percentage: int = 100,
        min_sample_size: int = 100,
        confidence_level: float = 0.95,
        created_by: Optional[UUID] = None,
    ) -> Experiment:
        """실험 생성"""
        experiment = Experiment(
            tenant_id=tenant_id,
            name=name,
            description=description,
            hypothesis=hypothesis,
            traffic_percentage=traffic_percentage,
            min_sample_size=min_sample_size,
            confidence_level=confidence_level,
            created_by=created_by,
            status="draft",
        )
        self.db.add(experiment)
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def get_experiment(self, experiment_id: UUID) -> Optional[Experiment]:
        """실험 조회"""
        return self.db.query(Experiment).filter(
            Experiment.experiment_id == experiment_id
        ).first()

    def list_experiments(
        self,
        tenant_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Experiment]:
        """실험 목록 조회"""
        query = self.db.query(Experiment)
        if tenant_id:
            query = query.filter(Experiment.tenant_id == tenant_id)
        if status:
            query = query.filter(Experiment.status == status)
        return query.order_by(Experiment.created_at.desc()).offset(offset).limit(limit).all()

    def update_experiment(
        self,
        experiment_id: UUID,
        **kwargs,
    ) -> Optional[Experiment]:
        """실험 수정 (draft 상태에서만 가능)"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return None
        if experiment.status != "draft":
            raise ValueError("실험이 draft 상태일 때만 수정할 수 있습니다")

        for key, value in kwargs.items():
            if hasattr(experiment, key) and value is not None:
                setattr(experiment, key, value)

        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def delete_experiment(self, experiment_id: UUID) -> bool:
        """실험 삭제 (draft 상태에서만 가능)"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return False
        if experiment.status not in ["draft", "cancelled"]:
            raise ValueError("draft 또는 cancelled 상태의 실험만 삭제할 수 있습니다")

        self.db.delete(experiment)
        self.db.commit()
        return True

    # ============ Variant Management ============

    def add_variant(
        self,
        experiment_id: UUID,
        name: str,
        ruleset_id: Optional[UUID] = None,
        is_control: bool = False,
        traffic_weight: int = 50,
        description: Optional[str] = None,
    ) -> ExperimentVariant:
        """실험 변형 추가"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError("실험을 찾을 수 없습니다")
        if experiment.status != "draft":
            raise ValueError("draft 상태의 실험에만 변형을 추가할 수 있습니다")

        variant = ExperimentVariant(
            experiment_id=experiment_id,
            name=name,
            ruleset_id=ruleset_id,
            is_control=is_control,
            traffic_weight=traffic_weight,
            description=description,
        )
        self.db.add(variant)
        self.db.commit()
        self.db.refresh(variant)
        return variant

    def update_variant(
        self,
        variant_id: UUID,
        **kwargs,
    ) -> Optional[ExperimentVariant]:
        """변형 수정"""
        variant = self.db.query(ExperimentVariant).filter(
            ExperimentVariant.variant_id == variant_id
        ).first()
        if not variant:
            return None

        experiment = self.get_experiment(variant.experiment_id)
        if experiment.status != "draft":
            raise ValueError("draft 상태의 실험에서만 변형을 수정할 수 있습니다")

        for key, value in kwargs.items():
            if hasattr(variant, key) and value is not None:
                setattr(variant, key, value)

        self.db.commit()
        self.db.refresh(variant)
        return variant

    def delete_variant(self, variant_id: UUID) -> bool:
        """변형 삭제"""
        variant = self.db.query(ExperimentVariant).filter(
            ExperimentVariant.variant_id == variant_id
        ).first()
        if not variant:
            return False

        experiment = self.get_experiment(variant.experiment_id)
        if experiment.status != "draft":
            raise ValueError("draft 상태의 실험에서만 변형을 삭제할 수 있습니다")

        self.db.delete(variant)
        self.db.commit()
        return True

    # ============ Experiment Lifecycle ============

    def start_experiment(self, experiment_id: UUID) -> Experiment:
        """실험 시작"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError("실험을 찾을 수 없습니다")
        if experiment.status != "draft":
            raise ValueError("draft 상태의 실험만 시작할 수 있습니다")

        # 변형 검증
        variants = experiment.variants
        if len(variants) < 2:
            raise ValueError("최소 2개의 변형이 필요합니다 (control + treatment)")

        # control 그룹 확인
        has_control = any(v.is_control for v in variants)
        if not has_control:
            raise ValueError("control 그룹이 필요합니다")

        # 트래픽 가중치 합계 확인
        total_weight = sum(v.traffic_weight for v in variants)
        if total_weight != 100:
            raise ValueError(f"변형들의 트래픽 가중치 합계가 100%여야 합니다 (현재: {total_weight}%)")

        experiment.status = "running"
        experiment.start_date = datetime.utcnow()
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def pause_experiment(self, experiment_id: UUID) -> Experiment:
        """실험 일시정지"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError("실험을 찾을 수 없습니다")
        if experiment.status != "running":
            raise ValueError("running 상태의 실험만 일시정지할 수 있습니다")

        experiment.status = "paused"
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def resume_experiment(self, experiment_id: UUID) -> Experiment:
        """실험 재개"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError("실험을 찾을 수 없습니다")
        if experiment.status != "paused":
            raise ValueError("paused 상태의 실험만 재개할 수 있습니다")

        experiment.status = "running"
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def complete_experiment(self, experiment_id: UUID) -> Experiment:
        """실험 완료"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError("실험을 찾을 수 없습니다")
        if experiment.status not in ["running", "paused"]:
            raise ValueError("running 또는 paused 상태의 실험만 완료할 수 있습니다")

        experiment.status = "completed"
        experiment.end_date = datetime.utcnow()
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def cancel_experiment(self, experiment_id: UUID) -> Experiment:
        """실험 취소"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError("실험을 찾을 수 없습니다")
        if experiment.status == "completed":
            raise ValueError("완료된 실험은 취소할 수 없습니다")

        experiment.status = "cancelled"
        experiment.end_date = datetime.utcnow()
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    # ============ Assignment Logic ============

    def assign_user_to_variant(
        self,
        experiment_id: UUID,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
    ) -> Optional[ExperimentAssignment]:
        """사용자를 실험 변형에 할당 (deterministic hashing)"""
        if not user_id and not session_id:
            raise ValueError("user_id 또는 session_id가 필요합니다")

        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return None
        if experiment.status != "running":
            return None

        # 기존 할당 확인
        existing = self.db.query(ExperimentAssignment).filter(
            ExperimentAssignment.experiment_id == experiment_id,
        )
        if user_id:
            existing = existing.filter(ExperimentAssignment.user_id == user_id)
        else:
            existing = existing.filter(ExperimentAssignment.session_id == session_id)

        existing_assignment = existing.first()
        if existing_assignment:
            return existing_assignment

        # 트래픽 비율 확인 - 실험 참여 여부 결정
        identifier = str(user_id) if user_id else session_id
        hash_input = f"{experiment_id}:{identifier}:participation"
        participation_hash = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 100

        if participation_hash >= experiment.traffic_percentage:
            return None  # 실험 미참여

        # 변형 할당 (가중치 기반)
        variants = sorted(experiment.variants, key=lambda v: v.variant_id)
        variant_hash_input = f"{experiment_id}:{identifier}:variant"
        variant_hash = int(hashlib.md5(variant_hash_input.encode()).hexdigest(), 16) % 100

        cumulative_weight = 0
        assigned_variant = None
        for variant in variants:
            cumulative_weight += variant.traffic_weight
            if variant_hash < cumulative_weight:
                assigned_variant = variant
                break

        if not assigned_variant:
            assigned_variant = variants[-1]

        # 할당 저장
        assignment = ExperimentAssignment(
            experiment_id=experiment_id,
            variant_id=assigned_variant.variant_id,
            user_id=user_id,
            session_id=session_id,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def get_user_assignment(
        self,
        experiment_id: UUID,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
    ) -> Optional[ExperimentAssignment]:
        """사용자의 실험 할당 조회"""
        query = self.db.query(ExperimentAssignment).filter(
            ExperimentAssignment.experiment_id == experiment_id,
        )
        if user_id:
            query = query.filter(ExperimentAssignment.user_id == user_id)
        else:
            query = query.filter(ExperimentAssignment.session_id == session_id)
        return query.first()

    def get_ruleset_for_user(
        self,
        experiment_id: UUID,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Ruleset]:
        """사용자에게 할당된 룰셋 조회"""
        assignment = self.assign_user_to_variant(
            experiment_id=experiment_id,
            user_id=user_id,
            session_id=session_id,
        )
        if not assignment:
            return None

        variant = self.db.query(ExperimentVariant).filter(
            ExperimentVariant.variant_id == assignment.variant_id
        ).first()

        if not variant or not variant.ruleset_id:
            return None

        return self.db.query(Ruleset).filter(
            Ruleset.ruleset_id == variant.ruleset_id
        ).first()

    # ============ Metrics ============

    def record_metric(
        self,
        experiment_id: UUID,
        variant_id: UUID,
        metric_name: str,
        metric_value: float,
        execution_id: Optional[UUID] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> ExperimentMetric:
        """메트릭 기록"""
        metric = ExperimentMetric(
            experiment_id=experiment_id,
            variant_id=variant_id,
            metric_name=metric_name,
            metric_value=metric_value,
            execution_id=execution_id,
            context_data=context_data or {},
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def get_experiment_stats(self, experiment_id: UUID) -> Dict[str, Any]:
        """실험 통계 조회"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return {}

        stats = {
            "experiment_id": str(experiment_id),
            "status": experiment.status,
            "variants": [],
        }

        for variant in experiment.variants:
            # 할당 수
            assignment_count = self.db.query(ExperimentAssignment).filter(
                ExperimentAssignment.variant_id == variant.variant_id
            ).count()

            # 메트릭 집계
            metrics_summary = {}
            metric_names = self.db.query(ExperimentMetric.metric_name).filter(
                ExperimentMetric.variant_id == variant.variant_id
            ).distinct().all()

            for (metric_name,) in metric_names:
                agg = self.db.query(
                    func.count(ExperimentMetric.metric_id),
                    func.avg(ExperimentMetric.metric_value),
                    func.stddev(ExperimentMetric.metric_value),
                    func.min(ExperimentMetric.metric_value),
                    func.max(ExperimentMetric.metric_value),
                ).filter(
                    ExperimentMetric.variant_id == variant.variant_id,
                    ExperimentMetric.metric_name == metric_name,
                ).first()

                metrics_summary[metric_name] = {
                    "count": agg[0] or 0,
                    "mean": float(agg[1]) if agg[1] else 0.0,
                    "stddev": float(agg[2]) if agg[2] else 0.0,
                    "min": float(agg[3]) if agg[3] else 0.0,
                    "max": float(agg[4]) if agg[4] else 0.0,
                }

            stats["variants"].append({
                "variant_id": str(variant.variant_id),
                "name": variant.name,
                "is_control": variant.is_control,
                "traffic_weight": variant.traffic_weight,
                "assignment_count": assignment_count,
                "metrics": metrics_summary,
            })

        # 총 할당 수
        stats["total_assignments"] = sum(v["assignment_count"] for v in stats["variants"])

        return stats

    def calculate_significance(
        self,
        experiment_id: UUID,
        metric_name: str,
    ) -> Dict[str, Any]:
        """통계적 유의성 계산 (간단한 Z-test)"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return {"error": "실험을 찾을 수 없습니다"}

        # control 그룹 찾기
        control_variant = None
        treatment_variants = []
        for v in experiment.variants:
            if v.is_control:
                control_variant = v
            else:
                treatment_variants.append(v)

        if not control_variant:
            return {"error": "control 그룹이 없습니다"}

        # control 그룹 통계
        control_agg = self.db.query(
            func.count(ExperimentMetric.metric_id),
            func.avg(ExperimentMetric.metric_value),
            func.stddev(ExperimentMetric.metric_value),
        ).filter(
            ExperimentMetric.variant_id == control_variant.variant_id,
            ExperimentMetric.metric_name == metric_name,
        ).first()

        control_n = control_agg[0] or 0
        control_mean = float(control_agg[1]) if control_agg[1] else 0.0
        control_std = float(control_agg[2]) if control_agg[2] else 0.0

        results = {
            "metric_name": metric_name,
            "control": {
                "name": control_variant.name,
                "n": control_n,
                "mean": control_mean,
                "std": control_std,
            },
            "treatments": [],
            "confidence_level": experiment.confidence_level,
            "min_sample_size": experiment.min_sample_size,
        }

        for treatment in treatment_variants:
            treatment_agg = self.db.query(
                func.count(ExperimentMetric.metric_id),
                func.avg(ExperimentMetric.metric_value),
                func.stddev(ExperimentMetric.metric_value),
            ).filter(
                ExperimentMetric.variant_id == treatment.variant_id,
                ExperimentMetric.metric_name == metric_name,
            ).first()

            treatment_n = treatment_agg[0] or 0
            treatment_mean = float(treatment_agg[1]) if treatment_agg[1] else 0.0
            treatment_std = float(treatment_agg[2]) if treatment_agg[2] else 0.0

            # Z-score 계산
            z_score = None
            p_value = None
            is_significant = False
            relative_diff = None

            if control_n > 0 and treatment_n > 0 and (control_std > 0 or treatment_std > 0):
                pooled_se = ((control_std ** 2 / control_n) + (treatment_std ** 2 / treatment_n)) ** 0.5
                if pooled_se > 0:
                    z_score = (treatment_mean - control_mean) / pooled_se
                    # 간단한 p-value 근사 (정규 분포 가정)
                    import math
                    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z_score) / math.sqrt(2))))
                    is_significant = p_value < (1 - experiment.confidence_level)

            if control_mean != 0:
                relative_diff = (treatment_mean - control_mean) / control_mean * 100

            results["treatments"].append({
                "name": treatment.name,
                "n": treatment_n,
                "mean": treatment_mean,
                "std": treatment_std,
                "z_score": z_score,
                "p_value": p_value,
                "is_significant": is_significant,
                "relative_diff_percent": relative_diff,
                "has_enough_samples": (control_n >= experiment.min_sample_size and
                                       treatment_n >= experiment.min_sample_size),
            })

        return results
