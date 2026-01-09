# -*- coding: utf-8 -*-
"""Sample Curation 모델

Learning Pipeline을 위한 샘플 큐레이션 모델 정의:
- Sample: 학습 샘플
- GoldenSampleSet: 골든 샘플셋
- GoldenSampleSetMember: N:M 연결

LRN-FR-020 스펙 참조
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


class Sample(Base):
    """학습 샘플

    피드백, 검증, 수동 입력에서 추출된 학습 샘플.
    품질 점수 기반으로 골든 샘플셋에 포함 가능.
    """

    __tablename__ = "samples"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('feedback', 'validation', 'manual')",
            name="ck_samples_source_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'archived')",
            name="ck_samples_status"
        ),
        CheckConstraint(
            "quality_score >= 0.0 AND quality_score <= 1.0",
            name="ck_samples_quality_score"
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_samples_confidence"
        ),
        UniqueConstraint(
            "tenant_id", "content_hash",
            name="uq_samples_unique_content"
        ),
        Index(
            "idx_samples_tenant_category",
            "tenant_id", "category"
        ),
        Index(
            "idx_samples_tenant_status",
            "tenant_id", "status"
        ),
        Index(
            "idx_samples_quality_score",
            "tenant_id", "quality_score"
        ),
        {"schema": "core", "extend_existing": True}
    )

    sample_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )

    # 출처 정보
    feedback_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.feedback_logs.feedback_id", ondelete="SET NULL"),
        nullable=True
    )
    execution_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.judgment_executions.execution_id", ondelete="SET NULL"),
        nullable=True
    )
    source_type = Column(String(20), nullable=False)  # feedback, validation, manual

    # 샘플 데이터
    category = Column(String(50), nullable=False)  # threshold_adjustment, field_correction, validation_failure
    input_data = Column(JSONB, nullable=False)
    expected_output = Column(JSONB, nullable=False)
    context = Column(JSONB, default=dict, nullable=False)

    # 품질 지표
    quality_score = Column(Numeric(5, 4), default=0.0, nullable=False)  # 0.0000 ~ 1.0000
    confidence = Column(Numeric(5, 4), default=0.0, nullable=False)

    # 중복 제거용 해시 (MD5)
    content_hash = Column(String(32), nullable=False, index=True)

    # 상태
    status = Column(String(20), default="pending", nullable=False)  # pending, approved, rejected, archived
    rejection_reason = Column(Text, nullable=True)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.users.user_id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    feedback = relationship("FeedbackLog", backref="samples")
    execution = relationship("JudgmentExecution", backref="samples")
    approver = relationship("User", foreign_keys=[approved_by])
    golden_set_memberships = relationship("GoldenSampleSetMember", back_populates="sample", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Sample("
            f"sample_id={self.sample_id}, "
            f"category={self.category}, "
            f"status={self.status}, "
            f"quality={self.quality_score})>"
        )

    @property
    def is_approved(self) -> bool:
        """승인 여부"""
        return self.status == "approved"

    @property
    def is_pending(self) -> bool:
        """대기 중 여부"""
        return self.status == "pending"

    def approve(self, approver_id) -> None:
        """샘플 승인"""
        self.status = "approved"
        self.approved_at = datetime.utcnow()
        self.approved_by = approver_id

    def reject(self, reason: str) -> None:
        """샘플 거부"""
        self.status = "rejected"
        self.rejection_reason = reason

    def archive(self) -> None:
        """샘플 보관"""
        self.status = "archived"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": str(self.sample_id),
            "tenant_id": str(self.tenant_id),
            "feedback_id": str(self.feedback_id) if self.feedback_id else None,
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "source_type": self.source_type,
            "category": self.category,
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "context": self.context,
            "quality_score": float(self.quality_score) if self.quality_score else 0.0,
            "confidence": float(self.confidence) if self.confidence else 0.0,
            "content_hash": self.content_hash,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": str(self.approved_by) if self.approved_by else None,
        }


class GoldenSampleSet(Base):
    """골든 샘플셋

    검증된 고품질 학습 샘플의 그룹.
    자동 업데이트 기능으로 품질 기준 충족 샘플 자동 추가 가능.
    """

    __tablename__ = "golden_sample_sets"
    __table_args__ = (
        CheckConstraint(
            "min_quality_score >= 0.0 AND min_quality_score <= 1.0",
            name="ck_golden_sample_sets_min_quality"
        ),
        CheckConstraint(
            "max_samples > 0 AND max_samples <= 100000",
            name="ck_golden_sample_sets_max_samples"
        ),
        Index(
            "idx_golden_sample_sets_tenant",
            "tenant_id", "is_active"
        ),
        {"schema": "core", "extend_existing": True}
    )

    set_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # 특정 카테고리로 제한 (NULL이면 전체)

    # 설정
    min_quality_score = Column(Numeric(5, 4), default=0.7, nullable=False)
    max_samples = Column(Integer, default=1000, nullable=False)
    auto_update = Column(Boolean, default=True, nullable=False)

    # 메타데이터
    config = Column(JSONB, default=dict, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.users.user_id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    members = relationship("GoldenSampleSetMember", back_populates="sample_set", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<GoldenSampleSet("
            f"set_id={self.set_id}, "
            f"name={self.name}, "
            f"category={self.category})>"
        )

    @property
    def sample_count(self) -> int:
        """현재 샘플 수"""
        return len(self.members) if self.members else 0

    @property
    def is_full(self) -> bool:
        """최대 샘플 수 도달 여부"""
        return self.sample_count >= self.max_samples

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_id": str(self.set_id),
            "tenant_id": str(self.tenant_id),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "min_quality_score": float(self.min_quality_score) if self.min_quality_score else 0.7,
            "max_samples": self.max_samples,
            "auto_update": self.auto_update,
            "config": self.config,
            "is_active": self.is_active,
            "sample_count": self.sample_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": str(self.created_by) if self.created_by else None,
        }


class GoldenSampleSetMember(Base):
    """골든 샘플셋 멤버

    GoldenSampleSet과 Sample 간의 N:M 관계.
    """

    __tablename__ = "golden_sample_set_members"
    __table_args__ = (
        Index(
            "idx_golden_sample_set_members_sample",
            "sample_id"
        ),
        {"schema": "core", "extend_existing": True}
    )

    set_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.golden_sample_sets.set_id", ondelete="CASCADE"),
        primary_key=True
    )
    sample_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.samples.sample_id", ondelete="CASCADE"),
        primary_key=True
    )
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    added_by = Column(
        PGUUID(as_uuid=True),
        ForeignKey("core.users.user_id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    sample_set = relationship("GoldenSampleSet", back_populates="members")
    sample = relationship("Sample", back_populates="golden_set_memberships")

    def __repr__(self):
        return (
            f"<GoldenSampleSetMember("
            f"set_id={self.set_id}, "
            f"sample_id={self.sample_id})>"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_id": str(self.set_id),
            "sample_id": str(self.sample_id),
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "added_by": str(self.added_by) if self.added_by else None,
        }
