"""
Tenant Pydantic Schemas
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TenantBase(BaseModel):
    """Tenant 기본 스키마"""

    name: str = Field(..., min_length=1, max_length=255, description="테넌트 이름")
    slug: str = Field(..., min_length=1, max_length=100, description="테넌트 슬러그 (URL용)")
    settings: Optional[dict] = Field(default_factory=dict, description="설정 (JSONB)")


class TenantCreate(TenantBase):
    """Tenant 생성 요청"""

    pass


class TenantUpdate(BaseModel):
    """Tenant 업데이트 요청"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    settings: Optional[dict] = None


class TenantResponse(TenantBase):
    """Tenant 응답"""

    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
