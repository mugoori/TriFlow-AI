"""
Base Pydantic schemas
"""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class TimestampMixin(BaseModel):
    """Mixin for models with timestamps"""
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantScopedMixin(BaseModel):
    """Mixin for tenant-scoped models"""
    tenant_id: UUID

    model_config = ConfigDict(from_attributes=True)


class BaseSchema(BaseModel):
    """Base schema with common configuration"""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
