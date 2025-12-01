"""
Experiments Router
A/B 테스트 실험 관리 API
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Experiment, ExperimentVariant, Tenant
from app.services.experiment_service import ExperimentService

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["experiments"])


# ============ Pydantic Schemas ============

class VariantCreate(BaseModel):
    """변형 생성 요청"""
    name: str = Field(..., description="변형 이름 (control, treatment_a 등)")
    ruleset_id: Optional[str] = Field(None, description="연결할 룰셋 ID")
    is_control: bool = Field(False, description="대조군 여부")
    traffic_weight: int = Field(50, ge=1, le=100, description="트래픽 비율 (%)")
    description: Optional[str] = None


class VariantUpdate(BaseModel):
    """변형 수정 요청"""
    name: Optional[str] = None
    ruleset_id: Optional[str] = None
    is_control: Optional[bool] = None
    traffic_weight: Optional[int] = Field(None, ge=1, le=100)
    description: Optional[str] = None


class VariantResponse(BaseModel):
    """변형 응답"""
    variant_id: str
    experiment_id: str
    name: str
    description: Optional[str]
    is_control: bool
    ruleset_id: Optional[str]
    traffic_weight: int
    created_at: datetime

    class Config:
        from_attributes = True


class ExperimentCreate(BaseModel):
    """실험 생성 요청"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    hypothesis: Optional[str] = Field(None, description="실험 가설")
    traffic_percentage: int = Field(100, ge=1, le=100, description="실험 참여 트래픽 비율")
    min_sample_size: int = Field(100, ge=10, description="최소 샘플 크기")
    confidence_level: float = Field(0.95, ge=0.8, le=0.99, description="신뢰 수준")
    variants: Optional[List[VariantCreate]] = Field(None, description="변형 목록")


class ExperimentUpdate(BaseModel):
    """실험 수정 요청"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    traffic_percentage: Optional[int] = Field(None, ge=1, le=100)
    min_sample_size: Optional[int] = Field(None, ge=10)
    confidence_level: Optional[float] = Field(None, ge=0.8, le=0.99)


class ExperimentResponse(BaseModel):
    """실험 응답"""
    experiment_id: str
    tenant_id: str
    name: str
    description: Optional[str]
    hypothesis: Optional[str]
    status: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    traffic_percentage: int
    min_sample_size: int
    confidence_level: float
    created_at: datetime
    updated_at: datetime
    variants: List[VariantResponse] = []

    class Config:
        from_attributes = True


class ExperimentListResponse(BaseModel):
    """실험 목록 응답"""
    total: int
    experiments: List[ExperimentResponse]


class AssignmentRequest(BaseModel):
    """할당 요청"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class AssignmentResponse(BaseModel):
    """할당 응답"""
    experiment_id: str
    variant_id: str
    variant_name: str
    is_control: bool
    ruleset_id: Optional[str]
    assigned_at: datetime


class MetricRecordRequest(BaseModel):
    """메트릭 기록 요청"""
    variant_id: str
    metric_name: str = Field(..., description="메트릭 이름 (success_rate, response_time 등)")
    metric_value: float
    execution_id: Optional[str] = None
    context_data: Optional[dict] = None


class MetricResponse(BaseModel):
    """메트릭 응답"""
    metric_id: str
    experiment_id: str
    variant_id: str
    metric_name: str
    metric_value: float
    recorded_at: datetime


class StatsResponse(BaseModel):
    """통계 응답"""
    experiment_id: str
    status: str
    total_assignments: int
    variants: List[dict]


class SignificanceResponse(BaseModel):
    """유의성 검정 응답"""
    metric_name: str
    control: dict
    treatments: List[dict]
    confidence_level: float
    min_sample_size: int


# ============ Helper Functions ============

