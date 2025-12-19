-- =====================================================
-- Migration 019: MCP ToolHub Schema
-- 스펙 참조: B-2-3_MCP_DataHub_Chat_Design.md
--
-- MCP ToolHub: 외부 MCP 서버 호출을 표준화하는 게이트웨이
--   - MCP 서버 레지스트리 관리
--   - 도구 메타데이터 저장
--   - 도구 호출 프록시 (인증, 타임아웃, 재시도)
--   - Circuit Breaker
--   - 커넥터 헬스 체크
--   - Drift 감지
-- =====================================================

SET search_path TO core, public;

-- =====================================================
-- 1. mcp_servers (MCP 서버 레지스트리)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.mcp_servers (
    server_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 서버 식별 정보
    name TEXT NOT NULL,
    description TEXT,
    base_url TEXT NOT NULL,

    -- 인증 설정
    auth_type TEXT NOT NULL CHECK (auth_type IN ('none', 'api_key', 'oauth2', 'basic')),
    api_key TEXT,  -- encrypted, auth_type='api_key'
    oauth_config JSONB,  -- auth_type='oauth2': {token_url, client_id, client_secret, scope}
    basic_auth_config JSONB,  -- auth_type='basic': {username, password}

    -- 연결 설정
    timeout_ms INT NOT NULL DEFAULT 30000 CHECK (timeout_ms > 0 AND timeout_ms <= 300000),
    retry_count INT NOT NULL DEFAULT 3 CHECK (retry_count >= 0 AND retry_count <= 10),
    retry_delay_ms INT NOT NULL DEFAULT 1000,

    -- 상태
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error')),
    last_health_check TIMESTAMPTZ,
    last_health_status TEXT CHECK (last_health_status IN ('healthy', 'unhealthy', 'unknown')),
    health_check_error TEXT,

    -- 메타데이터
    tags TEXT[] DEFAULT '{}',
    attributes JSONB NOT NULL DEFAULT '{}',

    -- 감사
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,

    CONSTRAINT uq_mcp_server_name_tenant UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_tenant ON core.mcp_servers (tenant_id);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_status ON core.mcp_servers (tenant_id, status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_mcp_servers_tags ON core.mcp_servers USING GIN (tags);

COMMENT ON TABLE core.mcp_servers IS 'MCP 서버 레지스트리 (외부 도구 서버 관리)';
COMMENT ON COLUMN core.mcp_servers.auth_type IS '인증 타입: none, api_key, oauth2, basic';
COMMENT ON COLUMN core.mcp_servers.oauth_config IS 'OAuth2 설정: {token_url, client_id, client_secret, scope}';
COMMENT ON COLUMN core.mcp_servers.timeout_ms IS '요청 타임아웃 (ms), 최대 300초';

-- =====================================================
-- 2. mcp_tools (MCP 도구 메타데이터)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.mcp_tools (
    tool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id UUID NOT NULL REFERENCES core.mcp_servers(server_id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 도구 정보
    name TEXT NOT NULL,
    description TEXT,
    method TEXT NOT NULL,  -- JSON-RPC method 이름

    -- 스키마
    input_schema JSONB NOT NULL DEFAULT '{}',  -- JSON Schema for input parameters
    output_schema JSONB NOT NULL DEFAULT '{}',  -- JSON Schema for output

    -- 사용 통계
    call_count BIGINT NOT NULL DEFAULT 0,
    success_count BIGINT NOT NULL DEFAULT 0,
    failure_count BIGINT NOT NULL DEFAULT 0,
    avg_latency_ms NUMERIC,
    last_called_at TIMESTAMPTZ,

    -- 상태
    is_enabled BOOLEAN NOT NULL DEFAULT true,

    -- 메타데이터
    tags TEXT[] DEFAULT '{}',
    attributes JSONB NOT NULL DEFAULT '{}',

    -- 감사
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_mcp_tool_name_server UNIQUE (server_id, name)
);

CREATE INDEX IF NOT EXISTS idx_mcp_tools_server ON core.mcp_tools (server_id);
CREATE INDEX IF NOT EXISTS idx_mcp_tools_tenant ON core.mcp_tools (tenant_id);
CREATE INDEX IF NOT EXISTS idx_mcp_tools_enabled ON core.mcp_tools (server_id, is_enabled) WHERE is_enabled = true;
CREATE INDEX IF NOT EXISTS idx_mcp_tools_tags ON core.mcp_tools USING GIN (tags);

COMMENT ON TABLE core.mcp_tools IS 'MCP 도구 메타데이터';
COMMENT ON COLUMN core.mcp_tools.method IS 'JSON-RPC 2.0 method 이름 (예: tools/read_file)';
COMMENT ON COLUMN core.mcp_tools.input_schema IS '입력 파라미터 JSON Schema';

-- =====================================================
-- 3. mcp_call_logs (도구 호출 로그) - 파티션 테이블
-- =====================================================
CREATE TABLE IF NOT EXISTS core.mcp_call_logs (
    log_id UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    server_id UUID NOT NULL,
    tool_id UUID,

    -- 호출 정보
    tool_name TEXT NOT NULL,
    request_id TEXT NOT NULL,  -- JSON-RPC request id

    -- 요청/응답
    request_payload JSONB NOT NULL,
    response_payload JSONB,

    -- 결과
    status TEXT NOT NULL CHECK (status IN ('success', 'failure', 'timeout', 'circuit_open')),
    error_message TEXT,
    error_code TEXT,

    -- 성능
    latency_ms INT,
    retry_count INT NOT NULL DEFAULT 0,

    -- 컨텍스트
    called_by UUID,  -- user_id
    correlation_id TEXT,  -- 연관 요청 추적

    -- 시간
    called_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (called_at, log_id)
) PARTITION BY RANGE (called_at);

-- 파티션 생성 (2025년 1월 ~ 12월)
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_01 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_02 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_03 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_04 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_05 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_06 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_07 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_08 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_09 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_10 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_11 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2025_12 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 2026년 파티션 (추가)
CREATE TABLE IF NOT EXISTS core.mcp_call_logs_2026_01 PARTITION OF core.mcp_call_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE INDEX IF NOT EXISTS idx_mcp_call_logs_tenant ON core.mcp_call_logs (tenant_id, called_at DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_call_logs_server ON core.mcp_call_logs (server_id, called_at DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_call_logs_status ON core.mcp_call_logs (status, called_at DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_call_logs_correlation ON core.mcp_call_logs (correlation_id) WHERE correlation_id IS NOT NULL;

COMMENT ON TABLE core.mcp_call_logs IS 'MCP 도구 호출 로그 (월별 파티션)';
COMMENT ON COLUMN core.mcp_call_logs.correlation_id IS '연관 요청 추적용 ID (Workflow 실행 등)';

-- =====================================================
-- 4. circuit_breaker_states (Circuit Breaker 상태)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.circuit_breaker_states (
    server_id UUID PRIMARY KEY REFERENCES core.mcp_servers(server_id) ON DELETE CASCADE,

    -- 상태
    state TEXT NOT NULL DEFAULT 'CLOSED' CHECK (state IN ('CLOSED', 'OPEN', 'HALF_OPEN')),

    -- 카운터
    failure_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    consecutive_failures INT NOT NULL DEFAULT 0,
    consecutive_successes INT NOT NULL DEFAULT 0,

    -- 설정
    failure_threshold INT NOT NULL DEFAULT 5,
    success_threshold INT NOT NULL DEFAULT 2,
    timeout_seconds INT NOT NULL DEFAULT 60,

    -- 타임스탬프
    last_failure_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,  -- OPEN 상태 진입 시간
    half_opened_at TIMESTAMPTZ,  -- HALF_OPEN 상태 진입 시간

    -- 감사
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE core.circuit_breaker_states IS 'MCP 서버별 Circuit Breaker 상태';
COMMENT ON COLUMN core.circuit_breaker_states.state IS 'CLOSED(정상), OPEN(차단), HALF_OPEN(테스트)';
COMMENT ON COLUMN core.circuit_breaker_states.failure_threshold IS 'OPEN 전환 실패 임계값';
COMMENT ON COLUMN core.circuit_breaker_states.success_threshold IS 'CLOSED 전환 성공 임계값';

-- =====================================================
-- 5. data_connectors (외부 데이터 소스 커넥터)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.data_connectors (
    connector_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 커넥터 정보
    name TEXT NOT NULL,
    description TEXT,
    connector_type TEXT NOT NULL CHECK (connector_type IN ('postgresql', 'mysql', 'mssql', 'oracle', 'rest_api', 'mqtt', 's3', 'gcs')),

    -- 연결 설정 (암호화 권장)
    connection_config JSONB NOT NULL,  -- 타입별 설정
    -- postgresql: {host, port, database, username, password, ssl_mode}
    -- mysql: {host, port, database, username, password, ssl}
    -- rest_api: {base_url, auth_type, api_key, oauth_config}
    -- mqtt: {broker_url, username, password, client_id, topics}
    -- s3: {bucket, region, access_key, secret_key, prefix}

    -- 상태
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error')),
    last_connection_test TIMESTAMPTZ,
    last_connection_status TEXT CHECK (last_connection_status IN ('success', 'failure')),
    connection_error TEXT,

    -- 메타데이터
    tags TEXT[] DEFAULT '{}',
    attributes JSONB NOT NULL DEFAULT '{}',

    -- 감사
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,

    CONSTRAINT uq_data_connector_name_tenant UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_data_connectors_tenant ON core.data_connectors (tenant_id);
CREATE INDEX IF NOT EXISTS idx_data_connectors_type ON core.data_connectors (connector_type);
CREATE INDEX IF NOT EXISTS idx_data_connectors_status ON core.data_connectors (tenant_id, status) WHERE status = 'active';

COMMENT ON TABLE core.data_connectors IS '외부 데이터 소스 커넥터 관리';
COMMENT ON COLUMN core.data_connectors.connector_type IS 'DB: postgresql, mysql, mssql, oracle / API: rest_api / 메시징: mqtt / 스토리지: s3, gcs';

-- =====================================================
-- 6. schema_snapshots (스키마 스냅샷)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.schema_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id UUID NOT NULL REFERENCES core.data_connectors(connector_id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 스키마 정보
    schema_data JSONB NOT NULL,  -- {table_name: {columns: [{column_name, data_type, is_nullable, ...}]}}
    schema_hash TEXT NOT NULL,  -- SHA256 hash for quick comparison

    -- 메타데이터
    table_count INT NOT NULL DEFAULT 0,
    column_count INT NOT NULL DEFAULT 0,

    -- 감사
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    captured_by UUID
);

CREATE INDEX IF NOT EXISTS idx_schema_snapshots_connector ON core.schema_snapshots (connector_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_schema_snapshots_hash ON core.schema_snapshots (connector_id, schema_hash);

COMMENT ON TABLE core.schema_snapshots IS '외부 데이터 소스 스키마 스냅샷';
COMMENT ON COLUMN core.schema_snapshots.schema_data IS '테이블별 컬럼 정보 JSON';

-- =====================================================
-- 7. schema_drift_detections (스키마 변경 감지)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.schema_drift_detections (
    detection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id UUID NOT NULL REFERENCES core.data_connectors(connector_id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 비교 대상
    old_snapshot_id UUID REFERENCES core.schema_snapshots(snapshot_id) ON DELETE SET NULL,
    new_snapshot_id UUID REFERENCES core.schema_snapshots(snapshot_id) ON DELETE SET NULL,

    -- 변경 내용
    changes JSONB NOT NULL,  -- [{type, table_name, column_name, old_value, new_value}]
    change_count INT NOT NULL DEFAULT 0,

    -- 변경 유형별 카운트
    tables_added INT NOT NULL DEFAULT 0,
    tables_deleted INT NOT NULL DEFAULT 0,
    columns_added INT NOT NULL DEFAULT 0,
    columns_deleted INT NOT NULL DEFAULT 0,
    types_changed INT NOT NULL DEFAULT 0,

    -- 상태
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    is_acknowledged BOOLEAN NOT NULL DEFAULT false,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID,

    -- 알림
    alert_sent BOOLEAN NOT NULL DEFAULT false,
    alert_sent_at TIMESTAMPTZ,

    -- 감사
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_schema_drift_connector ON core.schema_drift_detections (connector_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_schema_drift_severity ON core.schema_drift_detections (severity, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_schema_drift_unack ON core.schema_drift_detections (connector_id, is_acknowledged) WHERE NOT is_acknowledged;

COMMENT ON TABLE core.schema_drift_detections IS '스키마 변경 감지 기록';
COMMENT ON COLUMN core.schema_drift_detections.changes IS '변경 목록: [{type: table_deleted|column_added|type_changed, ...}]';

-- =====================================================
-- 8. updated_at 트리거
-- =====================================================
DROP TRIGGER IF EXISTS trigger_mcp_servers_updated_at ON core.mcp_servers;
CREATE TRIGGER trigger_mcp_servers_updated_at
    BEFORE UPDATE ON core.mcp_servers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_mcp_tools_updated_at ON core.mcp_tools;
CREATE TRIGGER trigger_mcp_tools_updated_at
    BEFORE UPDATE ON core.mcp_tools
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_circuit_breaker_updated_at ON core.circuit_breaker_states;
CREATE TRIGGER trigger_circuit_breaker_updated_at
    BEFORE UPDATE ON core.circuit_breaker_states
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_data_connectors_updated_at ON core.data_connectors;
CREATE TRIGGER trigger_data_connectors_updated_at
    BEFORE UPDATE ON core.data_connectors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 9. Circuit Breaker 상태 전이 함수
-- =====================================================
CREATE OR REPLACE FUNCTION update_circuit_breaker_on_success(p_server_id UUID)
RETURNS void AS $$
DECLARE
    v_state TEXT;
    v_consecutive_successes INT;
    v_success_threshold INT;
BEGIN
    -- 현재 상태 조회
    SELECT state, consecutive_successes, success_threshold
    INTO v_state, v_consecutive_successes, v_success_threshold
    FROM core.circuit_breaker_states
    WHERE server_id = p_server_id
    FOR UPDATE;

    IF NOT FOUND THEN
        -- 레코드가 없으면 생성
        INSERT INTO core.circuit_breaker_states (server_id, state, success_count, consecutive_successes, last_success_at)
        VALUES (p_server_id, 'CLOSED', 1, 1, now());
        RETURN;
    END IF;

    -- 상태별 처리
    IF v_state = 'CLOSED' THEN
        -- CLOSED: 성공 카운트 증가, 연속 실패 리셋
        UPDATE core.circuit_breaker_states
        SET success_count = success_count + 1,
            consecutive_successes = consecutive_successes + 1,
            consecutive_failures = 0,
            last_success_at = now()
        WHERE server_id = p_server_id;

    ELSIF v_state = 'HALF_OPEN' THEN
        -- HALF_OPEN: 성공 임계값 도달 시 CLOSED로 전환
        IF v_consecutive_successes + 1 >= v_success_threshold THEN
            UPDATE core.circuit_breaker_states
            SET state = 'CLOSED',
                success_count = success_count + 1,
                consecutive_successes = 0,
                consecutive_failures = 0,
                last_success_at = now()
            WHERE server_id = p_server_id;
        ELSE
            UPDATE core.circuit_breaker_states
            SET success_count = success_count + 1,
                consecutive_successes = consecutive_successes + 1,
                last_success_at = now()
            WHERE server_id = p_server_id;
        END IF;

    ELSIF v_state = 'OPEN' THEN
        -- OPEN: 무시 (타임아웃 후 HALF_OPEN 전환 시점에 호출)
        NULL;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_circuit_breaker_on_failure(p_server_id UUID)
RETURNS void AS $$
DECLARE
    v_state TEXT;
    v_consecutive_failures INT;
    v_failure_threshold INT;
BEGIN
    -- 현재 상태 조회
    SELECT state, consecutive_failures, failure_threshold
    INTO v_state, v_consecutive_failures, v_failure_threshold
    FROM core.circuit_breaker_states
    WHERE server_id = p_server_id
    FOR UPDATE;

    IF NOT FOUND THEN
        -- 레코드가 없으면 생성
        INSERT INTO core.circuit_breaker_states (server_id, state, failure_count, consecutive_failures, last_failure_at)
        VALUES (p_server_id, 'CLOSED', 1, 1, now());
        RETURN;
    END IF;

    -- 상태별 처리
    IF v_state = 'CLOSED' THEN
        -- CLOSED: 실패 임계값 도달 시 OPEN으로 전환
        IF v_consecutive_failures + 1 >= v_failure_threshold THEN
            UPDATE core.circuit_breaker_states
            SET state = 'OPEN',
                failure_count = failure_count + 1,
                consecutive_failures = consecutive_failures + 1,
                consecutive_successes = 0,
                last_failure_at = now(),
                opened_at = now()
            WHERE server_id = p_server_id;
        ELSE
            UPDATE core.circuit_breaker_states
            SET failure_count = failure_count + 1,
                consecutive_failures = consecutive_failures + 1,
                consecutive_successes = 0,
                last_failure_at = now()
            WHERE server_id = p_server_id;
        END IF;

    ELSIF v_state = 'HALF_OPEN' THEN
        -- HALF_OPEN: 실패 시 즉시 OPEN으로 전환
        UPDATE core.circuit_breaker_states
        SET state = 'OPEN',
            failure_count = failure_count + 1,
            consecutive_failures = 1,
            consecutive_successes = 0,
            last_failure_at = now(),
            opened_at = now()
        WHERE server_id = p_server_id;

    ELSIF v_state = 'OPEN' THEN
        -- OPEN: 실패 카운트만 증가
        UPDATE core.circuit_breaker_states
        SET failure_count = failure_count + 1,
            last_failure_at = now()
        WHERE server_id = p_server_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- HALF_OPEN 전환 함수 (타임아웃 후 호출)
CREATE OR REPLACE FUNCTION try_half_open_circuit_breaker(p_server_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_state TEXT;
    v_opened_at TIMESTAMPTZ;
    v_timeout_seconds INT;
BEGIN
    SELECT state, opened_at, timeout_seconds
    INTO v_state, v_opened_at, v_timeout_seconds
    FROM core.circuit_breaker_states
    WHERE server_id = p_server_id
    FOR UPDATE;

    IF NOT FOUND OR v_state != 'OPEN' THEN
        RETURN FALSE;
    END IF;

    -- 타임아웃 경과 확인
    IF v_opened_at + (v_timeout_seconds || ' seconds')::INTERVAL <= now() THEN
        UPDATE core.circuit_breaker_states
        SET state = 'HALF_OPEN',
            consecutive_successes = 0,
            half_opened_at = now()
        WHERE server_id = p_server_id;
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_circuit_breaker_on_success IS '성공 시 Circuit Breaker 상태 업데이트';
COMMENT ON FUNCTION update_circuit_breaker_on_failure IS '실패 시 Circuit Breaker 상태 업데이트';
COMMENT ON FUNCTION try_half_open_circuit_breaker IS 'OPEN 상태에서 타임아웃 후 HALF_OPEN 전환 시도';

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
