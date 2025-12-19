-- =====================================================
-- Migration 018: BI Pre-Aggregation Materialized Views
-- 스펙 참조: B-3-2_BI_Analytics_Schema.md
--
-- 🟡 High: Pre-Agg Materialized Views
--   - mv_defect_trend: 불량 추이 (대시보드용)
--   - mv_oee_daily: 일일 OEE
--   - mv_inventory_coverage: 재고 커버리지
--   - mv_line_performance: 라인별 성과
-- =====================================================

SET search_path TO bi, core, public;

-- =====================================================
-- 1. mv_defect_trend (불량 추이)
-- 목적: 불량률 추이 분석 (대시보드용)
-- 리프레시: 1시간마다
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_defect_trend AS
SELECT
    f.tenant_id,
    f.date,
    f.line_code,
    l.name AS line_name,
    f.product_code,
    p.name AS product_name,
    f.shift,
    SUM(f.total_qty) AS total_qty,
    SUM(f.defect_qty) AS defect_qty,
    CASE
        WHEN SUM(f.total_qty) > 0
        THEN SUM(f.defect_qty)::NUMERIC / SUM(f.total_qty)
        ELSE 0
    END AS defect_rate,
    -- 7일 이동평균 (Window Function)
    AVG(SUM(f.defect_qty)::NUMERIC / NULLIF(SUM(f.total_qty), 0))
        OVER (
            PARTITION BY f.tenant_id, f.line_code, f.product_code
            ORDER BY f.date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS defect_rate_7d_avg
FROM bi.fact_daily_production f
JOIN bi.dim_line l ON f.tenant_id = l.tenant_id AND f.line_code = l.line_code
JOIN bi.dim_product p ON f.tenant_id = p.tenant_id AND f.product_code = p.product_code
WHERE f.date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY f.tenant_id, f.date, f.line_code, l.name, f.product_code, p.name, f.shift;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_defect_trend_pk
    ON bi.mv_defect_trend (tenant_id, date, line_code, product_code, shift);
CREATE INDEX IF NOT EXISTS idx_mv_defect_trend_date
    ON bi.mv_defect_trend (tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_mv_defect_trend_line
    ON bi.mv_defect_trend (tenant_id, line_code, date DESC);

COMMENT ON MATERIALIZED VIEW bi.mv_defect_trend IS '불량률 추이 (최근 90일, 1시간 리프레시)';

-- =====================================================
-- 2. mv_oee_daily (일일 OEE)
-- 목적: OEE (Overall Equipment Effectiveness) 계산
-- OEE = Availability × Performance × Quality
-- 리프레시: 새벽 1회
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_oee_daily AS
SELECT
    f.tenant_id,
    f.date,
    f.line_code,
    l.name AS line_name,
    f.shift,
    SUM(f.total_qty) AS total_qty,
    SUM(f.good_qty) AS good_qty,
    SUM(f.runtime_minutes) AS runtime_minutes,
    SUM(f.downtime_minutes) AS downtime_minutes,
    SUM(f.setup_time_minutes) AS setup_time_minutes,
    -- Availability = Runtime / (Runtime + Downtime)
    CASE
        WHEN SUM(f.runtime_minutes + f.downtime_minutes) > 0
        THEN SUM(f.runtime_minutes)::NUMERIC / SUM(f.runtime_minutes + f.downtime_minutes)
        ELSE 0
    END AS availability,
    -- Performance = (Total Qty × Ideal Cycle Time) / Runtime
    CASE
        WHEN SUM(f.runtime_minutes) > 0 AND AVG(f.target_cycle_time) > 0
        THEN (SUM(f.total_qty) * AVG(f.target_cycle_time) / 60.0) / SUM(f.runtime_minutes)
        ELSE 0
    END AS performance,
    -- Quality = Good Qty / Total Qty
    CASE
        WHEN SUM(f.total_qty) > 0
        THEN SUM(f.good_qty)::NUMERIC / SUM(f.total_qty)
        ELSE 0
    END AS quality,
    -- OEE = Availability × Performance × Quality
    (
        CASE
            WHEN SUM(f.runtime_minutes + f.downtime_minutes) > 0
            THEN SUM(f.runtime_minutes)::NUMERIC / SUM(f.runtime_minutes + f.downtime_minutes)
            ELSE 0
        END
    ) * (
        CASE
            WHEN SUM(f.runtime_minutes) > 0 AND AVG(f.target_cycle_time) > 0
            THEN LEAST((SUM(f.total_qty) * AVG(f.target_cycle_time) / 60.0) / SUM(f.runtime_minutes), 1.0)
            ELSE 0
        END
    ) * (
        CASE
            WHEN SUM(f.total_qty) > 0
            THEN SUM(f.good_qty)::NUMERIC / SUM(f.total_qty)
            ELSE 0
        END
    ) AS oee
FROM bi.fact_daily_production f
JOIN bi.dim_line l ON f.tenant_id = l.tenant_id AND f.line_code = l.line_code
WHERE f.date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY f.tenant_id, f.date, f.line_code, l.name, f.shift;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_oee_daily_pk
    ON bi.mv_oee_daily (tenant_id, date, line_code, shift);
CREATE INDEX IF NOT EXISTS idx_mv_oee_daily_date
    ON bi.mv_oee_daily (tenant_id, date DESC);

COMMENT ON MATERIALIZED VIEW bi.mv_oee_daily IS '일일 OEE (최근 90일, 새벽 1회 리프레시)';

-- =====================================================
-- 3. mv_inventory_coverage (재고 커버리지)
-- 목적: 재고 커버리지 분석
-- 리프레시: 일 1회
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_inventory_coverage AS
SELECT
    i.tenant_id,
    i.date,
    i.product_code,
    p.name AS product_name,
    p.category,
    i.location,
    i.stock_qty,
    i.safety_stock_qty,
    i.available_qty,
    i.avg_daily_usage,
    CASE
        WHEN i.avg_daily_usage > 0
        THEN i.available_qty / i.avg_daily_usage
        ELSE NULL
    END AS coverage_days,
    CASE
        WHEN i.stock_qty < i.safety_stock_qty THEN 'below_safety'
        WHEN i.stock_qty < i.safety_stock_qty * 1.5 THEN 'low'
        WHEN i.stock_qty > i.safety_stock_qty * 3 THEN 'excess'
        ELSE 'normal'
    END AS stock_status
FROM bi.fact_inventory_snapshot i
JOIN bi.dim_product p ON i.tenant_id = p.tenant_id AND i.product_code = p.product_code
WHERE i.date >= CURRENT_DATE - INTERVAL '30 days';

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_inv_cov_pk
    ON bi.mv_inventory_coverage (tenant_id, date, product_code, location);
CREATE INDEX IF NOT EXISTS idx_mv_inv_cov_date
    ON bi.mv_inventory_coverage (tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_mv_inv_cov_status
    ON bi.mv_inventory_coverage (stock_status);

COMMENT ON MATERIALIZED VIEW bi.mv_inventory_coverage IS '재고 커버리지 (최근 30일, 일 1회 리프레시)';

-- =====================================================
-- 4. mv_line_performance (라인별 성과)
-- 목적: 라인별 종합 성과 지표
-- 리프레시: 새벽 1회
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS bi.mv_line_performance AS
WITH production_summary AS (
    SELECT
        f.tenant_id,
        f.date,
        f.line_code,
        f.shift,
        SUM(f.total_qty) AS total_qty,
        SUM(f.good_qty) AS good_qty,
        SUM(f.defect_qty) AS defect_qty,
        SUM(f.runtime_minutes) AS runtime_minutes,
        SUM(f.downtime_minutes) AS downtime_minutes,
        SUM(f.setup_time_minutes) AS setup_time_minutes,
        COUNT(DISTINCT f.product_code) AS product_variety
    FROM bi.fact_daily_production f
    WHERE f.date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY f.tenant_id, f.date, f.line_code, f.shift
),
equipment_summary AS (
    SELECT
        e.tenant_id,
        e.date,
        eq.line_code,
        SUM(CASE WHEN e.event_type = 'alarm' THEN e.event_count ELSE 0 END) AS alarm_count,
        SUM(CASE WHEN e.event_type = 'breakdown' THEN e.event_count ELSE 0 END) AS breakdown_count
    FROM bi.fact_equipment_event e
    JOIN bi.dim_equipment eq ON e.tenant_id = eq.tenant_id AND e.equipment_code = eq.equipment_code
    WHERE e.date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY e.tenant_id, e.date, eq.line_code
)
SELECT
    ps.tenant_id,
    ps.date,
    ps.line_code,
    l.name AS line_name,
    l.category AS line_category,
    ps.shift,
    -- 생산 지표
    ps.total_qty,
    ps.good_qty,
    ps.defect_qty,
    CASE WHEN ps.total_qty > 0 THEN ps.defect_qty::NUMERIC / ps.total_qty ELSE 0 END AS defect_rate,
    -- 시간 지표
    ps.runtime_minutes,
    ps.downtime_minutes,
    ps.setup_time_minutes,
    -- OEE (간소화)
    oee.oee,
    oee.availability,
    oee.performance,
    oee.quality,
    -- 제품 다양성
    ps.product_variety,
    -- 설비 이벤트
    COALESCE(es.alarm_count, 0) AS alarm_count,
    COALESCE(es.breakdown_count, 0) AS breakdown_count
FROM production_summary ps
JOIN bi.dim_line l ON ps.tenant_id = l.tenant_id AND ps.line_code = l.line_code
LEFT JOIN bi.mv_oee_daily oee ON
    ps.tenant_id = oee.tenant_id AND
    ps.date = oee.date AND
    ps.line_code = oee.line_code AND
    ps.shift = oee.shift
LEFT JOIN equipment_summary es ON
    ps.tenant_id = es.tenant_id AND
    ps.date = es.date AND
    ps.line_code = es.line_code;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_line_perf_pk
    ON bi.mv_line_performance (tenant_id, date, line_code, shift);
CREATE INDEX IF NOT EXISTS idx_mv_line_perf_date
    ON bi.mv_line_performance (tenant_id, date DESC);

COMMENT ON MATERIALIZED VIEW bi.mv_line_performance IS '라인별 종합 성과 (최근 90일, 새벽 1회 리프레시)';

-- =====================================================
-- 5. 리프레시 함수
-- =====================================================
CREATE OR REPLACE FUNCTION bi.refresh_all_mv() RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_defect_trend;
    REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_oee_daily;
    REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_inventory_coverage;
    REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_line_performance;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION bi.refresh_hourly_mv() RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_defect_trend;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION bi.refresh_daily_mv() RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_oee_daily;
    REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_inventory_coverage;
    REFRESH MATERIALIZED VIEW CONCURRENTLY bi.mv_line_performance;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION bi.refresh_all_mv IS '모든 Materialized View 리프레시';
COMMENT ON FUNCTION bi.refresh_hourly_mv IS '시간별 리프레시용 MV (mv_defect_trend)';
COMMENT ON FUNCTION bi.refresh_daily_mv IS '일별 리프레시용 MV (oee, inventory, line_perf)';

-- =====================================================
-- 6. BI 카탈로그 (데이터셋, 지표 정의)
-- =====================================================

-- bi_datasets (데이터셋 정의)
CREATE TABLE IF NOT EXISTS bi.bi_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    source_type TEXT NOT NULL CHECK (source_type IN ('postgres_table', 'postgres_view', 'materialized_view', 'api_endpoint')),
    source_ref TEXT NOT NULL,
    default_filters JSONB,
    refresh_schedule TEXT,
    last_refresh_at TIMESTAMPTZ,
    row_count BIGINT,
    created_by UUID REFERENCES core.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_bi_datasets_tenant ON bi.bi_datasets (tenant_id);

COMMENT ON TABLE bi.bi_datasets IS 'BI 데이터셋 정의';
COMMENT ON COLUMN bi.bi_datasets.source_ref IS 'postgres: 테이블/뷰명, api: 엔드포인트 URL';

-- bi_metrics (지표 정의)
CREATE TABLE IF NOT EXISTS bi.bi_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    dataset_id UUID NOT NULL REFERENCES bi.bi_datasets(id) ON DELETE CASCADE,
    expression_sql TEXT NOT NULL,
    agg_type TEXT CHECK (agg_type IN ('sum', 'avg', 'min', 'max', 'count', 'distinct_count', 'median', 'percentile')),
    format_type TEXT CHECK (format_type IN ('number', 'percent', 'currency', 'duration')),
    format_options JSONB,
    default_chart_type TEXT,
    created_by UUID REFERENCES core.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_bi_metrics_dataset ON bi.bi_metrics (dataset_id);

COMMENT ON TABLE bi.bi_metrics IS 'BI 지표 정의';

-- bi_dashboards (대시보드 정의)
CREATE TABLE IF NOT EXISTS bi.bi_dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    layout JSONB NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT false,
    owner_id UUID NOT NULL REFERENCES core.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_bi_dashboards_tenant ON bi.bi_dashboards (tenant_id);
CREATE INDEX IF NOT EXISTS idx_bi_dashboards_owner ON bi.bi_dashboards (owner_id);

COMMENT ON TABLE bi.bi_dashboards IS 'BI 대시보드 정의';

-- =====================================================
-- 7. ETL 메타데이터
-- =====================================================

-- etl_jobs (ETL 작업 정의)
CREATE TABLE IF NOT EXISTS bi.etl_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    job_type TEXT NOT NULL CHECK (job_type IN ('raw_to_fact', 'fact_to_agg', 'refresh_mv', 'data_quality')),
    source_tables TEXT[] NOT NULL,
    target_tables TEXT[] NOT NULL,
    transform_logic TEXT,
    schedule_cron TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    max_runtime_minutes INT NOT NULL DEFAULT 60,
    retry_count INT NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_etl_jobs_tenant ON bi.etl_jobs (tenant_id);

COMMENT ON TABLE bi.etl_jobs IS 'ETL 작업 정의';

-- etl_job_executions (ETL 실행 이력)
CREATE TABLE IF NOT EXISTS bi.etl_job_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES bi.etl_jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    rows_processed BIGINT,
    rows_inserted BIGINT,
    rows_updated BIGINT,
    rows_deleted BIGINT,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    duration_seconds INT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_etl_executions_job ON bi.etl_job_executions (job_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_etl_executions_status ON bi.etl_job_executions (status) WHERE status = 'running';

COMMENT ON TABLE bi.etl_job_executions IS 'ETL 실행 이력';

-- =====================================================
-- 8. 데이터 품질 체크
-- =====================================================

-- data_quality_rules (품질 규칙)
CREATE TABLE IF NOT EXISTS bi.data_quality_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    table_name TEXT NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('not_null', 'range', 'uniqueness', 'referential_integrity', 'pattern', 'custom_sql')),
    rule_config JSONB NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

COMMENT ON TABLE bi.data_quality_rules IS '데이터 품질 검증 규칙';

-- data_quality_checks (품질 체크 결과)
CREATE TABLE IF NOT EXISTS bi.data_quality_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID NOT NULL REFERENCES bi.data_quality_rules(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'warning')),
    failed_row_count INT,
    total_row_count INT,
    sample_failed_rows JSONB,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_dq_checks_rule ON bi.data_quality_checks (rule_id, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_dq_checks_status ON bi.data_quality_checks (status) WHERE status = 'fail';

COMMENT ON TABLE bi.data_quality_checks IS '데이터 품질 체크 결과';

-- =====================================================
-- 9. updated_at 트리거
-- =====================================================
DROP TRIGGER IF EXISTS trigger_bi_datasets_updated_at ON bi.bi_datasets;
CREATE TRIGGER trigger_bi_datasets_updated_at
    BEFORE UPDATE ON bi.bi_datasets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_bi_metrics_updated_at ON bi.bi_metrics;
CREATE TRIGGER trigger_bi_metrics_updated_at
    BEFORE UPDATE ON bi.bi_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_bi_dashboards_updated_at ON bi.bi_dashboards;
CREATE TRIGGER trigger_bi_dashboards_updated_at
    BEFORE UPDATE ON bi.bi_dashboards
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_etl_jobs_updated_at ON bi.etl_jobs;
CREATE TRIGGER trigger_etl_jobs_updated_at
    BEFORE UPDATE ON bi.etl_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 10. 샘플 데이터셋 및 지표 시드
-- =====================================================
INSERT INTO bi.bi_datasets (tenant_id, name, source_type, source_ref, description, refresh_schedule)
SELECT
    t.tenant_id,
    ds.name,
    ds.source_type,
    ds.source_ref,
    ds.description,
    ds.refresh_schedule
FROM core.tenants t
CROSS JOIN (VALUES
    ('불량추이', 'materialized_view', 'bi.mv_defect_trend', '불량률 추이 데이터', '0 * * * *'),
    ('일일OEE', 'materialized_view', 'bi.mv_oee_daily', '일일 OEE 지표', '0 3 * * *'),
    ('재고커버리지', 'materialized_view', 'bi.mv_inventory_coverage', '재고 커버리지 현황', '0 4 * * *'),
    ('라인성과', 'materialized_view', 'bi.mv_line_performance', '라인별 종합 성과', '0 5 * * *')
) AS ds(name, source_type, source_ref, description, refresh_schedule)
ON CONFLICT (tenant_id, name) DO NOTHING;

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