def _experiment_to_response(exp: Experiment) -> ExperimentResponse:
    """Experiment -> ExperimentResponse 변환"""
    variants = [
        VariantResponse(
            variant_id=str(v.variant_id),
            experiment_id=str(v.experiment_id),
            name=v.name,
            description=v.description,
            is_control=v.is_control,
            ruleset_id=str(v.ruleset_id) if v.ruleset_id else None,
            traffic_weight=v.traffic_weight,
            created_at=v.created_at,
        )
        for v in exp.variants
    ]
    return ExperimentResponse(
        experiment_id=str(exp.experiment_id),
        tenant_id=str(exp.tenant_id),
        name=exp.name,
        description=exp.description,
        hypothesis=exp.hypothesis,
        status=exp.status,
        start_date=exp.start_date,
        end_date=exp.end_date,
        traffic_percentage=exp.traffic_percentage,
        min_sample_size=exp.min_sample_size,
        confidence_level=exp.confidence_level,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
        variants=variants,
    )


# ============ API Endpoints ============

@router.post("", response_model=ExperimentResponse)
async def create_experiment(
    data: ExperimentCreate,
    db: Session = Depends(get_db),
):
    """
    새 실험 생성
    """
    # 테넌트 조회 (임시: 첫 번째 테넌트 사용)
    tenant = db.query(Tenant).first()
    if not tenant:
        raise HTTPException(status_code=400, detail="테넌트를 찾을 수 없습니다")

    service = ExperimentService(db)

    try:
        experiment = service.create_experiment(
            tenant_id=tenant.tenant_id,
            name=data.name,
            description=data.description,
            hypothesis=data.hypothesis,
            traffic_percentage=data.traffic_percentage,
            min_sample_size=data.min_sample_size,
            confidence_level=data.confidence_level,
        )

        # 변형 추가
        if data.variants:
            for v in data.variants:
                service.add_variant(
                    experiment_id=experiment.experiment_id,
                    name=v.name,
                    ruleset_id=UUID(v.ruleset_id) if v.ruleset_id else None,
                    is_control=v.is_control,
                    traffic_weight=v.traffic_weight,
                    description=v.description,
                )
            # refresh to get variants
            db.refresh(experiment)

        return _experiment_to_response(experiment)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=ExperimentListResponse)
