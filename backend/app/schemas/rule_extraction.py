# -*- coding: utf-8 -*-
"""Rule Extraction Schemas

Decision Tree 기반 규칙 추출 API 스키마.

LRN-FR-030 스펙 참조
"""
from datetime import datetime
from typing import Optional, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# 규칙 추출 요청/응답
# ============================================


class RuleExtractionRequest(BaseModel):
    """규칙 추출 요청"""

    category: Optional[str] = Field(
        default=None,
        description="특정 카테고리로 제한 (threshold_adjustment, field_correction 등)",
    )
    min_samples: int = Field(
        default=20,
        ge=10,
        le=10000,
        description="최소 샘플 수 (기본: 20)",
    )
    max_depth: int = Field(
        default=5,
        ge=2,
        le=10,
        description="Decision Tree 최대 깊이 (기본: 5)",
    )
    min_quality_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="최소 품질 점수 (기본: 0.7)",
    )
    class_weight: Optional[Literal["balanced"]] = Field(
        default=None,
        description="클래스 불균형 처리 ('balanced' 또는 None)",
    )


class ExtractionMetrics(BaseModel):
    """추출 성능 메트릭"""

    coverage: float = Field(description="데이터 커버리지 (0-1)")
    precision: float = Field(description="정밀도 (0-1)")
    recall: float = Field(description="재현율 (0-1)")
    f1_score: float = Field(description="F1 점수 (0-1)")
    accuracy: float = Field(description="정확도 (0-1)")


class RuleExtractionResponse(BaseModel):
    """규칙 추출 응답"""

    candidate_id: UUID
    samples_used: int
    tree_depth: int
    feature_count: int
    class_count: int
    metrics: ExtractionMetrics
    rhai_preview: str = Field(description="Rhai 스크립트 미리보기 (처음 500자)")
    feature_importance: dict[str, float] = Field(
        default_factory=dict,
        description="특징 중요도 (feature_name: importance)",
    )


# ============================================
# 후보 관리
# ============================================


ApprovalStatus = Literal["pending", "approved", "rejected", "testing"]
GenerationMethod = Literal["pattern_mining", "llm", "ensemble", "hybrid"]


class CandidateResponse(BaseModel):
    """규칙 후보 상세"""

    candidate_id: UUID
    tenant_id: UUID
    ruleset_id: Optional[UUID] = None
    generated_rule: str
    generation_method: GenerationMethod
    coverage: float
    precision_score: float = Field(alias="precision")
    recall: float
    f1_score: float
    approval_status: ApprovalStatus
    test_results: Optional[dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[UUID] = None

    class Config:
        from_attributes = True
        populate_by_name = True


class CandidateListResponse(BaseModel):
    """후보 목록 응답"""

    items: list[CandidateResponse]
    total: int
    page: int
    page_size: int


# ============================================
# 테스트
# ============================================


class TestSample(BaseModel):
    """테스트 샘플"""

    input: dict[str, Any] = Field(description="입력 데이터")
    expected: dict[str, Any] = Field(description="예상 출력")


class TestRequest(BaseModel):
    """테스트 요청"""

    test_samples: list[TestSample] = Field(
        min_length=1,
        max_length=1000,
        description="테스트 샘플 목록",
    )


class TestResultDetail(BaseModel):
    """개별 테스트 결과"""

    sample_index: int
    input: dict[str, Any]
    expected: dict[str, Any]
    actual: dict[str, Any]
    passed: bool
    error: Optional[str] = None


class TestResponse(BaseModel):
    """테스트 결과"""

    total: int
    passed: int
    failed: int
    accuracy: float
    execution_time_ms: float
    details: list[TestResultDetail]


# ============================================
# 승인/거절
# ============================================


class ApproveRequest(BaseModel):
    """승인 요청"""

    rule_name: Optional[str] = Field(
        default=None,
        description="ProposedRule 이름 (미지정 시 자동 생성)",
    )
    description: Optional[str] = Field(
        default=None,
        description="규칙 설명",
    )


class ApproveResponse(BaseModel):
    """승인 응답 - ProposedRule 생성됨"""

    proposal_id: UUID
    rule_name: str
    confidence: float
    status: str


class RejectRequest(BaseModel):
    """거절 요청"""

    reason: str = Field(
        min_length=1,
        max_length=500,
        description="거절 사유",
    )


# ============================================
# 통계
# ============================================


class ExtractionStats(BaseModel):
    """규칙 추출 통계"""

    total_candidates: int
    pending_count: int
    approved_count: int
    rejected_count: int
    testing_count: int
    avg_f1_score: float
    avg_coverage: float
    recent_extractions: int = Field(description="최근 7일 추출 횟수")
    by_category: dict[str, int] = Field(
        default_factory=dict,
        description="카테고리별 후보 수",
    )
