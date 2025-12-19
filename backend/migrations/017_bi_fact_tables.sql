-- =====================================================
-- Migration 017: BI Fact Tables
-- 스펙 참조: B-3-2_BI_Analytics_Schema.md
--
-- 🟡 High: FACT 테이블 (Star Schema)
--   - fact_daily_production: 일일 생산 실적
--   - fact_daily_defect: 일일 불량 실적
--   - fact_inventory_snapshot: 재고 스냅샷
--   - fact_equipment_event: 설비 이벤트 집계
--   - fact_hourly_production: 시간별 생산 실적
-- =====================================================

SET search_path TO bi, core, public;

-- =====================================================
-- 1. fact_daily_production (일일 생산 실적)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.fact_daily_production (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    line_code TEXT NOT NULL,
    product_code TEXT NOT NULL,
    shift TEXT NOT NULL,

    -- 생산량
    total_qty NUMERIC NOT NULL DEFAULT 0,
    good_qty NUMERIC NOT NULL DEFAULT 0,
    defect_qty NUMERIC NOT NULL DEFAULT 0,
    rework_qty NUMERIC NOT NULL DEFAULT 0,
    scrap_qty NUMERIC NOT NULL DEFAULT 0,

    -- 사이클타임
    cycle_time_avg NUMERIC,
    cycle_time_std NUMERIC,

    -- 시간 지표
    runtime_minutes NUMERIC NOT NULL DEFAULT 0,
    downtime_minutes NUMERIC NOT NULL DEFAULT 0,
    setup_time_minutes NUMERIC NOT NULL DEFAULT 0,

    -- 계획 대비
    planned_qty NUMERIC,
    target_cycle_time NUMERIC,

    -- 추가 지표
    work_order_count INT NOT NULL DEFAULT 0,
    operator_count INT,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (tenant_id, date, line_code, product_code, shift),
    FOREIGN KEY (date) REFERENCES bi.dim_date(date),
    FOREIGN KEY (tenant_id, line_code) REFERENCES bi.dim_line(tenant_id, line_code),
    FOREIGN KEY (tenant_id, product_code) REFERENCES bi.dim_product(tenant_id, product_code)
) PARTITION BY RANGE (date);

