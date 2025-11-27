-- ===================================
-- TriFlow AI - 샘플 센서 데이터 생성
-- 테스트 및 데모용 데이터
-- ===================================

SET search_path TO core, public;

-- 기존 tenant 확인 (없으면 생성)
DO $$
DECLARE
    v_tenant_id UUID;
BEGIN
    -- 기존 tenant 조회
    SELECT tenant_id INTO v_tenant_id FROM tenants WHERE slug = 'demo' LIMIT 1;

    -- tenant가 없으면 생성
    IF v_tenant_id IS NULL THEN
        INSERT INTO tenants (tenant_id, name, slug, settings)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Tenant', 'demo', '{"plan": "enterprise"}')
        ON CONFLICT (slug) DO NOTHING;

        v_tenant_id := '00000000-0000-0000-0000-000000000001';
        RAISE NOTICE 'Created demo tenant: %', v_tenant_id;
    ELSE
        RAISE NOTICE 'Using existing tenant: %', v_tenant_id;
    END IF;
END $$;

-- 샘플 센서 데이터 생성 (최근 7일간, 1시간 간격)
-- LINE_A, LINE_B, LINE_C, LINE_D 각각에 대해
-- temperature, pressure, humidity, vibration, flow_rate 센서 데이터

DO $$
DECLARE
    v_tenant_id UUID := '00000000-0000-0000-0000-000000000001';
    v_lines TEXT[] := ARRAY['LINE_A', 'LINE_B', 'LINE_C', 'LINE_D'];
    v_sensor_types TEXT[] := ARRAY['temperature', 'pressure', 'humidity', 'vibration', 'flow_rate'];
    v_units TEXT[] := ARRAY['°C', 'bar', '%', 'mm/s', 'L/min'];
    v_min_values FLOAT[] := ARRAY[20.0, 1.0, 30.0, 0.0, 10.0];
    v_max_values FLOAT[] := ARRAY[80.0, 10.0, 90.0, 5.0, 100.0];
    v_line TEXT;
    v_sensor_type TEXT;
    v_unit TEXT;
    v_min_val FLOAT;
    v_max_val FLOAT;
    v_timestamp TIMESTAMP;
    v_value FLOAT;
    v_count INT := 0;
    i INT;
    j INT;
    h INT;
BEGIN
    -- 기존 데이터 삭제 (선택적)
    -- DELETE FROM sensor_data WHERE tenant_id = v_tenant_id;

    -- 최근 7일간 데이터 생성 (1시간 간격 = 168개 시점)
    FOR h IN 0..167 LOOP
        v_timestamp := NOW() - (h || ' hours')::INTERVAL;

        -- 각 라인에 대해
        FOR i IN 1..array_length(v_lines, 1) LOOP
            v_line := v_lines[i];

            -- 각 센서 타입에 대해
            FOR j IN 1..array_length(v_sensor_types, 1) LOOP
                v_sensor_type := v_sensor_types[j];
                v_unit := v_units[j];
                v_min_val := v_min_values[j];
                v_max_val := v_max_values[j];

                -- 랜덤 값 생성 (정규 분포에 가깝게)
                v_value := v_min_val + (v_max_val - v_min_val) * (
                    0.5 + 0.3 * (random() - 0.5) + 0.1 * sin(h::FLOAT / 24 * 3.14159)
                );

                -- 값 범위 제한
                v_value := GREATEST(v_min_val, LEAST(v_max_val, v_value));
                v_value := ROUND(v_value::NUMERIC, 2);

                -- 데이터 삽입
                INSERT INTO sensor_data (
                    tenant_id,
                    line_code,
                    sensor_type,
                    value,
                    unit,
                    metadata,
                    recorded_at
                ) VALUES (
                    v_tenant_id,
                    v_line,
                    v_sensor_type,
                    v_value,
                    v_unit,
                    jsonb_build_object(
                        'source', 'sample_data',
                        'line', v_line,
                        'batch', 'BATCH_' || LPAD((h / 24 + 1)::TEXT, 3, '0')
                    ),
                    v_timestamp
                );

                v_count := v_count + 1;
            END LOOP;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'Inserted % sensor data records', v_count;
END $$;

-- 통계 확인
SELECT
    line_code,
    sensor_type,
    COUNT(*) as count,
    ROUND(AVG(value)::NUMERIC, 2) as avg_value,
    ROUND(MIN(value)::NUMERIC, 2) as min_value,
    ROUND(MAX(value)::NUMERIC, 2) as max_value,
    MIN(recorded_at) as oldest,
    MAX(recorded_at) as newest
FROM core.sensor_data
GROUP BY line_code, sensor_type
ORDER BY line_code, sensor_type;
