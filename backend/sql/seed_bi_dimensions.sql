-- ============================================
-- BI Dimension 테이블 시드 데이터 생성
-- ============================================
-- 스펙 참조: B-3-2 § 3
-- 작성일: 2026-01-22
-- 용도: BI Star Schema JOIN을 위한 필수 Dimension 데이터
--
-- 실행 방법:
-- psql -U postgres -d triflow < backend/sql/seed_bi_dimensions.sql
-- ============================================

-- ============================================
-- 1. dim_date: 날짜 차원 (2020-2030, 10년치)
-- ============================================
-- 스펙: B-3-2 § 3.1
-- 개수: 약 3,650개

INSERT INTO bi.dim_date (
    date,
    year,
    quarter,
    month,
    week,
    day_of_year,
    day_of_month,
    day_of_week,
    day_name,
    is_weekend,
    is_holiday,
    holiday_name,
    fiscal_year,
    fiscal_quarter
)
SELECT
    d::date AS date,
    EXTRACT(year FROM d)::int AS year,
    EXTRACT(quarter FROM d)::int AS quarter,
    EXTRACT(month FROM d)::int AS month,
    EXTRACT(week FROM d)::int AS week,
    EXTRACT(doy FROM d)::int AS day_of_year,
    EXTRACT(day FROM d)::int AS day_of_month,
    EXTRACT(dow FROM d)::int AS day_of_week,
    TRIM(to_char(d, 'Day')) AS day_name,
    EXTRACT(dow FROM d) IN (0, 6) AS is_weekend,
    FALSE AS is_holiday,
    NULL AS holiday_name,
    -- Fiscal year (4월 시작 가정)
    CASE
        WHEN EXTRACT(month FROM d) >= 4
        THEN EXTRACT(year FROM d)::int
        ELSE EXTRACT(year FROM d)::int - 1
    END AS fiscal_year,
    CASE
        WHEN EXTRACT(month FROM d) IN (4, 5, 6) THEN 1
        WHEN EXTRACT(month FROM d) IN (7, 8, 9) THEN 2
        WHEN EXTRACT(month FROM d) IN (10, 11, 12) THEN 3
        ELSE 4
    END AS fiscal_quarter
FROM generate_series('2020-01-01'::date, '2030-12-31'::date, '1 day'::interval) d
ON CONFLICT (date) DO NOTHING;

-- 한국 공휴일 업데이트 (주요 공휴일만)
UPDATE bi.dim_date
SET is_holiday = TRUE, holiday_name = '신정'
WHERE month = 1 AND day_of_month = 1;

UPDATE bi.dim_date
SET is_holiday = TRUE, holiday_name = '광복절'
WHERE month = 8 AND day_of_month = 15;

UPDATE bi.dim_date
SET is_holiday = TRUE, holiday_name = '개천절'
WHERE month = 10 AND day_of_month = 3;

UPDATE bi.dim_date
SET is_holiday = TRUE, holiday_name = '한글날'
WHERE month = 10 AND day_of_month = 9;

UPDATE bi.dim_date
SET is_holiday = TRUE, holiday_name = '크리스마스'
WHERE month = 12 AND day_of_month = 25;

SELECT COUNT(*) AS dim_date_count FROM bi.dim_date;
-- Expected: ~3,650 rows

-- ============================================
-- 2. dim_shift: 교대 차원 (기본 3교대)
-- ============================================
-- 스펙: B-3-2 § 3.6
-- 개수: 3개 (각 tenant별로 실행 필요)

-- 기본 tenant_id 조회
DO $$
DECLARE
    v_tenant_id uuid;
BEGIN
    -- 첫 번째 tenant_id 조회
    SELECT tenant_id INTO v_tenant_id
    FROM core.tenants
    ORDER BY created_at
    LIMIT 1;

    -- tenant_id가 있으면 shift 시드 생성
    IF v_tenant_id IS NOT NULL THEN
        INSERT INTO bi.dim_shift (
            tenant_id,
            shift_code,
            name,
            start_time,
            end_time,
            duration_hours,
            is_night_shift,
            shift_order
        )
        VALUES
            (v_tenant_id, 'A', '주간', '08:00'::time, '16:00'::time, 8.0, FALSE, 1),
            (v_tenant_id, 'B', '오후', '16:00'::time, '00:00'::time, 8.0, FALSE, 2),
            (v_tenant_id, 'C', '야간', '00:00'::time, '08:00'::time, 8.0, TRUE, 3)
        ON CONFLICT (tenant_id, shift_code) DO NOTHING;

        RAISE NOTICE 'Created shift data for tenant: %', v_tenant_id;
    ELSE
        RAISE NOTICE 'No tenant found. Create tenant first.';
    END IF;
