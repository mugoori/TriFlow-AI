-- =====================================================
-- Migration 024: StatCard Configuration Schema
-- 스펙 참조: DB 기반 동적 StatCard 시스템
--
-- 대시보드 StatCard 설정을 DB에 저장하여
-- 사용자별 지표 카드 커스터마이징 지원
--
-- 데이터 소스 유형:
--   - kpi: bi.dim_kpi에서 정의된 KPI
--   - db_query: 사용자 정의 테이블/컬럼 쿼리
--   - mcp_tool: MCP 도구를 통한 외부 시스템 연동
-- =====================================================

SET search_path TO bi, core, public;

-- =====================================================
-- 1. stat_card_configs (StatCard 설정)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.stat_card_configs (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(user_id) ON DELETE CASCADE,

    -- 표시 순서 및 가시성
    display_order INT NOT NULL DEFAULT 0,
    is_visible BOOLEAN NOT NULL DEFAULT true,

    -- 데이터 소스 유형
    source_type TEXT NOT NULL CHECK (source_type IN ('kpi', 'db_query', 'mcp_tool')),

    -- KPI 소스 (source_type = 'kpi')
    kpi_code TEXT,  -- bi.dim_kpi.kpi_code 참조

    -- DB Query 소스 (source_type = 'db_query')
    table_name TEXT,
    column_name TEXT,
    aggregation TEXT CHECK (aggregation IS NULL OR aggregation IN ('sum', 'avg', 'min', 'max', 'count', 'last')),
    filter_condition JSONB,  -- {"line_code": "L1", "shift": "day"} 등

    -- MCP Tool 소스 (source_type = 'mcp_tool')
    mcp_server_id UUID,  -- MCP 서버 ID (soft reference)
    mcp_tool_name TEXT,
    mcp_params JSONB,  -- 도구 호출 파라미터
    mcp_result_key TEXT,  -- 응답 JSON에서 추출할 키 (예: "data.total")

    -- 표시 설정 (커스텀 오버라이드)
    custom_title TEXT,
    custom_icon TEXT,
    custom_unit TEXT,

    -- 임계값 (DB Query, MCP용 - KPI는 dim_kpi에서 가져옴)
    green_threshold NUMERIC,
    yellow_threshold NUMERIC,
    red_threshold NUMERIC,
    higher_is_better BOOLEAN DEFAULT true,

    -- 캐시 설정
    cache_ttl_seconds INT DEFAULT 60,

    -- 메타데이터
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 제약조건: source_type별 필수 필드 검증
    CONSTRAINT chk_kpi_source CHECK (
        source_type != 'kpi' OR kpi_code IS NOT NULL
    ),
    CONSTRAINT chk_db_query_source CHECK (
        source_type != 'db_query' OR (table_name IS NOT NULL AND column_name IS NOT NULL AND aggregation IS NOT NULL)
    ),
    CONSTRAINT chk_mcp_tool_source CHECK (
        source_type != 'mcp_tool' OR (mcp_server_id IS NOT NULL AND mcp_tool_name IS NOT NULL)
    )
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_stat_card_configs_user ON bi.stat_card_configs (tenant_id, user_id, display_order);
CREATE INDEX IF NOT EXISTS idx_stat_card_configs_visible ON bi.stat_card_configs (tenant_id, user_id, is_visible) WHERE is_visible = true;
CREATE INDEX IF NOT EXISTS idx_stat_card_configs_source ON bi.stat_card_configs (source_type);

COMMENT ON TABLE bi.stat_card_configs IS '대시보드 StatCard 설정 (사용자별 커스터마이징)';
COMMENT ON COLUMN bi.stat_card_configs.source_type IS 'kpi: KPI 지표, db_query: DB 쿼리, mcp_tool: MCP 도구';
COMMENT ON COLUMN bi.stat_card_configs.kpi_code IS 'bi.dim_kpi.kpi_code 참조';
COMMENT ON COLUMN bi.stat_card_configs.filter_condition IS 'DB 쿼리 필터 조건 JSON';
COMMENT ON COLUMN bi.stat_card_configs.mcp_result_key IS 'MCP 응답에서 값을 추출할 경로 (예: data.total_count)';
COMMENT ON COLUMN bi.stat_card_configs.cache_ttl_seconds IS '값 캐시 TTL (초)';

-- =====================================================
-- 2. updated_at 트리거
-- =====================================================
DROP TRIGGER IF EXISTS trigger_stat_card_configs_updated_at ON bi.stat_card_configs;
CREATE TRIGGER trigger_stat_card_configs_updated_at
    BEFORE UPDATE ON bi.stat_card_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 3. 허용된 테이블/컬럼 목록 (DB Query 소스용)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.allowed_stat_card_tables (
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    schema_name TEXT NOT NULL DEFAULT 'bi',
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    description TEXT,
    allowed_aggregations TEXT[] DEFAULT ARRAY['sum', 'avg', 'min', 'max', 'count', 'last'],
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, schema_name, table_name, column_name)
);

