# -*- coding: utf-8 -*-
"""
Auto Execution API 스키마

Trust-based 자동 실행 시스템 API 스키마 정의.
"""
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# Decision Matrix 스키마
# ============================================

class DecisionMatrixEntry(BaseModel):
    """Decision Matrix 엔트리"""
    matrix_id: Optional[str] = None
    trust_level: int = Field(..., ge=0, le=3, description="Trust Level (0-3)")
    risk_level: str = Field(..., description="Risk Level (LOW, MEDIUM, HIGH, CRITICAL)")
    decision: str = Field(..., description="Decision (auto_execute, require_approval, reject)")
    min_trust_score: Optional[float] = Field(None, ge=0, le=1, description="최소 Trust Score")
    max_consecutive_failures: Optional[int] = Field(None, ge=0, description="최대 연속 실패 허용")
    require_recent_success: bool = Field(default=False, description="최근 성공 필요 여부")
    cooldown_seconds: Optional[int] = Field(None, ge=0, description="재실행 대기 시간")
    description: Optional[str] = None
    is_active: bool = True


class DecisionMatrixUpdateRequest(BaseModel):
    """Decision Matrix 업데이트 요청"""
    decision: Optional[str] = Field(None, description="Decision (auto_execute, require_approval, reject)")
    min_trust_score: Optional[float] = Field(None, ge=0, le=1)
    max_consecutive_failures: Optional[int] = Field(None, ge=0)
    require_recent_success: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None


class DecisionMatrixResponse(BaseModel):
    """Decision Matrix 응답"""
    tenant_id: str
    entries: list[DecisionMatrixEntry]
    summary: dict[str, dict[str, str]]  # trust_level -> risk_level -> decision


# ============================================
# Action Risk 스키마
# ============================================

class ActionRiskDefinitionCreate(BaseModel):
    """Action Risk 정의 생성 요청"""
    action_type: str = Field(..., min_length=1, max_length=100)
    risk_level: str = Field(..., description="Risk Level (LOW, MEDIUM, HIGH, CRITICAL)")
    action_pattern: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=50)
    risk_score: Optional[int] = Field(None, ge=0, le=100)
    reversible: bool = True
    affects_production: bool = False
    affects_finance: bool = False
    affects_compliance: bool = False
    description: Optional[str] = None
    priority: int = Field(default=100, ge=0)


class ActionRiskDefinitionUpdate(BaseModel):
    """Action Risk 정의 업데이트 요청"""
    risk_level: Optional[str] = None
    action_pattern: Optional[str] = None
    category: Optional[str] = None
    risk_score: Optional[int] = Field(None, ge=0, le=100)
    reversible: Optional[bool] = None
    affects_production: Optional[bool] = None
    affects_finance: Optional[bool] = None
    affects_compliance: Optional[bool] = None
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0)


class ActionRiskDefinitionResponse(BaseModel):
    """Action Risk 정의 응답"""
    risk_def_id: str
    tenant_id: str
    action_type: str
    action_pattern: Optional[str]
    category: Optional[str]
    risk_level: str
    risk_score: Optional[int]
    reversible: bool
    affects_production: bool
    affects_finance: bool
    affects_compliance: bool
    description: Optional[str]
    priority: int
    is_active: bool
    created_at: str


# ============================================
# Execution Evaluation 스키마
# ============================================

class ExecutionEvaluateRequest(BaseModel):
    """실행 결정 평가 요청"""
    action_type: str = Field(..., min_length=1, max_length=100)
    ruleset_id: Optional[str] = None
    trust_level_override: Optional[int] = Field(None, ge=0, le=3)
    trust_score_override: Optional[float] = Field(None, ge=0, le=1)


class ExecutionEvaluateResponse(BaseModel):
    """실행 결정 평가 응답"""
    decision: str  # auto_execute, require_approval, reject
    reason: str
    trust_level: int
    trust_level_name: str
    trust_score: Optional[float]
    risk_level: str
    risk_score: Optional[int]
    risk_info: Optional[dict]
    can_auto_execute: bool


# ============================================
# Execution Log 스키마
# ============================================

class AutoExecutionLogResponse(BaseModel):
    """자동 실행 로그 응답"""
    log_id: str
    tenant_id: str
    workflow_id: Optional[str]
    instance_id: Optional[str]
    node_id: Optional[str]
    ruleset_id: Optional[str]
    action_type: str
    action_params: Optional[dict]
    trust_level: int
    trust_score: Optional[float]
    risk_level: str
    risk_score: Optional[int]
    decision: str
    decision_reason: Optional[str]
    execution_status: str
    execution_result: Optional[dict]
    approval_id: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[str]
    error_message: Optional[str]
    latency_ms: Optional[int]
    created_at: str
    executed_at: Optional[str]


class AutoExecutionLogListResponse(BaseModel):
    """자동 실행 로그 목록 응답"""
    logs: list[AutoExecutionLogResponse]
    total: int
    limit: int
    offset: int


class PendingApprovalResponse(BaseModel):
    """승인 대기 항목 응답"""
    log_id: str
    action_type: str
    action_params: Optional[dict]
    trust_level: int
    trust_level_name: str
    risk_level: str
    decision_reason: Optional[str]
    workflow_id: Optional[str]
    ruleset_id: Optional[str]
    created_at: str


class ApprovalActionRequest(BaseModel):
    """승인/거부 요청"""
    action: str = Field(..., description="approve 또는 reject")
    reason: Optional[str] = None


# ============================================
# Stats 스키마
# ============================================

class ExecutionStatsResponse(BaseModel):
    """실행 통계 응답"""
    total: int
    by_decision: dict[str, int]
    by_status: dict[str, int]
    auto_execution_rate: float
    avg_latency_ms: int


class RiskSummaryResponse(BaseModel):
    """위험도 요약 응답"""
    total: int
    by_level: dict[str, int]
    by_category: dict[str, int]
