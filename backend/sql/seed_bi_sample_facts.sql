-- ============================================
-- BI FACT 테이블 샘플 데이터 생성
-- ============================================
-- 스펙 참조: B-3-2 § 4
-- 작성일: 2026-01-22
-- 용도: BI 분석 테스트용 샘플 데이터
--
-- 전제 조건: seed_bi_dimensions.sql 먼저 실행 필요
--
-- 실행 방법:
-- psql -U postgres -d triflow < backend/sql/seed_bi_sample_facts.sql
-- ============================================

-- ============================================
-- 1. fact_daily_production: 일일 생산 실적
-- ============================================
-- 최근 30일치 샘플 데이터 생성

DO $$
DECLARE
    v_tenant_id uuid;
    v_date date;
    v_line_code text;
    v_product_code text;
    v_shift_code text;
    v_base_qty numeric;
    v_defect_rate numeric;
    v_total_qty numeric;
    v_defect_qty numeric;
    v_good_qty numeric;
BEGIN
    -- tenant_id 조회
    SELECT tenant_id INTO v_tenant_id
    FROM core.tenants
    ORDER BY created_at
    LIMIT 1;

    IF v_tenant_id IS NULL THEN
        RAISE EXCEPTION 'No tenant found. Create tenant first.';
    END IF;

    -- 최근 30일 × 3개 라인 × 5개 제품 × 3교대 = 1,350개 레코드
    FOR v_date IN
        SELECT d::date
        FROM generate_series(CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE - INTERVAL '1 day', '1 day'::interval) d
    LOOP
        FOR v_line_code IN SELECT unnest(ARRAY['LINE-A', 'LINE-B', 'LINE-C'])
        LOOP
            FOR v_product_code IN SELECT unnest(ARRAY['PROD-X', 'PROD-Y', 'PROD-Z', 'PROD-W', 'PROD-V'])
            LOOP
                FOR v_shift_code IN SELECT unnest(ARRAY['A', 'B', 'C'])
                LOOP
                    -- 기본 생산량 (랜덤)
                    v_base_qty := 500 + floor(random() * 500)::numeric;

                    -- 현실적인 불량률 패턴
                    -- LINE-A + PROD-X 조합이 불량 높음 (문제 시나리오)
                    IF v_line_code = 'LINE-A' AND v_product_code = 'PROD-X' THEN
                        v_defect_rate := 0.07 + random() * 0.03;  -- 7-10% 불량
                    ELSIF v_shift_code = 'C' THEN  -- 야간 교대가 불량 높음
                        v_defect_rate := 0.04 + random() * 0.02;  -- 4-6% 불량
                    ELSE
                        v_defect_rate := 0.01 + random() * 0.02;  -- 1-3% 정상
                    END IF;

                    v_total_qty := v_base_qty;
                    v_defect_qty := floor(v_base_qty * v_defect_rate)::numeric;
                    v_good_qty := v_total_qty - v_defect_qty;

                    INSERT INTO bi.fact_daily_production (
                        tenant_id,
                        date,
                        line_code,
                        product_code,
                        shift,
                        total_qty,
                        good_qty,
                        defect_qty,
                        rework_qty,
                        scrap_qty,
                        cycle_time_avg,
                        runtime_minutes,
                        downtime_minutes,
                        setup_time_minutes,
                        planned_qty,
                        work_order_count
                    )
                    VALUES (
                        v_tenant_id,
                        v_date,
                        v_line_code,
                        v_product_code,
                        v_shift_code,
                        v_total_qty,
                        v_good_qty,
                        v_defect_qty,
                        floor(v_defect_qty * 0.3)::numeric,  -- 불량의 30%는 재작업
                        floor(v_defect_qty * 0.7)::numeric,  -- 불량의 70%는 폐기
                        50.0 + random() * 20.0,  -- 사이클타임 50-70초
                        400 + floor(random() * 60)::numeric,  -- 가동시간 400-460분
                        20 + floor(random() * 40)::numeric,   -- 비가동 20-60분
                        10 + floor(random() * 20)::numeric,   -- 셋업 10-30분
                        v_base_qty,  -- 계획 생산량
                        floor(1 + random() * 3)::int  -- 작업 오더 1-3개
                    )
                    ON CONFLICT (tenant_id, date, line_code, product_code, shift) DO NOTHING;

                END LOOP;
            END LOOP;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'Created 30 days of production data';
END $$;

SELECT COUNT(*) AS fact_daily_production_count FROM bi.fact_daily_production;
-- Expected: ~1,350 rows (30일 × 3라인 × 5제품 × 3교대)

-- ============================================
-- 2. fact_daily_defect: 일일 불량 상세
-- ============================================

DO $$
DECLARE
    v_tenant_id uuid;
    v_date date;
    v_line_code text;
    v_product_code text;
    v_shift_code text;
    v_defect_type text;
    v_total_defects numeric;