async def list_experiments(
    status: Optional[str] = Query(None, description="필터: draft, running, paused, completed, cancelled"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    실험 목록 조회
    """
    service = ExperimentService(db)
    experiments = service.list_experiments(status=status, limit=limit, offset=offset)

    # 총 개수 (필터 적용)
    query = db.query(Experiment)
    if status:
        query = query.filter(Experiment.status == status)
    total = query.count()

    return ExperimentListResponse(
        total=total,
        experiments=[_experiment_to_response(e) for e in experiments],
    )


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    """
    실험 상세 조회
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)
    experiment = service.get_experiment(exp_uuid)

    if not experiment:
        raise HTTPException(status_code=404, detail="실험을 찾을 수 없습니다")

    return _experiment_to_response(experiment)


@router.put("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: str,
    data: ExperimentUpdate,
    db: Session = Depends(get_db),
):
    """
    실험 수정 (draft 상태에서만 가능)
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)

    try:
        experiment = service.update_experiment(
            experiment_id=exp_uuid,
            **data.model_dump(exclude_unset=True),
        )
        if not experiment:
            raise HTTPException(status_code=404, detail="실험을 찾을 수 없습니다")

        return _experiment_to_response(experiment)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{experiment_id}")
async def delete_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    """
    실험 삭제 (draft/cancelled 상태에서만 가능)
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)

    try:
        deleted = service.delete_experiment(exp_uuid)
        if not deleted:
            raise HTTPException(status_code=404, detail="실험을 찾을 수 없습니다")

        return {"message": "실험이 삭제되었습니다", "experiment_id": experiment_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ Variant Endpoints ============

@router.post("/{experiment_id}/variants", response_model=VariantResponse)
async def add_variant(
    experiment_id: str,
    data: VariantCreate,
    db: Session = Depends(get_db),
):
    """
    실험에 변형 추가
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)

    try:
        variant = service.add_variant(
            experiment_id=exp_uuid,
            name=data.name,
            ruleset_id=UUID(data.ruleset_id) if data.ruleset_id else None,
            is_control=data.is_control,
            traffic_weight=data.traffic_weight,
            description=data.description,
        )

        return VariantResponse(
            variant_id=str(variant.variant_id),
            experiment_id=str(variant.experiment_id),
            name=variant.name,
            description=variant.description,
            is_control=variant.is_control,
            ruleset_id=str(variant.ruleset_id) if variant.ruleset_id else None,
            traffic_weight=variant.traffic_weight,
            created_at=variant.created_at,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{experiment_id}/variants/{variant_id}", response_model=VariantResponse)
async def update_variant(
    experiment_id: str,
    variant_id: str,
    data: VariantUpdate,
    db: Session = Depends(get_db),
):
    """
    변형 수정
    """
    try:
        var_uuid = UUID(variant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid variant ID format")

    service = ExperimentService(db)

    try:
        update_data = data.model_dump(exclude_unset=True)
        if "ruleset_id" in update_data and update_data["ruleset_id"]:
            update_data["ruleset_id"] = UUID(update_data["ruleset_id"])

        variant = service.update_variant(variant_id=var_uuid, **update_data)
        if not variant:
            raise HTTPException(status_code=404, detail="변형을 찾을 수 없습니다")

        return VariantResponse(
            variant_id=str(variant.variant_id),
            experiment_id=str(variant.experiment_id),
            name=variant.name,
            description=variant.description,
            is_control=variant.is_control,
            ruleset_id=str(variant.ruleset_id) if variant.ruleset_id else None,
            traffic_weight=variant.traffic_weight,
            created_at=variant.created_at,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{experiment_id}/variants/{variant_id}")
async def delete_variant(
    experiment_id: str,
    variant_id: str,
    db: Session = Depends(get_db),
):
    """
    변형 삭제
    """
    try:
        var_uuid = UUID(variant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid variant ID format")

    service = ExperimentService(db)

    try:
        deleted = service.delete_variant(var_uuid)
        if not deleted:
            raise HTTPException(status_code=404, detail="변형을 찾을 수 없습니다")

        return {"message": "변형이 삭제되었습니다", "variant_id": variant_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ Lifecycle Endpoints ============

@router.post("/{experiment_id}/start", response_model=ExperimentResponse)
async def start_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    """
    실험 시작
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)

    try:
        experiment = service.start_experiment(exp_uuid)
        return _experiment_to_response(experiment)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{experiment_id}/pause", response_model=ExperimentResponse)
async def pause_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    """
    실험 일시정지
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)

    try:
        experiment = service.pause_experiment(exp_uuid)
        return _experiment_to_response(experiment)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{experiment_id}/resume", response_model=ExperimentResponse)
async def resume_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    """
    실험 재개
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)

    try:
        experiment = service.resume_experiment(exp_uuid)
        return _experiment_to_response(experiment)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{experiment_id}/complete", response_model=ExperimentResponse)
async def complete_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    """
    실험 완료
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)

    try:
        experiment = service.complete_experiment(exp_uuid)
        return _experiment_to_response(experiment)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{experiment_id}/cancel", response_model=ExperimentResponse)
async def cancel_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    """
    실험 취소
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)

    try:
        experiment = service.cancel_experiment(exp_uuid)
        return _experiment_to_response(experiment)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ Assignment Endpoints ============

