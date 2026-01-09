# -*- coding: utf-8 -*-
"""009 Fix Materialized Views and Seed KPI Data

Revision ID: 009_fix_materialized_views
Revises: 008_materialized_views
Create Date: 2026-01-09

- 기존 MV 삭제 후 올바른 컬럼명으로 재생성
- dim_kpi 시드 데이터 추가 (KPI 드롭다운용)
- OEE 계산식을 직접 포함 (fact 테이블 컬럼 기반)
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '009_fix_materialized_views'
down_revision: Union[str, None] = '008_materialized_views'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # 1. 기존 MV 삭제
    # ============================================
    op.execute("DROP FUNCTION IF EXISTS bi.refresh_all_mvs() CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_quality_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_line_performance CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_oee_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_defect_trend CASCADE")

    # ============================================
    # 2. mv_defect_trend - 일일 결함 추이 (수정)
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_defect_trend AS
        SELECT
            tenant_id,
            date,
            line_code,
            COUNT(*) as defect_count,
            SUM(defect_qty) as defect_quantity,
            array_agg(DISTINCT defect_type) as defect_types
        FROM bi.fact_daily_defect
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
    # 3. mv_oee_daily - OEE 일일 집계 (수정)
    #    fact 테이블의 실제 컬럼 기반으로 OEE 계산
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_oee_daily AS
        SELECT
            tenant_id,
            date,
            line_code,
            -- 가동률: runtime / (runtime + downtime)
            CASE WHEN COALESCE(SUM(runtime_minutes), 0) + COALESCE(SUM(downtime_minutes), 0) > 0
                 THEN ROUND((SUM(runtime_minutes)::NUMERIC / (SUM(runtime_minutes) + SUM(downtime_minutes)) * 100), 2)
                 ELSE 0 END as avg_availability,
            -- 성능률: 현재 데이터에서 계산 불가, 기본 100%
            100.0 as avg_performance,
            -- 품질률: good_qty / total_qty
            CASE WHEN COALESCE(SUM(total_qty), 0) > 0
                 THEN ROUND((SUM(good_qty)::NUMERIC / SUM(total_qty) * 100), 2)
                 ELSE 0 END as avg_quality,
            -- OEE: 가동률 * 품질률 / 100 (성능률 100% 가정)
            CASE WHEN COALESCE(SUM(runtime_minutes), 0) + COALESCE(SUM(downtime_minutes), 0) > 0
                      AND COALESCE(SUM(total_qty), 0) > 0
                 THEN ROUND(
                     (SUM(runtime_minutes)::NUMERIC / (SUM(runtime_minutes) + SUM(downtime_minutes))) *
                     (SUM(good_qty)::NUMERIC / SUM(total_qty)) * 100, 2)
                 ELSE 0 END as avg_oee,
            SUM(total_qty) as total_production,
            SUM(good_qty) as total_good,
            COUNT(*) as record_count
        FROM bi.fact_daily_production
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
    # 4. mv_line_performance - 라인별 성과 (수정)
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_line_performance AS
        SELECT
            f.tenant_id,
            f.line_code,
            l.name as line_name,
            SUM(f.total_qty) as total_production,
            SUM(f.good_qty) as total_good,
            SUM(f.total_qty - f.good_qty) as total_defect,
            -- OEE 계산
            CASE WHEN COALESCE(SUM(f.runtime_minutes), 0) + COALESCE(SUM(f.downtime_minutes), 0) > 0
                      AND COALESCE(SUM(f.total_qty), 0) > 0
                 THEN ROUND(
                     (SUM(f.runtime_minutes)::NUMERIC / (SUM(f.runtime_minutes) + SUM(f.downtime_minutes))) *
                     (SUM(f.good_qty)::NUMERIC / SUM(f.total_qty)) * 100, 2)
                 ELSE 0 END as avg_oee,
            -- 가동률
            CASE WHEN COALESCE(SUM(f.runtime_minutes), 0) + COALESCE(SUM(f.downtime_minutes), 0) > 0
                 THEN ROUND((SUM(f.runtime_minutes)::NUMERIC / (SUM(f.runtime_minutes) + SUM(f.downtime_minutes)) * 100), 2)
                 ELSE 0 END as avg_availability,
            100.0 as avg_performance,
            -- 품질률
            CASE WHEN COALESCE(SUM(f.total_qty), 0) > 0
                 THEN ROUND((SUM(f.good_qty)::NUMERIC / SUM(f.total_qty) * 100), 2)
                 ELSE 0 END as avg_quality,
            COUNT(DISTINCT f.date) as working_days,
            MIN(f.date) as period_start,
            MAX(f.date) as period_end
        FROM bi.fact_daily_production f
        LEFT JOIN bi.dim_line l
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
    # 5. mv_quality_summary - 품질 요약 (수정)
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_quality_summary AS
        SELECT
            tenant_id,
            date,
            SUM(good_qty) as total_good,
            SUM(total_qty - good_qty) as total_defect,
            SUM(total_qty) as total_production,
            CASE
                WHEN SUM(total_qty) > 0
                THEN ROUND((SUM(good_qty)::NUMERIC / SUM(total_qty) * 100), 2)
                ELSE 0
            END as quality_rate
        FROM bi.fact_daily_production
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
    # 6. MV 리프레시를 위한 헬퍼 함수
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

    # ============================================
    # 7. dim_kpi 시드 데이터 추가
    # ============================================
    op.execute("""
        INSERT INTO bi.dim_kpi (tenant_id, kpi_code, name, name_en, category, unit, description, higher_is_better, green_threshold, yellow_threshold, red_threshold)
        SELECT tenant_id, 'oee', 'OEE', 'OEE', 'efficiency', '%', '종합설비효율 (Overall Equipment Effectiveness)', true, 85, 70, 60 FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'defect_rate', '불량률', 'Defect Rate', 'quality', '%', '생산 대비 불량 비율', false, 2, 5, 10 FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'yield_rate', '수율', 'Yield Rate', 'quality', '%', '양품 비율', true, 98, 95, 90 FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'availability', '가동률', 'Availability', 'efficiency', '%', '설비 가동률', true, 90, 80, 70 FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'performance', '성능률', 'Performance', 'efficiency', '%', '설비 성능률', true, 95, 85, 75 FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'quality', '품질률', 'Quality Rate', 'quality', '%', '품질률', true, 99, 97, 95 FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'throughput', '생산량', 'Throughput', 'production', '개', '총 생산 수량', true, NULL, NULL, NULL FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'inventory_days', '재고일수', 'Inventory Days', 'inventory', '일', '평균 재고 보유 일수', false, 30, 45, 60 FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'downtime', '비가동시간', 'Downtime', 'efficiency', '분', '설비 비가동 시간', false, 30, 60, 120 FROM core.tenants
        UNION ALL
        SELECT tenant_id, 'cycle_time', '사이클타임', 'Cycle Time', 'production', '초', '단위당 생산 시간', false, 60, 90, 120 FROM core.tenants
        ON CONFLICT (tenant_id, kpi_code) DO NOTHING
    """)


def downgrade() -> None:
    # KPI 시드 데이터 삭제
    op.execute("""
        DELETE FROM bi.dim_kpi
        WHERE kpi_code IN ('oee', 'defect_rate', 'yield_rate', 'availability', 'performance',
                          'quality', 'throughput', 'inventory_days', 'downtime', 'cycle_time')
    """)

    # MV 및 함수 삭제
    op.execute("DROP FUNCTION IF EXISTS bi.refresh_all_mvs() CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_quality_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_line_performance CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_oee_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bi.mv_defect_trend CASCADE")
