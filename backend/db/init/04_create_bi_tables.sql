-- ===================================
-- TriFlow AI - BI Schema 테이블
-- ===================================

SET search_path TO bi;

-- BI Dataset 정의
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sql_query TEXT NOT NULL,
    refresh_interval_seconds INTEGER DEFAULT 3600,
    last_refreshed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- BI Metric 정의
CREATE TABLE IF NOT EXISTS metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    aggregation_type VARCHAR(50) NOT NULL,  -- SUM, AVG, COUNT, MIN, MAX
    sql_expression TEXT NOT NULL,
    unit VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- Dashboard 정의
CREATE TABLE IF NOT EXISTS dashboards (
    dashboard_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    layout_config JSONB DEFAULT '[]',
    is_public BOOLEAN DEFAULT false,
    created_by UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- Dashboard Widget
CREATE TABLE IF NOT EXISTS widgets (
    widget_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dashboard_id UUID NOT NULL REFERENCES dashboards(dashboard_id) ON DELETE CASCADE,
    widget_type VARCHAR(50) NOT NULL,  -- LINE, BAR, PIE, TABLE, etc.
    config JSONB NOT NULL,
    position_x INTEGER NOT NULL,
    position_y INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BI Query 캐시
CREATE TABLE IF NOT EXISTS query_cache (
    cache_key VARCHAR(255) PRIMARY KEY,
    tenant_id UUID NOT NULL,
    query_sql TEXT NOT NULL,
    result_data JSONB NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- 인덱스
CREATE INDEX idx_datasets_tenant ON datasets(tenant_id);
CREATE INDEX idx_metrics_tenant ON metrics(tenant_id);
CREATE INDEX idx_dashboards_tenant ON dashboards(tenant_id, is_public);
CREATE INDEX idx_widgets_dashboard ON widgets(dashboard_id);
CREATE INDEX idx_query_cache_tenant_expires ON query_cache(tenant_id, expires_at);

-- 코멘트
COMMENT ON TABLE datasets IS 'BI 데이터셋 정의';
COMMENT ON TABLE metrics IS 'BI 메트릭 정의';
COMMENT ON TABLE dashboards IS '대시보드 구성';
COMMENT ON TABLE widgets IS '대시보드 위젯';
COMMENT ON TABLE query_cache IS 'BI 쿼리 결과 캐시';