-- 2025년 분기별 파티션 생성
CREATE TABLE IF NOT EXISTS bi.fact_daily_production_y2025q1 PARTITION OF bi.fact_daily_production
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS bi.fact_daily_production_y2025q2 PARTITION OF bi.fact_daily_production
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS bi.fact_daily_production_y2025q3 PARTITION OF bi.fact_daily_production
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS bi.fact_daily_production_y2025q4 PARTITION OF bi.fact_daily_production
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
-- 2026년 Q1 파티션
CREATE TABLE IF NOT EXISTS bi.fact_daily_production_y2026q1 PARTITION OF bi.fact_daily_production
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE INDEX IF NOT EXISTS idx_fact_daily_prod_date ON bi.fact_daily_production (tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_fact_daily_prod_line ON bi.fact_daily_production (tenant_id, line_code, date DESC);
CREATE INDEX IF NOT EXISTS idx_fact_daily_prod_product ON bi.fact_daily_production (tenant_id, product_code, date DESC);

COMMENT ON TABLE bi.fact_daily_production IS '일일 생산 실적 FACT (분기별 파티션)';

-- =====================================================
-- 2. fact_daily_defect (일일 불량 실적)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.fact_daily_defect (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    line_code TEXT NOT NULL,
    product_code TEXT NOT NULL,
    shift TEXT NOT NULL,
    defect_type TEXT NOT NULL,

    -- 불량 지표
    defect_qty NUMERIC NOT NULL DEFAULT 0,
    defect_cost NUMERIC,

    -- 원인 분석
    root_cause TEXT,
    countermeasure TEXT,
    responsible_dept TEXT,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (tenant_id, date, line_code, product_code, shift, defect_type),
    FOREIGN KEY (date) REFERENCES bi.dim_date(date),
    FOREIGN KEY (tenant_id, line_code) REFERENCES bi.dim_line(tenant_id, line_code),
    FOREIGN KEY (tenant_id, product_code) REFERENCES bi.dim_product(tenant_id, product_code)
) PARTITION BY RANGE (date);

-- 2025년 분기별 파티션 생성
CREATE TABLE IF NOT EXISTS bi.fact_daily_defect_y2025q1 PARTITION OF bi.fact_daily_defect
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS bi.fact_daily_defect_y2025q2 PARTITION OF bi.fact_daily_defect
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS bi.fact_daily_defect_y2025q3 PARTITION OF bi.fact_daily_defect
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS bi.fact_daily_defect_y2025q4 PARTITION OF bi.fact_daily_defect
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE IF NOT EXISTS bi.fact_daily_defect_y2026q1 PARTITION OF bi.fact_daily_defect
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE INDEX IF NOT EXISTS idx_fact_daily_defect_date ON bi.fact_daily_defect (tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_fact_daily_defect_type ON bi.fact_daily_defect (defect_type, date DESC);

COMMENT ON TABLE bi.fact_daily_defect IS '일일 불량 상세 FACT';

-- =====================================================
-- 3. fact_inventory_snapshot (재고 스냅샷)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.fact_inventory_snapshot (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    product_code TEXT NOT NULL,
    location TEXT NOT NULL,

    -- 재고 수량
    stock_qty NUMERIC NOT NULL DEFAULT 0,
    safety_stock_qty NUMERIC NOT NULL DEFAULT 0,
    reserved_qty NUMERIC NOT NULL DEFAULT 0,
    available_qty NUMERIC NOT NULL DEFAULT 0,
    in_transit_qty NUMERIC NOT NULL DEFAULT 0,

    -- 가치
    stock_value NUMERIC,

    -- 분석 지표
    avg_daily_usage NUMERIC,
    coverage_days NUMERIC,

    -- 최근 거래
    last_receipt_date DATE,
    last_issue_date DATE,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (tenant_id, date, product_code, location),
    FOREIGN KEY (date) REFERENCES bi.dim_date(date),
    FOREIGN KEY (tenant_id, product_code) REFERENCES bi.dim_product(tenant_id, product_code)
) PARTITION BY RANGE (date);

-- 2025년 분기별 파티션 생성
CREATE TABLE IF NOT EXISTS bi.fact_inventory_snapshot_y2025q1 PARTITION OF bi.fact_inventory_snapshot
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS bi.fact_inventory_snapshot_y2025q2 PARTITION OF bi.fact_inventory_snapshot
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS bi.fact_inventory_snapshot_y2025q3 PARTITION OF bi.fact_inventory_snapshot
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS bi.fact_inventory_snapshot_y2025q4 PARTITION OF bi.fact_inventory_snapshot
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE IF NOT EXISTS bi.fact_inventory_snapshot_y2026q1 PARTITION OF bi.fact_inventory_snapshot
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE INDEX IF NOT EXISTS idx_fact_inv_snapshot_date ON bi.fact_inventory_snapshot (tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_fact_inv_snapshot_product ON bi.fact_inventory_snapshot (tenant_id, product_code, date DESC);

COMMENT ON TABLE bi.fact_inventory_snapshot IS '일별 재고 스냅샷 FACT';
COMMENT ON COLUMN bi.fact_inventory_snapshot.coverage_days IS '재고 커버리지 일수 (재고량 / 일평균 사용량)';

-- =====================================================
-- 4. fact_equipment_event (설비 이벤트 집계)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.fact_equipment_event (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    equipment_code TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('alarm', 'breakdown', 'maintenance', 'setup', 'idle')),

    -- 집계 지표
    event_count INT NOT NULL DEFAULT 0,
    total_duration_minutes NUMERIC NOT NULL DEFAULT 0,
    avg_duration_minutes NUMERIC,
    max_duration_minutes NUMERIC,

    -- 상세
    severity_distribution JSONB,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (tenant_id, date, equipment_code, event_type),
    FOREIGN KEY (date) REFERENCES bi.dim_date(date),
    FOREIGN KEY (tenant_id, equipment_code) REFERENCES bi.dim_equipment(tenant_id, equipment_code)
) PARTITION BY RANGE (date);

-- 2025년 분기별 파티션 생성
CREATE TABLE IF NOT EXISTS bi.fact_equipment_event_y2025q1 PARTITION OF bi.fact_equipment_event
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS bi.fact_equipment_event_y2025q2 PARTITION OF bi.fact_equipment_event
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS bi.fact_equipment_event_y2025q3 PARTITION OF bi.fact_equipment_event
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS bi.fact_equipment_event_y2025q4 PARTITION OF bi.fact_equipment_event
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE IF NOT EXISTS bi.fact_equipment_event_y2026q1 PARTITION OF bi.fact_equipment_event
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE INDEX IF NOT EXISTS idx_fact_equip_event_date ON bi.fact_equipment_event (tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_fact_equip_event_equip ON bi.fact_equipment_event (tenant_id, equipment_code, date DESC);

COMMENT ON TABLE bi.fact_equipment_event IS '설비 이벤트 집계 FACT';

-- =====================================================
-- 5. fact_hourly_production (시간별 생산 실적)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    hour_timestamp TIMESTAMPTZ NOT NULL,
    line_code TEXT NOT NULL,
    product_code TEXT NOT NULL,

    -- 생산량
    total_qty NUMERIC NOT NULL DEFAULT 0,
    good_qty NUMERIC NOT NULL DEFAULT 0,
    defect_qty NUMERIC NOT NULL DEFAULT 0,

    -- 사이클타임
    cycle_time_avg NUMERIC,

    -- 시간 지표
    runtime_minutes NUMERIC NOT NULL DEFAULT 0,
    downtime_minutes NUMERIC NOT NULL DEFAULT 0,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (tenant_id, hour_timestamp, line_code, product_code),
    FOREIGN KEY (tenant_id, line_code) REFERENCES bi.dim_line(tenant_id, line_code),
    FOREIGN KEY (tenant_id, product_code) REFERENCES bi.dim_product(tenant_id, product_code)
) PARTITION BY RANGE (hour_timestamp);

-- 2025년 월별 파티션 생성 (시간별 데이터는 더 세분화)
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m01 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m02 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m03 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m04 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m05 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m06 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m07 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m08 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m09 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m10 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m11 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE IF NOT EXISTS bi.fact_hourly_production_y2025m12 PARTITION OF bi.fact_hourly_production
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

CREATE INDEX IF NOT EXISTS idx_fact_hourly_prod_time ON bi.fact_hourly_production (tenant_id, hour_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_fact_hourly_prod_line ON bi.fact_hourly_production (tenant_id, line_code, hour_timestamp DESC);

COMMENT ON TABLE bi.fact_hourly_production IS '시간별 생산 실적 FACT (실시간 모니터링용)';

-- =====================================================
-- 6. 계산 필드 뷰 (fact_daily_production)
-- =====================================================
CREATE OR REPLACE VIEW bi.v_fact_daily_production_calc AS
SELECT
    *,
    CASE WHEN total_qty > 0 THEN good_qty::NUMERIC / total_qty ELSE 0 END AS yield_rate,
    CASE WHEN total_qty > 0 THEN defect_qty::NUMERIC / total_qty ELSE 0 END AS defect_rate,
    CASE WHEN planned_qty > 0 THEN total_qty::NUMERIC / planned_qty ELSE 0 END AS achievement_rate,
    (runtime_minutes + downtime_minutes + setup_time_minutes) AS total_time_minutes,
    CASE
        WHEN (runtime_minutes + downtime_minutes + setup_time_minutes) > 0
        THEN runtime_minutes::NUMERIC / (runtime_minutes + downtime_minutes + setup_time_minutes)
        ELSE 0
    END AS availability
FROM bi.fact_daily_production;

COMMENT ON VIEW bi.v_fact_daily_production_calc IS '일일 생산 실적 + 계산 필드 뷰';

-- =====================================================
-- 7. updated_at 트리거
-- =====================================================
DROP TRIGGER IF EXISTS trigger_fact_daily_production_updated_at ON bi.fact_daily_production;
CREATE TRIGGER trigger_fact_daily_production_updated_at
    BEFORE UPDATE ON bi.fact_daily_production
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_fact_daily_defect_updated_at ON bi.fact_daily_defect;
CREATE TRIGGER trigger_fact_daily_defect_updated_at
    BEFORE UPDATE ON bi.fact_daily_defect
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_fact_equipment_event_updated_at ON bi.fact_equipment_event;
CREATE TRIGGER trigger_fact_equipment_event_updated_at
    BEFORE UPDATE ON bi.fact_equipment_event
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 8. 파티션 자동 생성 함수
-- =====================================================
CREATE OR REPLACE FUNCTION bi.create_quarterly_partitions(
    p_table_name TEXT,
    p_start_year INT,
    p_end_year INT
) RETURNS VOID AS $$
DECLARE
    v_partition_name TEXT;
    v_start_date DATE;
    v_end_date DATE;
    v_year INT;
    v_quarter INT;
BEGIN
    FOR v_year IN p_start_year..p_end_year LOOP
        FOR v_quarter IN 1..4 LOOP
            v_start_date := make_date(v_year, (v_quarter - 1) * 3 + 1, 1);
            v_end_date := v_start_date + INTERVAL '3 months';
            v_partition_name := p_table_name || '_y' || v_year || 'q' || v_quarter;

            BEGIN
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS bi.%I PARTITION OF bi.%I FOR VALUES FROM (%L) TO (%L)',
                    v_partition_name, p_table_name, v_start_date, v_end_date
                );
            EXCEPTION WHEN duplicate_table THEN
                -- 이미 존재하면 무시
                NULL;
            END;
        END LOOP;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION bi.create_monthly_partitions(
    p_table_name TEXT,
    p_start_date DATE,
    p_end_date DATE
) RETURNS VOID AS $$
DECLARE
    v_partition_name TEXT;
    v_current_date DATE;
    v_next_date DATE;
BEGIN
    v_current_date := date_trunc('month', p_start_date);

    WHILE v_current_date < p_end_date LOOP
        v_next_date := v_current_date + INTERVAL '1 month';
        v_partition_name := p_table_name || '_y' || to_char(v_current_date, 'YYYY') || 'm' || to_char(v_current_date, 'MM');

        BEGIN
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS bi.%I PARTITION OF bi.%I FOR VALUES FROM (%L) TO (%L)',
                v_partition_name, p_table_name, v_current_date, v_next_date
            );
        EXCEPTION WHEN duplicate_table THEN
            -- 이미 존재하면 무시
            NULL;
        END;

        v_current_date := v_next_date;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION bi.create_quarterly_partitions IS '분기별 파티션 자동 생성';
COMMENT ON FUNCTION bi.create_monthly_partitions IS '월별 파티션 자동 생성';

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