CREATE INDEX IF NOT EXISTS idx_allowed_stat_card_tables_active ON bi.allowed_stat_card_tables (tenant_id, is_active) WHERE is_active = true;

COMMENT ON TABLE bi.allowed_stat_card_tables IS 'StatCard DB 쿼리에서 사용 가능한 테이블/컬럼 화이트리스트';
COMMENT ON COLUMN bi.allowed_stat_card_tables.allowed_aggregations IS '허용된 집계 함수 목록';

-- =====================================================
-- 4. 샘플 허용 테이블 데이터
-- =====================================================
INSERT INTO bi.allowed_stat_card_tables (tenant_id, schema_name, table_name, column_name, data_type, description, allowed_aggregations)
SELECT
    t.tenant_id,
    col.schema_name,
    col.table_name,
    col.column_name,
    col.data_type,
    col.description,
    col.aggregations
FROM core.tenants t
CROSS JOIN (VALUES
    -- fact_daily_production
    ('bi', 'fact_daily_production', 'production_count', 'numeric', '일일 생산량', ARRAY['sum', 'avg', 'max']),
    ('bi', 'fact_daily_production', 'good_count', 'numeric', '양품 수량', ARRAY['sum', 'avg', 'max']),
    ('bi', 'fact_daily_production', 'defect_count', 'numeric', '불량 수량', ARRAY['sum', 'avg', 'max']),
    ('bi', 'fact_daily_production', 'defect_rate', 'numeric', '불량률 (%)', ARRAY['avg', 'min', 'max', 'last']),
    ('bi', 'fact_daily_production', 'oee', 'numeric', 'OEE (%)', ARRAY['avg', 'min', 'max', 'last']),
    ('bi', 'fact_daily_production', 'availability', 'numeric', '가동률 (%)', ARRAY['avg', 'min', 'max', 'last']),
    ('bi', 'fact_daily_production', 'performance', 'numeric', '성능 효율 (%)', ARRAY['avg', 'min', 'max', 'last']),
    ('bi', 'fact_daily_production', 'quality', 'numeric', '품질률 (%)', ARRAY['avg', 'min', 'max', 'last']),
    ('bi', 'fact_daily_production', 'planned_downtime_min', 'numeric', '계획 비가동 시간 (분)', ARRAY['sum', 'avg']),
    ('bi', 'fact_daily_production', 'unplanned_downtime_min', 'numeric', '비계획 비가동 시간 (분)', ARRAY['sum', 'avg']),

    -- fact_hourly_production
    ('bi', 'fact_hourly_production', 'production_count', 'numeric', '시간별 생산량', ARRAY['sum', 'avg', 'max', 'last']),
    ('bi', 'fact_hourly_production', 'good_count', 'numeric', '시간별 양품 수량', ARRAY['sum', 'avg', 'max', 'last']),
    ('bi', 'fact_hourly_production', 'defect_count', 'numeric', '시간별 불량 수량', ARRAY['sum', 'avg', 'max', 'last']),

    -- sensor_data (if exists)
    ('core', 'sensor_data', 'value', 'numeric', '센서 측정값', ARRAY['avg', 'min', 'max', 'last'])
) AS col(schema_name, table_name, column_name, data_type, description, aggregations)
ON CONFLICT (tenant_id, schema_name, table_name, column_name) DO NOTHING;

-- =====================================================
-- 5. 기본 StatCard 설정 시드 (신규 사용자용)
-- =====================================================
-- 신규 사용자에게 기본 StatCard 4개를 자동 생성하는 함수
CREATE OR REPLACE FUNCTION bi.create_default_stat_cards(
    p_tenant_id UUID,
    p_user_id UUID
) RETURNS void AS $$
BEGIN
    -- 이미 StatCard가 있으면 스킵
    IF EXISTS (
        SELECT 1 FROM bi.stat_card_configs
        WHERE tenant_id = p_tenant_id AND user_id = p_user_id
    ) THEN
        RETURN;
    END IF;

    -- 기본 KPI 카드 4개 생성
    INSERT INTO bi.stat_card_configs (tenant_id, user_id, display_order, source_type, kpi_code, custom_icon)
    VALUES
        (p_tenant_id, p_user_id, 0, 'kpi', 'defect_rate', 'AlertTriangle'),
        (p_tenant_id, p_user_id, 1, 'kpi', 'oee', 'Activity'),
        (p_tenant_id, p_user_id, 2, 'kpi', 'yield_rate', 'TrendingUp'),
        (p_tenant_id, p_user_id, 3, 'kpi', 'downtime', 'Clock');
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION bi.create_default_stat_cards IS '신규 사용자에게 기본 StatCard 4개 생성';

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