BEGIN
    SELECT tenant_id INTO v_tenant_id
    FROM core.tenants
    ORDER BY created_at
    LIMIT 1;

    -- 최근 30일 불량 상세
    FOR v_date IN
        SELECT d::date
        FROM generate_series(CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE - INTERVAL '1 day', '1 day') d
    LOOP
        FOR v_line_code IN SELECT unnest(ARRAY['LINE-A', 'LINE-B', 'LINE-C'])
        LOOP
            FOR v_product_code IN SELECT unnest(ARRAY['PROD-X', 'PROD-Y', 'PROD-Z'])
            LOOP
                FOR v_shift_code IN SELECT unnest(ARRAY['A', 'B', 'C'])
                LOOP
                    -- fact_daily_production에서 총 불량 조회
                    SELECT defect_qty INTO v_total_defects
                    FROM bi.fact_daily_production
                    WHERE tenant_id = v_tenant_id
                      AND date = v_date
                      AND line_code = v_line_code
                      AND product_code = v_product_code
                      AND shift = v_shift_code;

                    IF v_total_defects IS NOT NULL AND v_total_defects > 0 THEN
                        -- 불량을 유형별로 분배
                        FOR v_defect_type IN SELECT unnest(ARRAY['scratch', 'dimension', 'crack', 'contamination'])
                        LOOP
                            INSERT INTO bi.fact_daily_defect (
                                tenant_id,
                                date,
                                line_code,
                                product_code,
                                shift,
                                defect_type,
                                defect_qty,
                                defect_cost
                            )
                            VALUES (
                                v_tenant_id,
                                v_date,
                                v_line_code,
                                v_product_code,
                                v_shift_code,
                                v_defect_type,
                                floor(v_total_defects * (0.1 + random() * 0.3))::numeric,  -- 불량 유형별 분배
                                floor((v_total_defects * (0.1 + random() * 0.3)) * 10000)::numeric  -- 개당 10,000원 가정
                            )
                            ON CONFLICT DO NOTHING;
                        END LOOP;
                    END IF;

                END LOOP;
            END LOOP;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'Created defect detail data';
END $$;

SELECT COUNT(*) AS fact_daily_defect_count FROM bi.fact_daily_defect;

-- ============================================
-- 3. fact_inventory_snapshot: 재고 스냅샷
-- ============================================

DO $$
DECLARE
    v_tenant_id uuid;
    v_date date;
    v_product_code text;
BEGIN
    SELECT tenant_id INTO v_tenant_id FROM core.tenants ORDER BY created_at LIMIT 1;

    -- 최근 30일 일별 재고 스냅샷
    FOR v_date IN
        SELECT d::date FROM generate_series(CURRENT_DATE - 30, CURRENT_DATE - 1, '1 day') d
    LOOP
        FOR v_product_code IN SELECT unnest(ARRAY['PROD-X', 'PROD-Y', 'PROD-Z', 'PROD-W', 'PROD-V'])
        LOOP
            INSERT INTO bi.fact_inventory_snapshot (
                tenant_id,
                date,
                product_code,
                on_hand_qty,
                reserved_qty,
                available_qty,
                safety_stock_qty,
                reorder_point_qty,
                daily_usage_avg,
                lead_time_days,
                coverage_days
            )
            VALUES (
                v_tenant_id,
                v_date,
                v_product_code,
                floor(1000 + random() * 4000)::numeric,  -- 재고 1000-5000
                floor(100 + random() * 500)::numeric,    -- 예약 100-600
                floor(900 + random() * 3500)::numeric,   -- 가용 900-4400
                1000.0,  -- 안전재고
                1500.0,  -- 재주문점
                100.0,   -- 일평균 사용량
                7,       -- 리드타임 7일
                floor(10 + random() * 20)::numeric  -- 커버리지 10-30일
            )
            ON CONFLICT (tenant_id, date, product_code) DO NOTHING;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'Created inventory snapshot data';
END $$;

SELECT COUNT(*) AS fact_inventory_snapshot_count FROM bi.fact_inventory_snapshot;
-- Expected: 150 rows (30일 × 5제품)

-- ============================================
-- 4. fact_equipment_event: 설비 이벤트
-- ============================================

DO $$
DECLARE
    v_tenant_id uuid;
    v_date date;
    v_equipment_code text;
