-- =====================================================
-- Migration 016: BI Dimension Tables
-- 스펙 참조: B-3-2_BI_Analytics_Schema.md
--
-- 🟡 High: DIM 테이블 (Star Schema)
--   - dim_date: 날짜 차원
--   - dim_line: 생산 라인 마스터
--   - dim_product: 제품 마스터
--   - dim_equipment: 설비 마스터
--   - dim_kpi: KPI 정의
--   - dim_shift: 교대 정의
-- =====================================================

-- BI 스키마 생성 (이미 존재하면 무시)
CREATE SCHEMA IF NOT EXISTS bi;

SET search_path TO bi, core, public;

-- =====================================================
-- 1. dim_date (날짜 차원)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.dim_date (
    date DATE PRIMARY KEY,
    year INT NOT NULL,
    quarter INT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month INT NOT NULL CHECK (month BETWEEN 1 AND 12),
    week INT NOT NULL CHECK (week BETWEEN 1 AND 53),
    day_of_year INT NOT NULL CHECK (day_of_year BETWEEN 1 AND 366),
    day_of_month INT NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    day_name TEXT NOT NULL,
    month_name TEXT NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN NOT NULL DEFAULT false,
    holiday_name TEXT,
    fiscal_year INT,
    fiscal_quarter INT,
    fiscal_month INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dim_date_year_month ON bi.dim_date (year, month);
CREATE INDEX IF NOT EXISTS idx_dim_date_is_holiday ON bi.dim_date (is_holiday) WHERE is_holiday = true;

COMMENT ON TABLE bi.dim_date IS '날짜 차원 테이블 (2020-2030)';

-- dim_date 시드 데이터 생성 (2020-2030)
INSERT INTO bi.dim_date (
    date, year, quarter, month, week, day_of_year, day_of_month,
    day_of_week, day_name, month_name, is_weekend
)
SELECT
    d::date,
    EXTRACT(year FROM d)::int,
    EXTRACT(quarter FROM d)::int,
    EXTRACT(month FROM d)::int,
    EXTRACT(week FROM d)::int,
    EXTRACT(doy FROM d)::int,
    EXTRACT(day FROM d)::int,
    EXTRACT(dow FROM d)::int,
    trim(to_char(d, 'Day')),
    trim(to_char(d, 'Month')),
    EXTRACT(dow FROM d) IN (0, 6)
FROM generate_series('2020-01-01'::date, '2030-12-31'::date, '1 day'::interval) d
ON CONFLICT (date) DO NOTHING;

-- =====================================================
-- 2. dim_line (생산 라인 마스터)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.dim_line (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    line_code TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT CHECK (category IN ('assembly', 'processing', 'packaging', 'inspection', 'warehouse')),
    capacity_per_hour NUMERIC,
    capacity_unit TEXT,
    timezone TEXT NOT NULL DEFAULT 'Asia/Seoul',
    plant_code TEXT,
    department TEXT,
    manager TEXT,
    cost_center TEXT,
    attributes JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    activated_at DATE,
    deactivated_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, line_code)
);

CREATE INDEX IF NOT EXISTS idx_dim_line_active ON bi.dim_line (tenant_id, is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_dim_line_category ON bi.dim_line (category);

COMMENT ON TABLE bi.dim_line IS '생산 라인 차원 테이블';
COMMENT ON COLUMN bi.dim_line.attributes IS 'JSON: shift_pattern, automation_level, target_oee 등';

-- =====================================================
-- 3. dim_product (제품 마스터)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.dim_product (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    product_code TEXT NOT NULL,
    name TEXT NOT NULL,
    name_en TEXT,
    spec TEXT,
    category TEXT,
    subcategory TEXT,
    unit TEXT NOT NULL DEFAULT 'EA',
    standard_cost NUMERIC,
    target_cycle_time_sec NUMERIC,
    quality_standard TEXT,
    attributes JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    activated_at DATE,
    discontinued_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, product_code)
);

