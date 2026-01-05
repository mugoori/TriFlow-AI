"""
Tenant Module Configuration Models
테넌트별 모듈 설정 및 산업 프로필 관리

Multi-Tenant Customization 전략:
- ModuleDefinition: 모듈 마스터 데이터
- TenantModule: 테넌트별 모듈 활성화 설정
- IndustryProfile: 산업별 프로필 템플릿
"""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class IndustryProfile(Base):
    """산업별 프로필 템플릿

    산업별로 기본 활성화할 모듈, KPI, 샘플 룰셋을 정의
    - general: 일반 제조
    - pharma: 제약/화학
    - food: 식품/발효
    - electronics: 전자/반도체
    """

    __tablename__ = "industry_profiles"
    __table_args__ = {"schema": "core", "extend_existing": True}

    industry_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_modules: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    default_kpis: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    sample_rulesets: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tenants = relationship("Tenant", back_populates="industry_profile")

    def __repr__(self):
        return f"<IndustryProfile(code='{self.industry_code}', name='{self.name}')>"


class ModuleDefinition(Base):
    """모듈 정의 마스터 테이블

    시스템에서 제공하는 모든 모듈의 정의
    - core: 핵심 모듈 (dashboard, chat, data, settings) - 비활성화 불가
    - feature: 기능 모듈 (workflows, rulesets, experiments, learning) - 구독 플랜에 따라
    - industry: 산업별 특화 모듈 (quality_pharma, quality_food, quality_elec)
    """

    __tablename__ = "module_definitions"
    __table_args__ = {"schema": "core", "extend_existing": True}

    module_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # core, feature, industry
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    default_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_subscription: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # standard, enterprise
    depends_on: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    config_schema: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # JSON Schema for module config
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tenant_modules = relationship("TenantModule", back_populates="module_definition")

    def __repr__(self):
        return f"<ModuleDefinition(code='{self.module_code}', name='{self.name}', category='{self.category}')>"


class TenantModule(Base):
    """테넌트별 모듈 설정

    각 테넌트가 활성화한 모듈과 해당 모듈의 설정을 관리
    """

    __tablename__ = "tenant_modules"
    __table_args__ = {"schema": "core", "extend_existing": True}

    id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    tenant_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("core.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )
    module_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("core.module_definitions.module_code", ondelete="CASCADE"),
        nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    enabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    enabled_by: Mapped[Optional[PGUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("core.users.user_id", ondelete="SET NULL"),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="modules")
    module_definition = relationship("ModuleDefinition", back_populates="tenant_modules")
    enabled_by_user = relationship("User", foreign_keys=[enabled_by])

    def __repr__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"<TenantModule(tenant_id={self.tenant_id}, module='{self.module_code}', {status})>"
