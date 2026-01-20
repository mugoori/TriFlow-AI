"""
Korea Biopharm PostgreSQL Models
"""
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class RecipeMetadata(Base):
    """배합비 메타데이터"""
    __tablename__ = 'recipe_metadata'
    __table_args__ = (
        Index('idx_recipe_metadata_tenant', 'tenant_id'),
        Index('idx_recipe_metadata_formulation', 'formulation_type'),
        Index('idx_recipe_metadata_product_name', 'product_name'),
        {'schema': 'korea_biopharm'}
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('core.tenants.tenant_id'), nullable=False)
    filename = Column(String(255), nullable=False)
    product_name = Column(String(500))
    company_name = Column(String(500))
    formulation_type = Column(String(100))
    created_date = Column(DateTime)
    ingredient_count = Column(Integer)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class HistoricalRecipe(Base):
    """배합비 상세"""
    __tablename__ = 'historical_recipes'
    __table_args__ = (
        Index('idx_historical_recipes_tenant', 'tenant_id'),
        Index('idx_historical_recipes_filename', 'filename'),
        Index('idx_historical_recipes_ingredient', 'ingredient'),
        {'schema': 'korea_biopharm'}
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('core.tenants.tenant_id'), nullable=False)
    filename = Column(String(255), nullable=False)
    ingredient = Column(String(500))
    ratio = Column(Numeric(10, 2))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
