# -*- coding: utf-8 -*-
"""Auto Execution 모델

Trust-based 자동 실행 시스템을 위한 SQLAlchemy 모델:
- DecisionMatrix: Trust Level × Risk Level → Decision 매핑
- ActionRiskDefinition: 작업 유형별 위험도 정의
- AutoExecutionLog: 자동 실행 이력 로깅
"""
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Text,
    DateTime,
    Numeric,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class RiskLevel:
    """Risk Level 상수"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.LOW, cls.MEDIUM, cls.HIGH, cls.CRITICAL]


class ExecutionDecision:
    """실행 결정 상수"""
    AUTO_EXECUTE = "auto_execute"
    REQUIRE_APPROVAL = "require_approval"
    REJECT = "reject"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.AUTO_EXECUTE, cls.REQUIRE_APPROVAL, cls.REJECT]


class ExecutionStatus:
    """실행 상태 상수"""
    PENDING = "pending"
    EXECUTED = "executed"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    SKIPPED = "skipped"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.PENDING, cls.EXECUTED, cls.APPROVED, cls.REJECTED, cls.FAILED, cls.SKIPPED]


class DecisionMatrix(Base):
    """Decision Matrix

    Trust Level과 Risk Level 조합에 따른 실행 결정 매핑.
    테넌트별로 커스터마이징 가능.
    """

    __tablename__ = "decision_matrix"
    __table_args__ = (
        CheckConstraint(
            "trust_level >= 0 AND trust_level <= 3",
            name="ck_decision_matrix_trust_level"
        ),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_decision_matrix_risk_level"
        ),
        CheckConstraint(
            "decision IN ('auto_execute', 'require_approval', 'reject')",
            name="ck_decision_matrix_decision"
        ),
        UniqueConstraint(
            'tenant_id', 'trust_level', 'risk_level',
            name='uq_decision_matrix_tenant_levels'
        ),
        Index(
            'idx_decision_matrix_tenant_active',
            'tenant_id', 'is_active'
        ),
        {"schema": "core", "extend_existing": True}
    )

    matrix_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )

    # 조건: Trust Level (0-3) × Risk Level
    trust_level = Column(Integer, nullable=False)
    risk_level = Column(String(20), nullable=False)

    # 결정
    decision = Column(String(30), nullable=False)

    # 추가 조건 (선택적)
    min_trust_score = Column(Numeric(5, 4), nullable=True)
    max_consecutive_failures = Column(Integer, nullable=True)
    require_recent_success = Column(Boolean, default=False)
    cooldown_seconds = Column(Integer, nullable=True)

    # 메타데이터
    description = Column(Text, nullable=True)
    matrix_metadata = Column(JSONB, default=dict, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)

    def __repr__(self):
        return (
            f"<DecisionMatrix("
            f"trust_level={self.trust_level}, "
            f"risk_level={self.risk_level}, "
            f"decision={self.decision})>"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix_id": str(self.matrix_id),
            "tenant_id": str(self.tenant_id),
            "trust_level": self.trust_level,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "min_trust_score": float(self.min_trust_score) if self.min_trust_score else None,
            "max_consecutive_failures": self.max_consecutive_failures,
            "require_recent_success": self.require_recent_success,
            "cooldown_seconds": self.cooldown_seconds,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ActionRiskDefinition(Base):
    """Action Risk Definition

    작업 유형별 위험도 정의.
    패턴 매칭으로 유사 작업 그룹화 가능.
    """

    __tablename__ = "action_risk_definitions"
    __table_args__ = (
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_action_risk_risk_level"
        ),
        UniqueConstraint(
            'tenant_id', 'action_type',
            name='uq_action_risk_tenant_type'
        ),
        Index(
            'idx_action_risk_tenant_type',
            'tenant_id', 'action_type'
        ),
        Index(
            'idx_action_risk_tenant_category',
            'tenant_id', 'category'
        ),
        {"schema": "core", "extend_existing": True}
    )

    risk_def_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )

    # 작업 식별
    action_type = Column(String(100), nullable=False)
    action_pattern = Column(String(255), nullable=True)  # 패턴 매칭
    category = Column(String(50), nullable=True)  # mes, erp, notification, data

    # 위험도 정의
    risk_level = Column(String(20), nullable=False)
    risk_score = Column(Integer, nullable=True)  # 0-100

    # 위험 요소
    reversible = Column(Boolean, default=True)
    affects_production = Column(Boolean, default=False)
    affects_finance = Column(Boolean, default=False)
    affects_compliance = Column(Boolean, default=False)

    # 메타데이터
    description = Column(Text, nullable=True)
    risk_factors = Column(JSONB, default=dict, nullable=True)
    mitigation_notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # 우선순위
    priority = Column(Integer, default=100, nullable=False)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<ActionRiskDefinition("
            f"action_type={self.action_type}, "
            f"risk_level={self.risk_level})>"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_def_id": str(self.risk_def_id),
            "tenant_id": str(self.tenant_id),
            "action_type": self.action_type,
            "action_pattern": self.action_pattern,
            "category": self.category,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "reversible": self.reversible,
            "affects_production": self.affects_production,
            "affects_finance": self.affects_finance,
            "affects_compliance": self.affects_compliance,
            "description": self.description,
            "risk_factors": self.risk_factors,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AutoExecutionLog(Base):
    """Auto Execution Log

    자동 실행 이력 로깅.
    Trust/Risk 평가 결과와 실행 결과를 기록.
    """

    __tablename__ = "auto_execution_logs"
    __table_args__ = (
        CheckConstraint(
            "trust_level >= 0 AND trust_level <= 3",
            name="ck_auto_exec_log_trust_level"
        ),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_auto_exec_log_risk_level"
        ),
        CheckConstraint(
            "decision IN ('auto_execute', 'require_approval', 'reject')",
            name="ck_auto_exec_log_decision"
        ),
        CheckConstraint(
            "execution_status IN ('pending', 'executed', 'approved', 'rejected', 'failed', 'skipped')",
            name="ck_auto_exec_log_status"
        ),
        Index(
            'idx_auto_exec_log_tenant_created',
            'tenant_id', 'created_at'
        ),
        Index(
            'idx_auto_exec_log_ruleset',
            'ruleset_id', 'created_at'
        ),
        Index(
            'idx_auto_exec_log_workflow',
            'workflow_id', 'instance_id'
        ),
        Index(
            'idx_auto_exec_log_status',
            'execution_status', 'created_at'
        ),
        {"schema": "core", "extend_existing": True}
    )

    log_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )

    # 실행 컨텍스트
    workflow_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.workflows.workflow_id", ondelete="SET NULL"),
        nullable=True
    )
    instance_id = Column(PGUUID(as_uuid=True), nullable=True)
    node_id = Column(String(255), nullable=True)
    ruleset_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.rulesets.ruleset_id", ondelete="SET NULL"),
        nullable=True
    )

    # 실행 정보
    action_type = Column(String(100), nullable=False)
    action_params = Column(JSONB, nullable=True)

    # Trust/Risk 평가 결과
    trust_level = Column(Integer, nullable=False)
    trust_score = Column(Numeric(5, 4), nullable=True)
    risk_level = Column(String(20), nullable=False)
    risk_score = Column(Integer, nullable=True)

    # 결정 및 결과
    decision = Column(String(30), nullable=False)
    decision_reason = Column(Text, nullable=True)
    execution_status = Column(String(30), nullable=False)
    execution_result = Column(JSONB, nullable=True)

    # 승인 관련
    approval_id = Column(PGUUID(as_uuid=True), nullable=True)
    approved_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # 에러 정보
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)

    # 메타데이터
    execution_metadata = Column(JSONB, default=dict, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    executed_at = Column(DateTime, nullable=True)

    # Relationships
    ruleset = relationship("Ruleset", backref="auto_execution_logs")
    workflow = relationship("Workflow", backref="auto_execution_logs")

    def __repr__(self):
        return (
            f"<AutoExecutionLog("
            f"action_type={self.action_type}, "
            f"decision={self.decision}, "
            f"status={self.execution_status})>"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "log_id": str(self.log_id),
            "tenant_id": str(self.tenant_id),
            "workflow_id": str(self.workflow_id) if self.workflow_id else None,
            "instance_id": str(self.instance_id) if self.instance_id else None,
            "node_id": self.node_id,
            "ruleset_id": str(self.ruleset_id) if self.ruleset_id else None,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "trust_level": self.trust_level,
            "trust_score": float(self.trust_score) if self.trust_score else None,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "execution_status": self.execution_status,
            "execution_result": self.execution_result,
            "approval_id": str(self.approval_id) if self.approval_id else None,
            "approved_by": str(self.approved_by) if self.approved_by else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }

    def mark_executed(self, result: dict = None, latency_ms: int = None) -> None:
        """실행 완료 마킹"""
        self.execution_status = ExecutionStatus.EXECUTED
        self.executed_at = datetime.utcnow()
        if result:
            self.execution_result = result
        if latency_ms:
            self.latency_ms = latency_ms

    def mark_failed(self, error_message: str, error_details: dict = None) -> None:
        """실행 실패 마킹"""
        self.execution_status = ExecutionStatus.FAILED
        self.error_message = error_message
        if error_details:
            self.error_details = error_details

    def mark_approved(self, user_id: str, approval_id: str = None) -> None:
        """승인 완료 마킹"""
        from uuid import UUID
        self.execution_status = ExecutionStatus.APPROVED
        self.approved_by = UUID(user_id) if isinstance(user_id, str) else user_id
        self.approved_at = datetime.utcnow()
        if approval_id:
            self.approval_id = UUID(approval_id) if isinstance(approval_id, str) else approval_id
