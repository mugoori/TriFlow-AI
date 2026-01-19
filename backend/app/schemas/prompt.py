# -*- coding: utf-8 -*-
"""
Prompt Template Schemas
프롬프트 템플릿 관련 Pydantic 스키마
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ========== Request Schemas ==========


class PromptTemplateCreateRequest(BaseModel):
    """프롬프트 템플릿 생성 요청"""

    name: str = Field(..., description="템플릿 이름 (예: LearningAgent)")
    purpose: str = Field(..., description="템플릿 용도 설명")
    template_type: str = Field(
        ...,
        description="템플릿 타입",
        pattern="^(judgment|chat|reasoning|extraction)$",
    )
    model_config: Dict[str, Any] = Field(
        ..., description="모델 설정 (model, temperature, max_tokens)"
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="변수 설정 (required, optional, defaults)",
    )
    system_prompt: str = Field(..., description="시스템 프롬프트")
    user_prompt_template: str = Field(..., description="사용자 프롬프트 템플릿")
    locale: str = Field(default="ko-KR", description="로케일")
    few_shot_examples: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Few-shot 예제 리스트"
    )


class PromptTemplateUpdateRequest(BaseModel):
    """프롬프트 템플릿 수정 요청"""

    purpose: Optional[str] = None
    model_config: Optional[Dict[str, Any]] = None
    variables: Optional[Dict[str, Any]] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    few_shot_examples: Optional[List[Dict[str, Any]]] = None


class FewShotExampleSelectRequest(BaseModel):
    """Few-shot example 자동 선택 요청"""

    golden_set_id: UUID = Field(..., description="Golden Sample Set ID")
    k: int = Field(default=5, ge=1, le=10, description="선택할 샘플 수 (1-10)")
    strategy: str = Field(
        default="hybrid",
        description="선택 전략 (quality_rank, balanced, diverse, hybrid)",
        pattern="^(quality_rank|balanced|diverse|hybrid)$",
    )
    diversity_weight: float = Field(
        default=0.3, ge=0, le=1, description="다양성 가중치 (0-1)"
    )
    quality_weight: float = Field(
        default=0.7, ge=0, le=1, description="품질 가중치 (0-1)"
    )
    category: Optional[str] = Field(
        default=None, description="특정 카테고리만 선택 (선택)"
    )


# ========== Response Schemas ==========


class PromptMetricsResponse(BaseModel):
    """프롬프트 성능 메트릭 응답"""

    avg_tokens_per_call: Optional[int] = None
    avg_latency_ms: Optional[int] = None
    success_rate: Optional[float] = None
    validation_error_rate: Optional[float] = None
    last_update: Optional[datetime] = None
    total_calls: Optional[int] = None


class PromptTemplateResponse(BaseModel):
    """프롬프트 템플릿 응답"""

    template_id: UUID
    tenant_id: UUID
    name: str
    purpose: str
    version: int
    template_type: str
    is_active: bool
    a_b_test_group: Optional[str] = None
    model_config: Dict[str, Any]
    variables: Dict[str, Any]
    metrics: Optional[PromptMetricsResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptTemplateBodyResponse(BaseModel):
    """프롬프트 템플릿 본문 응답"""

    body_id: UUID
    template_id: UUID
    locale: str
    system_prompt: str
    user_prompt_template: str
    few_shot_examples: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PromptTemplateDetailResponse(BaseModel):
    """프롬프트 템플릿 상세 응답"""

    template: PromptTemplateResponse
    bodies: List[PromptTemplateBodyResponse]


class PromptComparisonResponse(BaseModel):
    """프롬프트 버전 비교 응답"""

    template_1: Dict[str, Any]
    template_2: Dict[str, Any]
    delta: Dict[str, Any]


class FewShotExamplesResponse(BaseModel):
    """Few-shot examples 응답"""

    examples: List[Dict[str, Any]]
    count: int
    strategy: str
    golden_set_id: UUID