END $$;

SELECT COUNT(*) AS dim_shift_count FROM bi.dim_shift;
-- Expected: 3 rows per tenant

-- ============================================
-- 3. dim_line: 라인 차원 (샘플)
-- ============================================
-- 스펙: B-3-2 § 3.2
-- 개수: 3개 샘플

DO $$
DECLARE
    v_tenant_id uuid;
BEGIN
    SELECT tenant_id INTO v_tenant_id
    FROM core.tenants
    ORDER BY created_at
    LIMIT 1;

    IF v_tenant_id IS NOT NULL THEN
        INSERT INTO bi.dim_line (
            tenant_id,
            line_code,
            name,
            line_type,
            capacity_per_day,
            is_active
        )
        VALUES
            (v_tenant_id, 'LINE-A', 'A 라인', 'Assembly', 5000, TRUE),
            (v_tenant_id, 'LINE-B', 'B 라인', 'Packaging', 3000, TRUE),
            (v_tenant_id, 'LINE-C', 'C 라인', 'Inspection', 2000, TRUE)
        ON CONFLICT (tenant_id, line_code) DO NOTHING;

        RAISE NOTICE 'Created line data for tenant: %', v_tenant_id;
    END IF;
END $$;

SELECT COUNT(*) AS dim_line_count FROM bi.dim_line;
-- Expected: 3 rows

-- ============================================
-- 4. dim_product: 제품 차원 (샘플)
-- ============================================
-- 스펙: B-3-2 § 3.3
-- 개수: 5개 샘플

DO $$
DECLARE
    v_tenant_id uuid;
BEGIN
    SELECT tenant_id INTO v_tenant_id
    FROM core.tenants
    ORDER BY created_at
    LIMIT 1;

    IF v_tenant_id IS NOT NULL THEN
        INSERT INTO bi.dim_product (
            tenant_id,
            product_code,
            name,
            category,
            subcategory,
            unit,
            is_active
        )
        VALUES
            (v_tenant_id, 'PROD-X', '제품 X', '전자부품', 'Type-A', 'EA', TRUE),
            (v_tenant_id, 'PROD-Y', '제품 Y', '기계부품', 'Type-B', 'EA', TRUE),
            (v_tenant_id, 'PROD-Z', '제품 Z', '전자부품', 'Type-C', 'EA', TRUE),
            (v_tenant_id, 'PROD-W', '제품 W', '조립품', 'Type-D', 'SET', TRUE),
            (v_tenant_id, 'PROD-V', '제품 V', '포장재', 'Type-E', 'BOX', TRUE)
        ON CONFLICT (tenant_id, product_code) DO NOTHING;

        RAISE NOTICE 'Created product data for tenant: %', v_tenant_id;
    END IF;
END $$;

SELECT COUNT(*) AS dim_product_count FROM bi.dim_product;
-- Expected: 5 rows

-- ============================================
-- 5. dim_equipment: 설비 차원 (샘플)
-- ============================================
-- 스펙: B-3-2 § 3.4
-- 개수: 5개 샘플

DO $$
DECLARE
    v_tenant_id uuid;
BEGIN
    SELECT tenant_id INTO v_tenant_id
    FROM core.tenants
    ORDER BY created_at
    LIMIT 1;

    IF v_tenant_id IS NOT NULL THEN
        INSERT INTO bi.dim_equipment (
            tenant_id,
            equipment_code,
            line_code,
            name,
            equipment_type,
            is_active
        )
        VALUES
            (v_tenant_id, 'EQ-501', 'LINE-A', '설비 501 (CNC)', 'machine', TRUE),
            (v_tenant_id, 'EQ-502', 'LINE-A', '설비 502 (Press)', 'machine', TRUE),
            (v_tenant_id, 'EQ-503', 'LINE-B', '설비 503 (Robot)', 'robot', TRUE),
            (v_tenant_id, 'EQ-504', 'LINE-B', '설비 504 (Conveyor)', 'conveyor', TRUE),
            (v_tenant_id, 'EQ-505', 'LINE-C', '설비 505 (Inspection)', 'inspection', TRUE)
        ON CONFLICT (tenant_id, equipment_code) DO NOTHING;

        RAISE NOTICE 'Created equipment data for tenant: %', v_tenant_id;
    END IF;
