# -*- coding: utf-8 -*-
"""008 Materialized Views for Dashboard Performance

Revision ID: 008_materialized_views
Revises: 007_bi_schema_fixes
Create Date: 2026-01-09

- Create 4 Materialized Views in bi schema for dashboard performance
- mv_defect_trend: Daily defect trends
- mv_oee_daily: Daily OEE aggregation
- mv_line_performance: Line performance summary
- mv_quality_summary: Quality summary by date
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '008_materialized_views'
down_revision: Union[str, None] = '007_bi_schema_fixes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # 1. mv_defect_trend - 일일 결함 추이
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_defect_trend AS
        SELECT
            tenant_id,
            date,
            line_code,
            COUNT(*) as defect_count,
            SUM(quantity) as defect_quantity,
            array_agg(DISTINCT defect_code) as defect_codes
        FROM analytics.fact_daily_defect
        WHERE date >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY tenant_id, date, line_code
        WITH DATA
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_defect_trend_pk
        ON bi.mv_defect_trend(tenant_id, date, line_code)
    """)
    op.execute("COMMENT ON MATERIALIZED VIEW bi.mv_defect_trend IS 'Daily defect trends - refreshed every 30 min'")

    # ============================================
    # 2. mv_oee_daily - OEE 일일 집계
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_oee_daily AS
        SELECT
            tenant_id,
            date,
            line_code,
            AVG(availability) as avg_availability,
            AVG(performance) as avg_performance,
            AVG(quality) as avg_quality,
            AVG(oee) as avg_oee,
            SUM(production_quantity) as total_production,
            SUM(good_quantity) as total_good,
            COUNT(*) as record_count
        FROM analytics.fact_daily_production
        WHERE date >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY tenant_id, date, line_code
        WITH DATA
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_oee_daily_pk
        ON bi.mv_oee_daily(tenant_id, date, line_code)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_oee_daily_date
        ON bi.mv_oee_daily(tenant_id, date DESC)
    """)
    op.execute("COMMENT ON MATERIALIZED VIEW bi.mv_oee_daily IS 'Daily OEE aggregation - refreshed every 30 min'")

    # ============================================
    # 3. mv_line_performance - 라인별 성과 (30일)
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_line_performance AS
        SELECT
            f.tenant_id,
            f.line_code,
            l.name as line_name,
            SUM(f.production_quantity) as total_production,
            SUM(f.good_quantity) as total_good,
            SUM(f.production_quantity - f.good_quantity) as total_defect,
            AVG(f.oee) as avg_oee,
            AVG(f.availability) as avg_availability,
            AVG(f.performance) as avg_performance,
            AVG(f.quality) as avg_quality,
            COUNT(DISTINCT f.date) as working_days,
            MIN(f.date) as period_start,
            MAX(f.date) as period_end
        FROM analytics.fact_daily_production f
        LEFT JOIN analytics.dim_line l
            ON f.tenant_id = l.tenant_id AND f.line_code = l.line_code
        WHERE f.date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY f.tenant_id, f.line_code, l.name
        WITH DATA
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_line_performance_pk
        ON bi.mv_line_performance(tenant_id, line_code)
    """)
    op.execute("COMMENT ON MATERIALIZED VIEW bi.mv_line_performance IS 'Line performance summary (30 days) - refreshed every 30 min'")

    # ============================================
    # 4. mv_quality_summary - 품질 요약 (일별)
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_quality_summary AS
        SELECT
            tenant_id,
            date,
            SUM(good_quantity) as total_good,
            SUM(production_quantity - good_quantity) as total_defect,
            SUM(production_quantity) as total_production,
            CASE
                WHEN SUM(production_quantity) > 0
                THEN ROUND((SUM(good_quantity)::NUMERIC / SUM(production_quantity) * 100), 2)
                ELSE 0
            END as quality_rate
        FROM analytics.fact_daily_production
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY tenant_id, date
        WITH DATA
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_quality_summary_pk
        ON bi.mv_quality_summary(tenant_id, date)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_quality_summary_date
        ON bi.mv_quality_summary(tenant_id, date DESC)
    """)
    op.execute("COMMENT ON MATERIALIZED VIEW bi.mv_quality_summary IS 'Quality summary by date - refreshed every 30 min'")

    # ============================================
    # MV 리프레시를 위한 헬퍼 함수
    # ============================================
    op.execute("""
        CREATE OR REPLACE FUNCTION bi.refresh_all_mvs()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_defect_trend;
            REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_oee_daily;
            REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_line_performance;
            REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_quality_summary;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("COMMENT ON FUNCTION bi.refresh_all_mvs() IS 'Refresh all dashboard materialized views concurrently'")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS bi.refresh_all_mvs() CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_quality_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_line_performance CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_oee_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_defect_trend CASCADE")
