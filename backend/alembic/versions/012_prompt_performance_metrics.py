"""Add performance metrics to prompt_templates

Revision ID: 012_prompt_metrics
Revises: 011_sample_curation
Create Date: 2026-01-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_prompt_metrics'
down_revision = '011_sample_curation'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance metrics columns to prompt_templates table"""

    # Add performance metrics columns
    op.add_column(
        'prompt_templates',
        sa.Column('avg_tokens_per_call', sa.Integer(), nullable=True),
        schema='core'
    )
    op.add_column(
        'prompt_templates',
        sa.Column('avg_latency_ms', sa.Integer(), nullable=True),
        schema='core'
    )
    op.add_column(
        'prompt_templates',
        sa.Column('success_rate', sa.Numeric(5, 4), nullable=True),
        schema='core'
    )
    op.add_column(
        'prompt_templates',
        sa.Column('validation_error_rate', sa.Numeric(5, 4), nullable=True),
        schema='core'
    )
    op.add_column(
        'prompt_templates',
        sa.Column('last_performance_update', sa.DateTime(), nullable=True),
        schema='core'
    )

    # Create index for performance queries
    op.create_index(
        'idx_prompt_templates_performance',
        'prompt_templates',
        ['is_active', 'last_performance_update'],
        unique=False,
        schema='core',
        postgresql_where=sa.text('is_active = true')
    )


def downgrade():
    """Remove performance metrics columns"""

    # Drop index
    op.drop_index(
        'idx_prompt_templates_performance',
        table_name='prompt_templates',
        schema='core'
    )

    # Drop columns
    op.drop_column('prompt_templates', 'last_performance_update', schema='core')
    op.drop_column('prompt_templates', 'validation_error_rate', schema='core')
    op.drop_column('prompt_templates', 'success_rate', schema='core')
    op.drop_column('prompt_templates', 'avg_latency_ms', schema='core')
    op.drop_column('prompt_templates', 'avg_tokens_per_call', schema='core')
