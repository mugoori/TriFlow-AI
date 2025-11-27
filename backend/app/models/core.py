"""
Core Schema ORM Models
테넌트, 사용자, 룰셋, 워크플로, 센서 데이터 등
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Tenant(Base):
    """테넌트 (멀티테넌트 지원)"""

    __tablename__ = "tenants"
    __table_args__ = {"schema": "core"}

    tenant_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    settings = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    rulesets = relationship("Ruleset", back_populates="tenant", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.tenant_id}, name='{self.name}')>"


class User(Base):
    """사용자"""

    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    username = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="user")  # admin, user, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")

    def __repr__(self):
        return f"<User(id={self.user_id}, username='{self.username}')>"


class Ruleset(Base):
    """룰셋 (Rhai 스크립트 기반 규칙)"""

    __tablename__ = "rulesets"
    __table_args__ = {"schema": "core"}

    ruleset_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    rhai_script = Column(Text, nullable=False)
    version = Column(String(50), default="1.0.0")
    is_active = Column(Boolean, default=True)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="rulesets")
    executions = relationship("JudgmentExecution", back_populates="ruleset")

    def __repr__(self):
        return f"<Ruleset(id={self.ruleset_id}, name='{self.name}')>"


class Workflow(Base):
    """워크플로 (JSON DSL 기반)"""

    __tablename__ = "workflows"
    __table_args__ = {"schema": "core"}

    workflow_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    dsl_definition = Column(JSONB, nullable=False)  # JSON DSL
    version = Column(String(50), default="1.0.0")
    is_active = Column(Boolean, default=True)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("core.users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="workflows")
    instances = relationship("WorkflowInstance", back_populates="workflow")

    def __repr__(self):
        return f"<Workflow(id={self.workflow_id}, name='{self.name}')>"


class WorkflowInstance(Base):
    """워크플로 실행 인스턴스"""

    __tablename__ = "workflow_instances"
    __table_args__ = {"schema": "core"}

    instance_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(PGUUID(as_uuid=True), ForeignKey("core.workflows.workflow_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    input_data = Column(JSONB, default={})
    output_data = Column(JSONB, default={})
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    workflow = relationship("Workflow", back_populates="instances")

    def __repr__(self):
        return f"<WorkflowInstance(id={self.instance_id}, status='{self.status}')>"


class JudgmentExecution(Base):
    """판단 실행 로그 (Ruleset 실행 결과)"""

    __tablename__ = "judgment_executions"
    __table_args__ = {"schema": "core"}

    execution_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ruleset_id = Column(PGUUID(as_uuid=True), ForeignKey("core.rulesets.ruleset_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    input_data = Column(JSONB, nullable=False)
    output_data = Column(JSONB, nullable=False)
    confidence_score = Column(Float, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    ruleset = relationship("Ruleset", back_populates="executions")

    def __repr__(self):
        return f"<JudgmentExecution(id={self.execution_id}, confidence={self.confidence_score})>"


class SensorData(Base):
    """센서 데이터 (파티션 테이블)"""

    __tablename__ = "sensor_data"
    __table_args__ = {"schema": "core"}

    # 복합 PRIMARY KEY (sensor_id, recorded_at)
    sensor_id = Column(PGUUID(as_uuid=True), default=uuid4, primary_key=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow, primary_key=True)

    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    line_code = Column(String(100), nullable=False)
    sensor_type = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    sensor_metadata = Column("metadata", JSONB, default={})  # 컬럼명 'metadata'이지만 속성명은 sensor_metadata

    def __repr__(self):
        return f"<SensorData(type='{self.sensor_type}', value={self.value}, recorded_at={self.recorded_at})>"