BEGIN
    SELECT tenant_id INTO v_tenant_id FROM core.tenants ORDER BY created_at LIMIT 1;

    -- 최근 30일 설비 이벤트 (비가동, 고장 등)
    FOR v_date IN
        SELECT d::date FROM generate_series(CURRENT_DATE - 30, CURRENT_DATE - 1, '1 day') d
    LOOP
        -- 각 설비별로 랜덤하게 이벤트 발생
        IF random() < 0.3 THEN  -- 30% 확률로 이벤트 발생
            v_equipment_code := (ARRAY['EQ-501', 'EQ-502', 'EQ-503', 'EQ-504', 'EQ-505'])[floor(random() * 5 + 1)::int];

            INSERT INTO bi.fact_equipment_event (
                tenant_id,
                date,
                equipment_code,
                event_type,
                event_subtype,
                duration_minutes,
                event_description
            )
            VALUES (
                v_tenant_id,
                v_date,
                v_equipment_code,
                (ARRAY['downtime', 'maintenance', 'setup', 'breakdown'])[floor(random() * 4 + 1)::int],
                (ARRAY['planned', 'unplanned'])[floor(random() * 2 + 1)::int],
                floor(10 + random() * 120)::numeric,  -- 10-130분
                'Sample event for testing'
            );
        END IF;
    END LOOP;

    RAISE NOTICE 'Created equipment event data';
END $$;

SELECT COUNT(*) AS fact_equipment_event_count FROM bi.fact_equipment_event;

-- ============================================
-- 검증 쿼리
-- ============================================

SELECT 'fact_daily_production' AS table_name, COUNT(*) AS row_count FROM bi.fact_daily_production
UNION ALL
SELECT 'fact_daily_defect', COUNT(*) FROM bi.fact_daily_defect
UNION ALL
SELECT 'fact_inventory_snapshot', COUNT(*) FROM bi.fact_inventory_snapshot
UNION ALL
SELECT 'fact_equipment_event', COUNT(*) FROM bi.fact_equipment_event;

-- ============================================
-- BI 쿼리 테스트
-- ============================================

-- 1. 최근 7일 불량률 추이 (라인별)
SELECT
    d.date,
    l.line_code,
    l.name AS line_name,
    SUM(f.total_qty) AS total_qty,
    SUM(f.defect_qty) AS defect_qty,
    CASE
        WHEN SUM(f.total_qty) > 0
        THEN ROUND((SUM(f.defect_qty)::numeric / SUM(f.total_qty) * 100), 2)
        ELSE 0
    END AS defect_rate_pct
FROM bi.fact_daily_production f
JOIN bi.dim_date d ON f.date = d.date
JOIN bi.dim_line l ON f.tenant_id = l.tenant_id AND f.line_code = l.line_code
WHERE d.date >= CURRENT_DATE - 7
  AND f.tenant_id = (SELECT tenant_id FROM core.tenants ORDER BY created_at LIMIT 1)
GROUP BY d.date, l.line_code, l.name
ORDER BY d.date, l.line_code;

-- 2. 제품별 불량률 TOP 5
SELECT
    p.product_code,
    p.name AS product_name,
    SUM(f.total_qty) AS total_qty,
    SUM(f.defect_qty) AS defect_qty,
    ROUND((SUM(f.defect_qty)::numeric / NULLIF(SUM(f.total_qty), 0) * 100), 2) AS defect_rate_pct
FROM bi.fact_daily_production f
JOIN bi.dim_product p ON f.tenant_id = p.tenant_id AND f.product_code = p.product_code
WHERE f.date >= CURRENT_DATE - 30
  AND f.tenant_id = (SELECT tenant_id FROM core.tenants ORDER BY created_at LIMIT 1)
GROUP BY p.product_code, p.name
ORDER BY defect_rate_pct DESC
LIMIT 5;

-- 3. 교대별 평균 불량률
SELECT
    s.shift_code,
    s.name AS shift_name,
    s.is_night_shift,
    COUNT(DISTINCT f.date) AS work_days,
    ROUND(AVG(f.defect_qty::numeric / NULLIF(f.total_qty, 0) * 100), 2) AS avg_defect_rate_pct
FROM bi.fact_daily_production f
JOIN bi.dim_shift s ON f.tenant_id = s.tenant_id AND f.shift = s.shift_code
WHERE f.date >= CURRENT_DATE - 30
  AND f.tenant_id = (SELECT tenant_id FROM core.tenants ORDER BY created_at LIMIT 1)
GROUP BY s.shift_code, s.name, s.is_night_shift, s.shift_order
ORDER BY s.shift_order;

-- ============================================
-- 완료 메시지
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'BI FACT Sample Data Creation Complete!';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'fact_daily_production: 30 days × 3 lines × 5 products × 3 shifts';
    RAISE NOTICE 'fact_daily_defect: Defect details by type';
    RAISE NOTICE 'fact_inventory_snapshot: 30 days × 5 products';
    RAISE NOTICE 'fact_equipment_event: Random equipment events';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Data pattern:';
    RAISE NOTICE '  - LINE-A + PROD-X has high defect rate (7-10%)';
    RAISE NOTICE '  - Night shift (C) has higher defects (4-6%)';
    RAISE NOTICE '  - Other combinations: normal (1-3%)';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Next: Test BI queries!';
    RAISE NOTICE 'Example: "Show me defect rate trend for last 7 days"';
    RAISE NOTICE '============================================';
END $$;
