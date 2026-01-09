# -*- coding: utf-8 -*-
"""Sample Curation Pydantic Schemas

샘플 큐레이션 API를 위한 요청/응답 스키마 정의.
"""
from datetime import datetime
from typing import Optional, Literal, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ============================================
# Enums / Literals
# ============================================

SourceType = Literal["feedback", "validation", "manual"]
SampleStatus = Literal["pending", "approved", "rejected", "archived"]
SampleCategory = Literal["threshold_adjustment", "field_correction", "validation_failure", "general"]
ExportFormat = Literal["json", "csv"]


# ============================================
# Sample Schemas
# ============================================

class SampleBase(BaseModel):
    """샘플 기본 정보"""
    category: str = Field(..., min_length=1, max_length=50)
    input_data: dict[str, Any]
    expected_output: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)


class SampleCreate(SampleBase):
    """샘플 생성 요청 (수동)"""
    source_type: SourceType = "manual"
    feedback_id: Optional[UUID] = None
    execution_id: Optional[UUID] = None
    quality_score: Optional[float] = Field(None, ge=0, le=1, description="품질 점수 (0.0 ~ 1.0)")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="신뢰도 (0.0 ~ 1.0)")


class SampleUpdate(BaseModel):
    """샘플 수정 요청"""
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    input_data: Optional[dict[str, Any]] = None
    expected_output: Optional[dict[str, Any]] = None
    context: Optional[dict[str, Any]] = None
    quality_score: Optional[float] = Field(None, ge=0, le=1)
    confidence: Optional[float] = Field(None, ge=0, le=1)


class SampleApproveRequest(BaseModel):
    """샘플 승인 요청"""
    pass  # 추가 정보 없이 승인


class SampleRejectRequest(BaseModel):
    """샘플 거부 요청"""
    reason: str = Field(..., min_length=1, max_length=500, description="거부 사유")


class SampleExtractRequest(BaseModel):
    """피드백에서 샘플 자동 추출 요청"""
    days: int = Field(default=7, ge=1, le=90, description="추출할 피드백 기간 (일)")
    min_confidence: float = Field(default=0.5, ge=0, le=1, description="최소 신뢰도")
    categories: Optional[list[str]] = Field(None, description="추출할 카테고리 (미지정 시 전체)")
    dry_run: bool = Field(default=False, description="True면 추출 결과만 반환, DB 저장 안 함")


class SampleResponse(BaseModel):
    """샘플 응답"""
    sample_id: UUID
    tenant_id: UUID
    feedback_id: Optional[UUID] = None
    execution_id: Optional[UUID] = None
    source_type: SourceType

    category: str
    input_data: dict[str, Any]
    expected_output: dict[str, Any]
    context: dict[str, Any]

    quality_score: float
    confidence: float
    content_hash: str

    status: SampleStatus
    rejection_reason: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class SampleListResponse(BaseModel):
    """샘플 목록 응답"""
    samples: list[SampleResponse]
    total: int
    page: int
    page_size: int


class SampleExtractResponse(BaseModel):
    """샘플 추출 응답"""
    extracted_count: int
    skipped_duplicates: int
    samples: list[SampleResponse]
    dry_run: bool


class SampleStats(BaseModel):
    """샘플 통계"""
    total_count: int
    pending_count: int
    approved_count: int
    rejected_count: int
    archived_count: int

    by_category: dict[str, int] = Field(default_factory=dict)
    by_source_type: dict[str, int] = Field(default_factory=dict)

    avg_quality_score: float
    min_quality_score: float
    max_quality_score: float


# ============================================
# Golden Sample Set Schemas
# ============================================

class GoldenSetBase(BaseModel):
    """골든 샘플셋 기본 정보"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=50, description="특정 카테고리로 제한 (미지정 시 전체)")


class GoldenSetCreate(GoldenSetBase):
    """골든 샘플셋 생성 요청"""
    min_quality_score: float = Field(default=0.7, ge=0, le=1, description="최소 품질 점수")
    max_samples: int = Field(default=1000, ge=1, le=100000, description="최대 샘플 수")
    auto_update: bool = Field(default=True, description="자동 업데이트 여부")
    config: dict[str, Any] = Field(default_factory=dict)


class GoldenSetUpdate(BaseModel):
    """골든 샘플셋 수정 요청"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=50)
    min_quality_score: Optional[float] = Field(None, ge=0, le=1)
    max_samples: Optional[int] = Field(None, ge=1, le=100000)
    auto_update: Optional[bool] = None
    is_active: Optional[bool] = None
    config: Optional[dict[str, Any]] = None


class GoldenSetAddSampleRequest(BaseModel):
    """골든 샘플셋에 샘플 추가 요청"""
    sample_id: UUID


class GoldenSetAutoUpdateRequest(BaseModel):
    """골든 샘플셋 자동 업데이트 요청"""
    force: bool = Field(default=False, description="True면 max_samples 제한 무시하고 갱신")


class GoldenSetResponse(BaseModel):
    """골든 샘플셋 응답"""
    set_id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None

    min_quality_score: float
    max_samples: int
    auto_update: bool
    config: dict[str, Any]

    is_active: bool
    sample_count: int

    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class GoldenSetListResponse(BaseModel):
    """골든 샘플셋 목록 응답"""
    sets: list[GoldenSetResponse]
    total: int


class GoldenSetSampleListResponse(BaseModel):
    """골든 샘플셋 샘플 목록 응답"""
    set_id: UUID
    samples: list[SampleResponse]
    total: int
    page: int
    page_size: int


class GoldenSetAutoUpdateResponse(BaseModel):
    """골든 샘플셋 자동 업데이트 응답"""
    set_id: UUID
    added_count: int
    removed_count: int
    current_sample_count: int


class GoldenSetMemberResponse(BaseModel):
    """골든 샘플셋 멤버 응답"""
    set_id: UUID
    sample_id: UUID
    added_at: datetime
    added_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# Export Schemas
# ============================================

class ExportRequest(BaseModel):
    """내보내기 요청"""
    format: ExportFormat = "json"
    include_metadata: bool = Field(default=True, description="메타데이터 포함 여부")


class ExportResponse(BaseModel):
    """내보내기 응답 (메타데이터)"""
    set_id: UUID
    format: ExportFormat
    sample_count: int
    file_size_bytes: int
    exported_at: datetime
