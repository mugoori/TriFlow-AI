# -*- coding: utf-8 -*-
"""Canary Deployment 모델

Canary 배포를 위한 SQLAlchemy 모델 정의:
- CanaryAssignment: Sticky Session 할당
- DeploymentMetrics: v1/v2 메트릭 비교
- CanaryExecutionLog: Canary 기간 실행 로그 격리

LRN-FR-050 스펙 참조
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


class CanaryAssignment(Base):
    """Canary 세션 할당

    Sticky Session을 위한 사용자/세션/워크플로우 인스턴스별 버전 할당.
    3계층 우선순위: workflow_instance > session > user
    """

    __tablename__ = "canary_assignments"
    __table_args__ = (
        CheckConstraint(
            "identifier_type IN ('user', 'session', 'workflow_instance')",
            name="ck_canary_assignments_identifier_type"
        ),
        CheckConstraint(
            "assigned_version IN ('v1', 'v2')",
            name="ck_canary_assignments_version"
        ),
        UniqueConstraint(
            "deployment_id", "identifier",
            name="uq_canary_assignments_deployment_identifier"
        ),
        Index(
            "idx_canary_assignments_tenant_deployment",
            "tenant_id", "deployment_id"
        ),
        {"schema": "core", "extend_existing": True}
    )

    assignment_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )
    deployment_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.rule_deployments.deployment_id", ondelete="CASCADE"),
        nullable=False
    )

    # 식별자
    identifier = Column(String(255), nullable=False)
    identifier_type = Column(String(30), nullable=False)  # user, session, workflow_instance

    # 할당된 버전
    assigned_version = Column(String(10), nullable=False)  # v1 (stable), v2 (canary)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # NULL = 만료 없음

    # Relationships
    deployment = relationship("RuleDeployment", backref="canary_assignments")

    def __repr__(self):
        return (
            f"<CanaryAssignment("
            f"deployment_id={self.deployment_id}, "
            f"identifier={self.identifier}, "
            f"version={self.assigned_version})>"
        )

    @property
    def is_expired(self) -> bool:
        """할당 만료 여부"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": str(self.assignment_id),
            "deployment_id": str(self.deployment_id),
            "identifier": self.identifier,
            "identifier_type": self.identifier_type,
            "assigned_version": self.assigned_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired,
        }


class DeploymentMetrics(Base):
    """배포 메트릭

    시간 윈도우별 v1/v2 성능 비교 메트릭.
    Circuit Breaker 판단에 사용.
    """

    __tablename__ = "deployment_metrics"
    __table_args__ = (
        CheckConstraint(
            "version_type IN ('canary', 'stable')",
            name="ck_deployment_metrics_version_type"
        ),
        Index(
            "idx_deployment_metrics_deployment_version",
            "deployment_id", "version_type", "window_end"
        ),
        {"schema": "core", "extend_existing": True}
    )

    metric_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )
    deployment_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.rule_deployments.deployment_id", ondelete="CASCADE"),
        nullable=False
    )

    # 버전 타입
    version_type = Column(String(10), nullable=False)  # canary, stable

    # 집계 통계
    sample_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)
    error_rate = Column(Numeric(5, 4), default=0, nullable=False)  # 0.0000 ~ 1.0000

    # 레이턴시 (밀리초)
    latency_p50_ms = Column(Integer, nullable=True)
    latency_p95_ms = Column(Integer, nullable=True)
    latency_p99_ms = Column(Integer, nullable=True)
    latency_avg_ms = Column(Integer, nullable=True)

    # 연속 실패 카운터
    consecutive_failures = Column(Integer, default=0, nullable=False)

    # 시간 윈도우
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    deployment = relationship("RuleDeployment", backref="metrics")

    def __repr__(self):
        return (
            f"<DeploymentMetrics("
            f"deployment_id={self.deployment_id}, "
            f"version={self.version_type}, "
            f"error_rate={self.error_rate})>"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": str(self.metric_id),
            "deployment_id": str(self.deployment_id),
            "version_type": self.version_type,
            "sample_count": self.sample_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "error_rate": float(self.error_rate) if self.error_rate else 0.0,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "latency_avg_ms": self.latency_avg_ms,
            "consecutive_failures": self.consecutive_failures,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
        }


class CanaryExecutionLog(Base):
    """Canary 실행 로그

    Canary 배포 기간 동안의 실행 로그를 격리 저장.
    롤백 시 Compensation 처리에 사용.
    """

    __tablename__ = "canary_execution_logs"
    __table_args__ = (
        CheckConstraint(
            "canary_version IN ('v1', 'v2')",
            name="ck_canary_execution_logs_version"
        ),
        Index(
            "idx_canary_execution_logs_deployment_version",
            "deployment_id", "canary_version", "created_at"
        ),
        {"schema": "core", "extend_existing": True}
    )

    log_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )
    deployment_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.rule_deployments.deployment_id", ondelete="CASCADE"),
        nullable=False
    )

    # 원본 실행 참조
    execution_id = Column(PGUUID(as_uuid=True), nullable=True)

    # 버전 정보
    canary_version = Column(String(10), nullable=False)  # v1, v2

    # 실행 결과
    success = Column(Boolean, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # 롤백 관련
    rollback_safe = Column(Boolean, default=True)
    needs_reprocess = Column(Boolean, default=False)
    reprocessed_at = Column(DateTime, nullable=True)

    # 메타데이터
    execution_metadata = Column(JSONB, default=dict, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    deployment = relationship("RuleDeployment", backref="canary_logs")

    def __repr__(self):
        return (
            f"<CanaryExecutionLog("
            f"deployment_id={self.deployment_id}, "
            f"version={self.canary_version}, "
            f"success={self.success})>"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "log_id": str(self.log_id),
            "deployment_id": str(self.deployment_id),
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "canary_version": self.canary_version,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "rollback_safe": self.rollback_safe,
            "needs_reprocess": self.needs_reprocess,
            "execution_metadata": self.execution_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def mark_for_reprocess(self) -> None:
        """재처리 필요 마킹"""
        self.needs_reprocess = True

    def mark_reprocessed(self) -> None:
        """재처리 완료 마킹"""
        self.needs_reprocess = False
        self.reprocessed_at = datetime.utcnow()