CREATE INDEX IF NOT EXISTS idx_dim_product_active ON bi.dim_product (tenant_id, is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_dim_product_category ON bi.dim_product (category, subcategory);

COMMENT ON TABLE bi.dim_product IS '제품 차원 테이블';

-- =====================================================
-- 4. dim_equipment (설비 마스터)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.dim_equipment (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    equipment_code TEXT NOT NULL,
    line_code TEXT NOT NULL,
    name TEXT NOT NULL,
    equipment_type TEXT CHECK (equipment_type IN ('machine', 'robot', 'conveyor', 'inspection', 'utility')),
    vendor TEXT,
    model TEXT,
    serial_number TEXT,
    install_date DATE,
    warranty_expiry_date DATE,
    maintenance_cycle_days INT,
    last_maintenance_date DATE,
    next_maintenance_date DATE,
    mtbf_hours NUMERIC,
    mttr_hours NUMERIC,
    attributes JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, equipment_code),
    FOREIGN KEY (tenant_id, line_code) REFERENCES bi.dim_line(tenant_id, line_code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dim_equipment_line ON bi.dim_equipment (tenant_id, line_code);
CREATE INDEX IF NOT EXISTS idx_dim_equipment_type ON bi.dim_equipment (equipment_type);
CREATE INDEX IF NOT EXISTS idx_dim_equipment_maintenance ON bi.dim_equipment (next_maintenance_date) WHERE is_active = true;

COMMENT ON TABLE bi.dim_equipment IS '설비 차원 테이블';
COMMENT ON COLUMN bi.dim_equipment.mtbf_hours IS 'Mean Time Between Failures (평균 고장 간격)';
COMMENT ON COLUMN bi.dim_equipment.mttr_hours IS 'Mean Time To Repair (평균 수리 시간)';

-- =====================================================
-- 5. dim_kpi (KPI 정의)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.dim_kpi (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    kpi_code TEXT NOT NULL,
    name TEXT NOT NULL,
    name_en TEXT,
    category TEXT NOT NULL CHECK (category IN ('quality', 'production', 'efficiency', 'cost', 'safety', 'inventory')),
    unit TEXT,
    description TEXT,
    calculation_method TEXT,
    default_target NUMERIC,
    green_threshold NUMERIC,
    yellow_threshold NUMERIC,
    red_threshold NUMERIC,
    higher_is_better BOOLEAN NOT NULL DEFAULT true,
    aggregation_method TEXT CHECK (aggregation_method IN ('sum', 'avg', 'min', 'max', 'last')),
    attributes JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, kpi_code)
);

CREATE INDEX IF NOT EXISTS idx_dim_kpi_category ON bi.dim_kpi (category);

COMMENT ON TABLE bi.dim_kpi IS 'KPI 정의 차원 테이블';
COMMENT ON COLUMN bi.dim_kpi.higher_is_better IS 'true: 높을수록 좋음 (OEE), false: 낮을수록 좋음 (불량률)';

-- =====================================================
-- 6. dim_shift (교대 정의)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.dim_shift (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    shift_code TEXT NOT NULL,
    name TEXT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    duration_hours NUMERIC NOT NULL,
    is_night_shift BOOLEAN NOT NULL DEFAULT false,
    shift_order INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, shift_code)
);

COMMENT ON TABLE bi.dim_shift IS '교대 차원 테이블';

-- =====================================================
-- 7. updated_at 트리거
-- =====================================================
DROP TRIGGER IF EXISTS trigger_dim_line_updated_at ON bi.dim_line;
CREATE TRIGGER trigger_dim_line_updated_at
    BEFORE UPDATE ON bi.dim_line
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_dim_product_updated_at ON bi.dim_product;
CREATE TRIGGER trigger_dim_product_updated_at
    BEFORE UPDATE ON bi.dim_product
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_dim_equipment_updated_at ON bi.dim_equipment;
CREATE TRIGGER trigger_dim_equipment_updated_at
    BEFORE UPDATE ON bi.dim_equipment
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_dim_kpi_updated_at ON bi.dim_kpi;
CREATE TRIGGER trigger_dim_kpi_updated_at
    BEFORE UPDATE ON bi.dim_kpi
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 8. 샘플 시드 데이터 (개발/테스트용)
-- =====================================================

-- 기본 테넌트의 샘플 KPI 정의
INSERT INTO bi.dim_kpi (tenant_id, kpi_code, name, name_en, category, unit, default_target, higher_is_better, aggregation_method)
SELECT
    t.tenant_id,
    kpi.code,
    kpi.name,
    kpi.name_en,
    kpi.category,
    kpi.unit,
    kpi.target,
    kpi.higher_is_better,
    kpi.agg_method
FROM core.tenants t
CROSS JOIN (VALUES
    ('defect_rate', '불량률', 'Defect Rate', 'quality', '%', 3.0, false, 'avg'),
    ('oee', 'OEE', 'OEE', 'efficiency', '%', 85.0, true, 'avg'),
    ('cycle_time', '사이클타임', 'Cycle Time', 'production', 'sec', 45.0, false, 'avg'),
    ('yield_rate', '수율', 'Yield Rate', 'quality', '%', 97.0, true, 'avg'),
    ('downtime', '다운타임', 'Downtime', 'efficiency', 'min', 30.0, false, 'sum'),
    ('inventory_days', '재고일수', 'Inventory Days', 'inventory', 'days', 7.0, false, 'last')
) AS kpi(code, name, name_en, category, unit, target, higher_is_better, agg_method)
ON CONFLICT (tenant_id, kpi_code) DO NOTHING;

-- 기본 테넌트의 샘플 교대 정의
INSERT INTO bi.dim_shift (tenant_id, shift_code, name, start_time, end_time, duration_hours, is_night_shift, shift_order)
SELECT
    t.tenant_id,
    shift.code,
    shift.name,
    shift.start_time,
    shift.end_time,
    shift.duration,
    shift.is_night,
    shift.order_num
FROM core.tenants t
CROSS JOIN (VALUES
    ('day', '주간', '08:00'::TIME, '16:00'::TIME, 8.0, false, 1),
    ('evening', '오후', '16:00'::TIME, '00:00'::TIME, 8.0, false, 2),
    ('night', '야간', '00:00'::TIME, '08:00'::TIME, 8.0, true, 3)
) AS shift(code, name, start_time, end_time, duration, is_night, order_num)
ON CONFLICT (tenant_id, shift_code) DO NOTHING;

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
