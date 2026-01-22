# -*- coding: utf-8 -*-
"""
Prompts API Router
프롬프트 템플릿 관리 API
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, PromptTemplate, PromptTemplateBody
from app.auth.dependencies import get_current_user
from app.services.rbac_service import require_admin
from app.services.prompt_service import PromptService
from app.services.few_shot_selector import FewShotSelector
from app.services.prompt_metrics_aggregator import PromptMetricsAggregator
from app.services.prompt_auto_tuner import get_prompt_auto_tuner
from app.schemas.prompt import (
    PromptTemplateCreateRequest,
    PromptTemplateUpdateRequest,
    PromptTemplateResponse,
    PromptTemplateDetailResponse,
    PromptTemplateBodyResponse,
    PromptMetricsResponse,
    PromptComparisonResponse,
    FewShotExampleSelectRequest,
    FewShotExamplesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/templates", response_model=PromptTemplateResponse)
async def create_prompt_template(
    request: PromptTemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    프롬프트 템플릿 생성 (ADMIN 전용)

    새로운 프롬프트 템플릿 버전을 생성합니다.
    """
    try:
        service = PromptService(db)
        template = service.create_prompt_version(
            tenant_id=current_user.tenant_id,
            name=request.name,
            purpose=request.purpose,
            template_type=request.template_type,
            model_config=request.model_config,
            variables=request.variables,
            system_prompt=request.system_prompt,
            user_prompt_template=request.user_prompt_template,
            locale=request.locale,
            few_shot_examples=request.few_shot_examples,
            created_by=current_user.user_id,
        )

        return PromptTemplateResponse.from_orm(template)

    except Exception as e:
        logger.error(f"Failed to create prompt template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프롬프트 템플릿 생성에 실패했습니다",
        )