@router.post("/{experiment_id}/assign", response_model=AssignmentResponse)
async def assign_to_experiment(
    experiment_id: str,
    data: AssignmentRequest,
    db: Session = Depends(get_db),
):
    """
    사용자를 실험 변형에 할당
    """
    if not data.user_id and not data.session_id:
        raise HTTPException(status_code=400, detail="user_id 또는 session_id가 필요합니다")

    try:
        exp_uuid = UUID(experiment_id)
        user_uuid = UUID(data.user_id) if data.user_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    service = ExperimentService(db)

    assignment = service.assign_user_to_variant(
        experiment_id=exp_uuid,
        user_id=user_uuid,
        session_id=data.session_id,
    )

    if not assignment:
        raise HTTPException(status_code=404, detail="실험에 할당할 수 없습니다 (실험이 running 상태가 아니거나 트래픽 외부)")

    # 변형 정보 조회
    variant = db.query(ExperimentVariant).filter(
        ExperimentVariant.variant_id == assignment.variant_id
    ).first()

    return AssignmentResponse(
        experiment_id=str(assignment.experiment_id),
        variant_id=str(assignment.variant_id),
        variant_name=variant.name if variant else "",
        is_control=variant.is_control if variant else False,
        ruleset_id=str(variant.ruleset_id) if variant and variant.ruleset_id else None,
        assigned_at=assignment.assigned_at,
    )


@router.get("/{experiment_id}/assignment")
async def get_assignment(
    experiment_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    사용자의 실험 할당 조회
    """
    if not user_id and not session_id:
        raise HTTPException(status_code=400, detail="user_id 또는 session_id가 필요합니다")

    try:
        exp_uuid = UUID(experiment_id)
        user_uuid = UUID(user_id) if user_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    service = ExperimentService(db)

    assignment = service.get_user_assignment(
        experiment_id=exp_uuid,
        user_id=user_uuid,
        session_id=session_id,
    )

    if not assignment:
        return {"assigned": False, "experiment_id": experiment_id}

    variant = db.query(ExperimentVariant).filter(
        ExperimentVariant.variant_id == assignment.variant_id
    ).first()

    return {
        "assigned": True,
        "experiment_id": str(assignment.experiment_id),
        "variant_id": str(assignment.variant_id),
        "variant_name": variant.name if variant else "",
        "is_control": variant.is_control if variant else False,
        "ruleset_id": str(variant.ruleset_id) if variant and variant.ruleset_id else None,
        "assigned_at": assignment.assigned_at,
    }


# ============ Metrics Endpoints ============

@router.post("/{experiment_id}/metrics", response_model=MetricResponse)
async def record_metric(
    experiment_id: str,
    data: MetricRecordRequest,
    db: Session = Depends(get_db),
):
    """
    실험 메트릭 기록
    """
    try:
        exp_uuid = UUID(experiment_id)
        var_uuid = UUID(data.variant_id)
        exec_uuid = UUID(data.execution_id) if data.execution_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    service = ExperimentService(db)

    metric = service.record_metric(
        experiment_id=exp_uuid,
        variant_id=var_uuid,
        metric_name=data.metric_name,
        metric_value=data.metric_value,
        execution_id=exec_uuid,
        context_data=data.context_data,
    )

    return MetricResponse(
        metric_id=str(metric.metric_id),
        experiment_id=str(metric.experiment_id),
        variant_id=str(metric.variant_id),
        metric_name=metric.metric_name,
        metric_value=metric.metric_value,
        recorded_at=metric.recorded_at,
    )


@router.get("/{experiment_id}/stats", response_model=StatsResponse)
async def get_experiment_stats(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    """
    실험 통계 조회
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)
    stats = service.get_experiment_stats(exp_uuid)

    if not stats:
        raise HTTPException(status_code=404, detail="실험을 찾을 수 없습니다")

    return StatsResponse(**stats)


@router.get("/{experiment_id}/significance/{metric_name}", response_model=SignificanceResponse)
async def get_significance(
    experiment_id: str,
    metric_name: str,
    db: Session = Depends(get_db),
):
    """
    통계적 유의성 검정
    """
    try:
        exp_uuid = UUID(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    service = ExperimentService(db)
    result = service.calculate_significance(exp_uuid, metric_name)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return SignificanceResponse(**result)