END $$;

SELECT COUNT(*) AS dim_equipment_count FROM bi.dim_equipment;
-- Expected: 5 rows

-- ============================================
-- 6. dim_kpi: KPI 정의 차원 (기본 KPI)
-- ============================================
-- 스펙: B-3-2 § 3.5

DO $$
DECLARE
    v_tenant_id uuid;
BEGIN
    SELECT tenant_id INTO v_tenant_id
    FROM core.tenants
    ORDER BY created_at
    LIMIT 1;

    IF v_tenant_id IS NOT NULL THEN
        INSERT INTO bi.dim_kpi (
            tenant_id,
            kpi_code,
            name,
            category,
            unit,
            aggregation_method,
            target_value,
            warning_threshold,
            critical_threshold
        )
        VALUES
            (v_tenant_id, 'defect_rate', '불량률', 'quality', '%', 'avg', 3.0, 5.0, 10.0),
            (v_tenant_id, 'oee', 'OEE (종합설비효율)', 'productivity', '%', 'avg', 85.0, 75.0, 65.0),
            (v_tenant_id, 'operation_rate', '가동률', 'productivity', '%', 'avg', 90.0, 80.0, 70.0),
            (v_tenant_id, 'production_qty', '생산량', 'production', 'EA', 'sum', 1000.0, 800.0, 600.0),
            (v_tenant_id, 'inventory_coverage', '재고 커버리지', 'inventory', 'days', 'avg', 30.0, 15.0, 7.0),
            (v_tenant_id, 'cycle_time', '사이클타임', 'productivity', 'sec', 'avg', 60.0, 80.0, 100.0),
            (v_tenant_id, 'downtime_hours', '비가동 시간', 'maintenance', 'hours', 'sum', 0.0, 4.0, 8.0),
            (v_tenant_id, 'yield_rate', '수율', 'quality', '%', 'avg', 97.0, 95.0, 90.0)
        ON CONFLICT (tenant_id, kpi_code) DO NOTHING;

        RAISE NOTICE 'Created KPI definitions for tenant: %', v_tenant_id;
    END IF;
END $$;

SELECT COUNT(*) AS dim_kpi_count FROM bi.dim_kpi;
-- Expected: 8 rows

-- ============================================
-- 7. 검증 쿼리
-- ============================================

SELECT 'dim_date' AS table_name, COUNT(*) AS row_count FROM bi.dim_date
UNION ALL
SELECT 'dim_shift', COUNT(*) FROM bi.dim_shift
UNION ALL
SELECT 'dim_line', COUNT(*) FROM bi.dim_line
UNION ALL
SELECT 'dim_product', COUNT(*) FROM bi.dim_product
UNION ALL
SELECT 'dim_equipment', COUNT(*) FROM bi.dim_equipment
UNION ALL
SELECT 'dim_kpi', COUNT(*) FROM bi.dim_kpi;

-- Expected output:
-- table_name    | row_count
-- --------------+-----------
-- dim_date      | 3650
-- dim_shift     | 3
-- dim_line      | 3
-- dim_product   | 5
-- dim_equipment | 5
-- dim_kpi       | 8

-- ============================================
-- 완료 메시지
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'BI Dimension Seed Data Creation Complete!';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'dim_date: 2020-2030 (10 years)';
    RAISE NOTICE 'dim_shift: 3 shifts (A/B/C)';
    RAISE NOTICE 'dim_line: 3 sample lines';
    RAISE NOTICE 'dim_product: 5 sample products';
    RAISE NOTICE 'dim_equipment: 5 sample equipment';
    RAISE NOTICE 'dim_kpi: 8 KPI definitions';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Next step: Generate sample FACT data';
    RAISE NOTICE 'Or use Mock API: POST /api/v1/erp-mes/mock/generate';
    RAISE NOTICE '============================================';
END $$;
