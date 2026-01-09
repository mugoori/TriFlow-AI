# -*- coding: utf-8 -*-
"""Canary Deployment Pydantic Schemas

배포 관리 API를 위한 요청/응답 스키마 정의.
"""
from datetime import datetime
from typing import Optional, Literal, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ============================================
# Enums / Literals
# ============================================

DeploymentStatus = Literal["draft", "canary", "active", "rolled_back", "deprecated"]
CompensationStrategy = Literal["ignore", "mark_and_reprocess", "soft_delete"]
CanaryVersion = Literal["v1", "v2"]
IdentifierType = Literal["user", "session", "workflow_instance"]
VersionType = Literal["canary", "stable"]


# ============================================
# Canary Config
# ============================================

class CanaryConfig(BaseModel):
    """Canary 배포 설정"""
    auto_rollback_enabled: bool = Field(default=True, description="자동 롤백 활성화")
    min_samples: int = Field(default=100, ge=10, description="통계적 유의성을 위한 최소 샘플 수")

    # Circuit Breaker 임계값
    error_rate_threshold: float = Field(default=0.05, ge=0, le=1, description="절대 에러율 임계값 (5%)")
    relative_error_threshold: float = Field(default=2.0, ge=1, description="v1 대비 상대 에러율 임계값 (2x)")
    latency_p95_threshold: float = Field(default=1.5, ge=1, description="v1 대비 P95 레이턴시 임계값 (1.5x)")
    consecutive_failure_threshold: int = Field(default=5, ge=1, description="연속 실패 임계값")

    model_config = ConfigDict(extra="allow")


# ============================================
# Deployment Schemas
# ============================================

class DeploymentBase(BaseModel):
    """배포 기본 정보"""
    ruleset_id: UUID
    version: int
    changelog: str = Field(..., min_length=1, max_length=2000)


class DeploymentCreate(DeploymentBase):
    """배포 생성 요청"""
    canary_config: Optional[CanaryConfig] = None
    compensation_strategy: CompensationStrategy = "ignore"


class DeploymentUpdate(BaseModel):
    """배포 수정 요청"""
    changelog: Optional[str] = Field(None, min_length=1, max_length=2000)
    canary_config: Optional[CanaryConfig] = None
    compensation_strategy: Optional[CompensationStrategy] = None


class StartCanaryRequest(BaseModel):
    """Canary 시작 요청"""
    canary_pct: float = Field(..., gt=0, le=1, description="Canary 트래픽 비율 (0.1 = 10%)")
    canary_target_filter: Optional[dict[str, Any]] = Field(
        None,
        description="타겟 필터 (예: {line_codes: [...], shift: '...'})"
    )


class UpdateTrafficRequest(BaseModel):
    """트래픽 비율 조정 요청"""
    canary_pct: float = Field(..., ge=0, le=1, description="새 Canary 트래픽 비율")


class RollbackRequest(BaseModel):
    """롤백 요청"""
    reason: str = Field(..., min_length=1, max_length=500, description="롤백 사유")
    compensation_strategy: Optional[CompensationStrategy] = Field(
        None,
        description="롤백 시 데이터 처리 전략 (기본값: 배포 설정 사용)"
    )


class DeploymentResponse(BaseModel):
    """배포 응답"""
    deployment_id: UUID
    tenant_id: UUID
    ruleset_id: UUID
    version: int
    status: DeploymentStatus

    canary_pct: Optional[float] = None
    canary_target_filter: Optional[dict[str, Any]] = None
    canary_config: dict[str, Any] = Field(default_factory=dict)
    compensation_strategy: CompensationStrategy

    changelog: str
    approver_id: Optional[UUID] = None

    # 타임스탬프
    created_at: datetime
    started_at: Optional[datetime] = None
    deployed_at: Optional[datetime] = None
    promoted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None

    rollback_to: Optional[int] = None
    rollback_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# Assignment Schemas
# ============================================

class AssignmentResponse(BaseModel):
    """Canary 할당 응답"""
    assignment_id: UUID
    deployment_id: UUID
    identifier: str
    identifier_type: IdentifierType
    assigned_version: CanaryVersion
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_expired: bool

    model_config = ConfigDict(from_attributes=True)


class AssignmentListResponse(BaseModel):
    """할당 목록 응답"""
    assignments: list[AssignmentResponse]
    total: int
    page: int
    page_size: int


# ============================================
# Metrics Schemas
# ============================================

class MetricsSnapshot(BaseModel):
    """메트릭 스냅샷"""
    version_type: VersionType
    sample_count: int
    success_count: int
    error_count: int
    error_rate: float

    latency_p50_ms: Optional[int] = None
    latency_p95_ms: Optional[int] = None
    latency_p99_ms: Optional[int] = None
    latency_avg_ms: Optional[int] = None

    consecutive_failures: int
    window_start: datetime
    window_end: datetime


class MetricsComparison(BaseModel):
    """v1/v2 메트릭 비교"""
    deployment_id: UUID
    stable: Optional[MetricsSnapshot] = None
    canary: Optional[MetricsSnapshot] = None

    # 비교 결과
    error_rate_ratio: Optional[float] = Field(None, description="canary/stable 에러율 비율")
    latency_p95_ratio: Optional[float] = Field(None, description="canary/stable P95 레이턴시 비율")

    # 상태
    is_statistically_significant: bool = Field(default=False, description="통계적 유의성 여부")
    should_halt: bool = Field(default=False, description="Canary 중단 필요 여부")
    halt_reason: Optional[str] = None


class HealthStatus(BaseModel):
    """배포 건강 상태"""
    deployment_id: UUID
    status: DeploymentStatus
    is_healthy: bool

    # Circuit Breaker 상태
    circuit_state: Literal["closed", "open", "half_open"] = "closed"
    consecutive_failures: int = 0

    # 최근 메트릭
    stable_error_rate: Optional[float] = None
    canary_error_rate: Optional[float] = None

    # 경고/에러 메시지
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    last_checked_at: datetime


# ============================================
# Version Resolution
# ============================================

class VersionResolutionRequest(BaseModel):
    """버전 결정 요청 (내부 사용)"""
    deployment_id: UUID
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    workflow_instance_id: Optional[UUID] = None

    # JWT에서 추출한 캐시된 버전 (있으면 DB 조회 스킵)
    cached_version: Optional[CanaryVersion] = None


class VersionResolutionResponse(BaseModel):
    """버전 결정 응답"""
    deployment_id: UUID
    resolved_version: CanaryVersion
    resolution_source: Literal["jwt_cache", "redis_cache", "db", "new_assignment"]
    identifier: str
    identifier_type: IdentifierType


# ============================================
# Execution Log Schemas
# ============================================

class ExecutionLogCreate(BaseModel):
    """실행 로그 생성"""
    deployment_id: UUID
    execution_id: Optional[UUID] = None
    canary_version: CanaryVersion
    success: bool
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    rollback_safe: bool = True
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionLogResponse(BaseModel):
    """실행 로그 응답"""
    log_id: UUID
    deployment_id: UUID
    execution_id: Optional[UUID] = None
    canary_version: CanaryVersion
    success: bool
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    rollback_safe: bool
    needs_reprocess: bool
    reprocessed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================
# Response Headers (프론트엔드용)
# ============================================

class CanaryHeaders(BaseModel):
    """응답 헤더에 포함할 Canary 정보"""
    X_Canary_Version: Optional[str] = Field(None, alias="X-Canary-Version")
    X_Canary_Deployment_Id: Optional[str] = Field(None, alias="X-Canary-Deployment-Id")
