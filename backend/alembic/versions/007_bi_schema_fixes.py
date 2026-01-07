# -*- coding: utf-8 -*-
"""007 BI Schema Fixes

Revision ID: 007_bi_schema_fixes
Revises: 006_add_deleted_at
Create Date: 2026-01-06

- Create bi schema (models use 'bi' but migrations created 'analytics')
- Create ai_insights table
- Create pinned_insights table
- Create bi_dashboards table in bi schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007_bi_schema_fixes'
down_revision: Union[str, None] = '006_add_deleted_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create bi schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS bi")

    # ============================================
    # bi.ai_insights - AI 생성 인사이트
    # ============================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS bi.ai_insights (
            insight_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

            -- 인사이트 내용
            title text NOT NULL,
            summary text,
            facts jsonb DEFAULT '[]'::jsonb,
            reasoning jsonb DEFAULT '{}'::jsonb,
            actions jsonb DEFAULT '[]'::jsonb,

            -- 메타데이터
            source_type text NOT NULL DEFAULT 'chat',  -- chat, scheduled, alert
            source_id text,  -- conversation_id or schedule_id

            -- 피드백
            feedback_score int CHECK (feedback_score BETWEEN 1 AND 5),
            feedback_comment text,

            -- 타임스탬프
            generated_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_insights_tenant ON bi.ai_insights (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_insights_generated ON bi.ai_insights (tenant_id, generated_at DESC)")

    # ============================================
    # bi.pinned_insights - 대시보드 고정 인사이트
    # ============================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS bi.pinned_insights (
            pin_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
            insight_id uuid NOT NULL REFERENCES bi.ai_insights(insight_id) ON DELETE CASCADE,

            -- 대시보드 위치
            dashboard_order int NOT NULL DEFAULT 0,
            grid_position jsonb,  -- {x, y, w, h}

            -- 표시 옵션
            display_mode text NOT NULL DEFAULT 'card',  -- card, expanded, minimized
            show_facts boolean NOT NULL DEFAULT true,
            show_reasoning boolean NOT NULL DEFAULT false,
            show_actions boolean NOT NULL DEFAULT true,

            -- 메타데이터
            pinned_at timestamptz NOT NULL DEFAULT now(),
            pinned_by uuid REFERENCES core.users(user_id),

            UNIQUE (tenant_id, insight_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pinned_insights_tenant ON bi.pinned_insights (tenant_id, dashboard_order)")

    # ============================================
    # bi.bi_dashboards - 대시보드 정의 (bi 스키마)
    # ============================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS bi.bi_dashboards (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

            name text NOT NULL,
            description text,

            layout jsonb NOT NULL DEFAULT '{}'::jsonb,

            is_public boolean NOT NULL DEFAULT false,
            owner_id uuid NOT NULL REFERENCES core.users(user_id),

            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),

            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_bi_dashboards_tenant ON bi.bi_dashboards (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bi_dashboards_owner ON bi.bi_dashboards (owner_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bi.pinned_insights CASCADE")
    op.execute("DROP TABLE IF EXISTS bi.ai_insights CASCADE")
    op.execute("DROP TABLE IF EXISTS bi.bi_dashboards CASCADE")
