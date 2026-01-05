# -*- coding: utf-8 -*-
"""004 V2 Trust Fields

Revision ID: 004_v2_trust
Revises: 003_rag_aas
Create Date: 2026-01-05

V2.0 Phase 1: Progressive Trust Model
Based on specs A-2-5 (V2 Algorithm) and D-5 (Migration Plan)

Changes:
1. Add trust_level, trust_score fields to rulesets table
2. Add execution metrics fields to rulesets table
3. Add trust-related fields to judgment_executions table
4. Create trust_level_history table for tracking level changes
5. Add indexes for trust-related queries
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_v2_trust'
down_revision: Union[str, None] = '003_rag_aas'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # 1. Extend rulesets table with Trust fields
    # ============================================

    # Trust Level (0-3): Proposed(0) → Alert Only(1) → Low Risk Auto(2) → Full Auto(3)
    op.add_column(
        'rulesets',
        sa.Column('trust_level', sa.Integer(), nullable=False, server_default='0'),
        schema='core'
    )

    # Trust Score (0.0000 - 1.0000)
    op.add_column(
        'rulesets',
        sa.Column('trust_score', sa.Numeric(5, 4), nullable=False, server_default='0.0000'),
        schema='core'
    )

    # Trust Score components stored as JSONB for simplicity
    # Contains: accuracy, consistency, frequency, feedback, age components
    op.add_column(
        'rulesets',
        sa.Column('trust_score_components', postgresql.JSONB(), nullable=True),
        schema='core'
    )

    # Execution metrics for Trust Score calculation
    op.add_column(
        'rulesets',
        sa.Column('execution_count', sa.Integer(), nullable=False, server_default='0'),
        schema='core'
    )
    op.add_column(
        'rulesets',
        sa.Column('positive_feedback_count', sa.Integer(), nullable=False, server_default='0'),
        schema='core'
    )
    op.add_column(
        'rulesets',
        sa.Column('negative_feedback_count', sa.Integer(), nullable=False, server_default='0'),
        schema='core'
    )
    op.add_column(
        'rulesets',
        sa.Column('accuracy_rate', sa.Numeric(5, 4), nullable=True),
        schema='core'
    )

    # Timestamps for Trust management
    op.add_column(
        'rulesets',
        sa.Column('last_execution_at', sa.DateTime(), nullable=True),
        schema='core'
    )
    op.add_column(
        'rulesets',
        sa.Column('last_promoted_at', sa.DateTime(), nullable=True),
        schema='core'
    )
    op.add_column(
        'rulesets',
        sa.Column('last_demoted_at', sa.DateTime(), nullable=True),
        schema='core'
    )

    # ============================================
    # 2. Extend judgment_executions with Trust fields
    # ============================================

    # Trust level at time of execution
    op.add_column(
        'judgment_executions',
        sa.Column('trust_level', sa.Integer(), nullable=True),
        schema='core'
    )

    # Risk level for this execution (none, low, medium, high)
    op.add_column(
        'judgment_executions',
        sa.Column('risk_level', sa.String(20), nullable=True),
        schema='core'
    )

    # Risk score (0.0 - 1.0)
    op.add_column(
        'judgment_executions',
        sa.Column('risk_score', sa.Numeric(5, 4), nullable=True),
        schema='core'
    )

    # Whether this was auto-executed (V2 Auto Execution)
    op.add_column(
        'judgment_executions',
        sa.Column('auto_executed', sa.Boolean(), nullable=False, server_default='false'),
        schema='core'
    )

    # Ruleset ID reference for trust tracking
    op.add_column(
        'judgment_executions',
        sa.Column('ruleset_id', postgresql.UUID(as_uuid=True), nullable=True),
        schema='core'
    )

    # Add foreign key for ruleset_id
    op.create_foreign_key(
        'fk_judgment_executions_ruleset',
        'judgment_executions', 'rulesets',
        ['ruleset_id'], ['ruleset_id'],
        source_schema='core', referent_schema='core',
        ondelete='SET NULL'
    )

    # ============================================
    # 3. Create trust_level_history table
    # ============================================
    op.create_table(
        'trust_level_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('ruleset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('previous_level', sa.Integer(), nullable=False),
        sa.Column('new_level', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('triggered_by', sa.String(50), nullable=True),  # auto, manual, feedback, etc.
        # JSONB for metrics snapshot at time of change
        # Contains: trust_score, accuracy_rate, execution_count, etc.
        sa.Column('metrics_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['ruleset_id'], ['core.rulesets.ruleset_id'],
            name='fk_trust_history_ruleset',
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['created_by'], ['core.users.user_id'],
            name='fk_trust_history_user',
            ondelete='SET NULL'
        ),
        schema='core'
    )

    # ============================================
    # 4. Create Indexes
    # ============================================

    # Index for querying rulesets by trust level
    op.create_index(
        'idx_rulesets_trust_level',
        'rulesets',
        ['trust_level'],
        schema='core'
    )

    # Index for querying rulesets by trust score (descending for top performers)
    op.create_index(
        'idx_rulesets_trust_score',
        'rulesets',
        [sa.text('trust_score DESC')],
        schema='core'
    )

    # Index for finding auto-executed judgments
    op.create_index(
        'idx_judgment_executions_auto',
        'judgment_executions',
        ['auto_executed'],
        schema='core',
        postgresql_where=sa.text('auto_executed = true')
    )

    # Index for trust level history by ruleset
    op.create_index(
        'idx_trust_history_ruleset',
        'trust_level_history',
        ['ruleset_id', sa.text('created_at DESC')],
        schema='core'
    )

    # Index for judgment executions by ruleset_id for trust metrics
    op.create_index(
        'idx_judgment_executions_ruleset',
        'judgment_executions',
        ['ruleset_id'],
        schema='core',
        postgresql_where=sa.text('ruleset_id IS NOT NULL')
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_judgment_executions_ruleset', table_name='judgment_executions', schema='core')
    op.drop_index('idx_trust_history_ruleset', table_name='trust_level_history', schema='core')
    op.drop_index('idx_judgment_executions_auto', table_name='judgment_executions', schema='core')
    op.drop_index('idx_rulesets_trust_score', table_name='rulesets', schema='core')
    op.drop_index('idx_rulesets_trust_level', table_name='rulesets', schema='core')

    # Drop trust_level_history table
    op.drop_table('trust_level_history', schema='core')

    # Drop foreign key from judgment_executions
    op.drop_constraint('fk_judgment_executions_ruleset', 'judgment_executions', schema='core', type_='foreignkey')

    # Remove columns from judgment_executions
    op.drop_column('judgment_executions', 'ruleset_id', schema='core')
    op.drop_column('judgment_executions', 'auto_executed', schema='core')
    op.drop_column('judgment_executions', 'risk_score', schema='core')
    op.drop_column('judgment_executions', 'risk_level', schema='core')
    op.drop_column('judgment_executions', 'trust_level', schema='core')

    # Remove columns from rulesets
    op.drop_column('rulesets', 'last_demoted_at', schema='core')
    op.drop_column('rulesets', 'last_promoted_at', schema='core')
    op.drop_column('rulesets', 'last_execution_at', schema='core')
    op.drop_column('rulesets', 'accuracy_rate', schema='core')
    op.drop_column('rulesets', 'negative_feedback_count', schema='core')
    op.drop_column('rulesets', 'positive_feedback_count', schema='core')
    op.drop_column('rulesets', 'execution_count', schema='core')
    op.drop_column('rulesets', 'trust_score_components', schema='core')
    op.drop_column('rulesets', 'trust_score', schema='core')
    op.drop_column('rulesets', 'trust_level', schema='core')
