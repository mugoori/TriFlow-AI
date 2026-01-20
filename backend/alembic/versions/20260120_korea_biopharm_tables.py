"""Add korea_biopharm schema and tables

Revision ID: 20260120_korea_biopharm
Revises: (latest revision)
Create Date: 2026-01-20 13:35:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260120_korea_biopharm'
down_revision = '012_prompt_metrics'
branch_labels = None
depends_on = None


def upgrade():
    # 스키마 생성
    op.execute("CREATE SCHEMA IF NOT EXISTS korea_biopharm")

    # recipe_metadata 테이블
    op.create_table(
        'recipe_metadata',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('product_name', sa.String(500), nullable=True),
        sa.Column('company_name', sa.String(500), nullable=True),
        sa.Column('formulation_type', sa.String(100), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.Column('ingredient_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        schema='korea_biopharm'
    )

    # 인덱스
    op.create_index(
        'idx_recipe_metadata_tenant',
        'recipe_metadata',
        ['tenant_id'],
        schema='korea_biopharm'
    )
    op.create_index(
        'idx_recipe_metadata_formulation',
        'recipe_metadata',
        ['formulation_type'],
        schema='korea_biopharm'
    )
    op.create_index(
        'idx_recipe_metadata_product_name',
        'recipe_metadata',
        ['product_name'],
        schema='korea_biopharm'
    )

    # historical_recipes 테이블
    op.create_table(
        'historical_recipes',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('ingredient', sa.String(500), nullable=True),
        sa.Column('ratio', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        schema='korea_biopharm'
    )

    # 인덱스
    op.create_index(
        'idx_historical_recipes_tenant',
        'historical_recipes',
        ['tenant_id'],
        schema='korea_biopharm'
    )
    op.create_index(
        'idx_historical_recipes_filename',
        'historical_recipes',
        ['filename'],
        schema='korea_biopharm'
    )
    op.create_index(
        'idx_historical_recipes_ingredient',
        'historical_recipes',
        ['ingredient'],
        schema='korea_biopharm'
    )

    # Foreign key
    op.create_foreign_key(
        'fk_recipe_metadata_tenant',
        'recipe_metadata',
        'tenants',
        ['tenant_id'],
        ['tenant_id'],
        source_schema='korea_biopharm',
        referent_schema='core'
    )
    op.create_foreign_key(
        'fk_historical_recipes_tenant',
        'historical_recipes',
        'tenants',
        ['tenant_id'],
        ['tenant_id'],
        source_schema='korea_biopharm',
        referent_schema='core'
    )


def downgrade():
    # 테이블 삭제
    op.drop_table('historical_recipes', schema='korea_biopharm')
    op.drop_table('recipe_metadata', schema='korea_biopharm')

    # 스키마 삭제
    op.execute("DROP SCHEMA IF EXISTS korea_biopharm CASCADE")