@router.get("/templates", response_model=List[PromptTemplateResponse])
async def list_prompt_templates(
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    프롬프트 템플릿 목록 조회

    Args:
        name: 템플릿 이름 필터
        is_active: 활성 상태 필터
    """
    service = PromptService(db)
    templates = service.list_prompt_versions(
        tenant_id=current_user.tenant_id, name=name, is_active=is_active
    )

    return [PromptTemplateResponse.from_orm(t) for t in templates]


@router.get("/templates/{template_id}", response_model=PromptTemplateDetailResponse)
async def get_prompt_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """프롬프트 템플릿 상세 조회"""
    template = db.query(PromptTemplate).get(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="템플릿을 찾을 수 없습니다"
        )

    if template.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="접근 권한이 없습니다"
        )

    bodies = (
        db.query(PromptTemplateBody)
        .filter(PromptTemplateBody.template_id == template_id)
        .all()
    )

    return PromptTemplateDetailResponse(
        template=PromptTemplateResponse.from_orm(template),
        bodies=[PromptTemplateBodyResponse.from_orm(b) for b in bodies],
    )


@router.post("/templates/{template_id}/activate", response_model=PromptTemplateResponse)
async def activate_prompt_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """프롬프트 템플릿 버전 활성화 (ADMIN 전용)"""
    service = PromptService(db)

    try:
        template = service.activate_prompt_version(template_id)
        return PromptTemplateResponse.from_orm(template)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/templates/{template_id}/deactivate", response_model=PromptTemplateResponse
)
async def deactivate_prompt_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """프롬프트 템플릿 버전 비활성화 (ADMIN 전용)"""
    service = PromptService(db)

    try:
        template = service.deactivate_prompt_version(template_id)
        return PromptTemplateResponse.from_orm(template)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/templates/{template_id}/metrics", response_model=PromptMetricsResponse)
async def get_prompt_metrics(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """프롬프트 성능 메트릭 조회"""
    aggregator = PromptMetricsAggregator(db)

    try:
        summary = aggregator.get_performance_summary(template_id)
        return PromptMetricsResponse(**summary["metrics"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/templates/{template_id}/update-metrics", response_model=PromptMetricsResponse
)
async def update_prompt_metrics(
    template_id: UUID,
    time_window_hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """프롬프트 메트릭 수동 업데이트 (ADMIN 전용)"""
    aggregator = PromptMetricsAggregator(db)

    try:
        metrics = aggregator.update_prompt_metrics(template_id, time_window_hours)
        return PromptMetricsResponse(**metrics)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/templates/compare", response_model=PromptComparisonResponse)
async def compare_prompt_templates(
    template_id_1: UUID,
    template_id_2: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """두 프롬프트 버전 성능 비교"""
    service = PromptService(db)

    try:
        comparison = service.compare_prompt_versions(template_id_1, template_id_2)
        return PromptComparisonResponse(**comparison)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/templates/{template_id}/select-examples", response_model=FewShotExamplesResponse
)
async def select_few_shot_examples(
    template_id: UUID,
    request: FewShotExampleSelectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Few-shot examples 자동 선택 (ADMIN 전용)

    Golden Sample Set에서 최적의 examples를 선택하고
    프롬프트 템플릿에 저장합니다.
    """
    selector = FewShotSelector(db)

    try:
        # Select samples
        samples = selector.select_examples(
            golden_set_id=request.golden_set_id,
            k=request.k,
            strategy=request.strategy,
            diversity_weight=request.diversity_weight,
            quality_weight=request.quality_weight,
            category=request.category,
        )

        # Convert to few-shot format
        examples = []
        for sample in samples:
            examples.append(
                {
                    "sample_id": str(sample.sample_id),
                    "input": sample.input_data,
                    "output": sample.expected_output,
                    "quality_score": float(sample.quality_score)
                    if sample.quality_score
                    else None,
                    "category": sample.category,
                }
            )

        # Update template body with examples
        body = (
            db.query(PromptTemplateBody)
            .filter(PromptTemplateBody.template_id == template_id)
            .first()
        )

        if body:
            body.few_shot_examples = examples
            db.commit()
            logger.info(
                f"Updated {len(examples)} few-shot examples for template {template_id}"
            )

        return FewShotExamplesResponse(
            examples=examples,
            count=len(examples),
            strategy=request.strategy,
            golden_set_id=request.golden_set_id,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to select few-shot examples: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Few-shot example 선택에 실패했습니다",
        )


@router.post("/templates/{template_id}/auto-tune")
async def auto_tune_prompt(
    template_id: UUID,
    max_examples: int = 5,
    min_rating: float = 4.0,
    time_window_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    프롬프트 자동 튜닝 (ADMIN 전용)

    긍정 피드백 샘플을 Few-shot 예시로 자동 추가합니다.

    Args:
        template_id: 프롬프트 템플릿 ID
        max_examples: 최대 Few-shot 개수 (기본 5개)
        min_rating: 최소 평점 (기본 4.0)
        time_window_days: 샘플 수집 기간 (기본 30일)

    Returns:
        {
            "added_count": int,
            "total_examples": int,
            "template_id": str,
        }
    """
    auto_tuner = get_prompt_auto_tuner(db)

    try:
        result = auto_tuner.auto_add_few_shots(
            template_id=template_id,
            max_examples=max_examples,
            min_rating=min_rating,
            time_window_days=time_window_days,
        )

        logger.info(
            f"Auto-tuned template {template_id}: "
            f"added {result['added_count']} examples"
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to auto-tune prompt: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프롬프트 자동 튜닝에 실패했습니다",
        )


@router.post("/templates/auto-tune-all")
async def auto_tune_all_prompts(
    max_examples: int = 5,
    min_rating: float = 4.0,
    time_window_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    모든 활성 프롬프트 자동 튜닝 (ADMIN 전용)

    모든 활성 프롬프트에 Few-shot 예시를 자동 추가합니다.

    Args:
        max_examples: 최대 Few-shot 개수
        min_rating: 최소 평점
        time_window_days: 샘플 수집 기간

    Returns:
        {
            "tuned_count": int,
            "total_templates": int,
            "total_examples_added": int,
        }
    """
    auto_tuner = get_prompt_auto_tuner(db)

    try:
        result = auto_tuner.auto_tune_all_templates(
            max_examples=max_examples,
            min_rating=min_rating,
            time_window_days=time_window_days,
        )

        logger.info(
            f"Auto-tuned {result['tuned_count']} templates, "
            f"added {result['total_examples_added']} examples"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to auto-tune all prompts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="전체 프롬프트 자동 튜닝에 실패했습니다",
        )


@router.get("/templates/{template_id}/tuning-candidates")
async def get_tuning_candidates(
    template_id: UUID,
    min_rating: float = 4.0,
    time_window_days: int = 30,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Few-shot 후보 샘플 조회

    자동 튜닝 전 어떤 샘플이 추가될지 미리 확인합니다.

    Args:
        template_id: 프롬프트 템플릿 ID
        min_rating: 최소 평점
        time_window_days: 샘플 수집 기간
        limit: 최대 개수

    Returns:
        후보 샘플 리스트
    """
    auto_tuner = get_prompt_auto_tuner(db)

    try:
        candidates = auto_tuner.get_tuning_candidates(
            template_id=template_id,
            min_rating=min_rating,
            time_window_days=time_window_days,
            limit=limit,
        )

        return {
            "candidates": candidates,
            "count": len(candidates),
            "template_id": str(template_id),
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


logger.info("Prompts router initialized")
