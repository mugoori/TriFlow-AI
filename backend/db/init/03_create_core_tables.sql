-- ===================================
-- TriFlow AI - Core Schema 테이블
-- ===================================

SET search_path TO core, public;

-- 테넌트 (멀티테넌트 지원)
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 사용자
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'viewer',  -- admin, editor, viewer
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rule 세트
CREATE TABLE IF NOT EXISTS rulesets (
    ruleset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rhai_code TEXT NOT NULL,
    version VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT false,
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name, version)
);

-- Workflow 정의 (B-3-1 Core Schema 스펙 준수)
CREATE TABLE IF NOT EXISTS workflows (
    workflow_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    dsl_json JSONB NOT NULL,
    version VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT false,
    -- B-3-1 확장 컬럼
    dsl_digest VARCHAR(64),                     -- DSL JSON SHA256 해시 (변경 추적)
    trigger_config JSONB,                       -- 트리거 설정 (schedule, event, webhook)
    timeout_seconds INTEGER DEFAULT 300,        -- 워크플로우 타임아웃 (초)
    max_retry INTEGER DEFAULT 3,                -- 최대 재시도 횟수
    tags TEXT[] DEFAULT '{}',                   -- 태그 배열 (검색용)
    metadata JSONB DEFAULT '{}',                -- 추가 메타데이터
    activated_at TIMESTAMP,                     -- 활성화 시각
    -- 감사 컬럼
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name, version)
);

-- Judgment 실행 이력
CREATE TABLE IF NOT EXISTS judgment_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES workflows(workflow_id) ON DELETE SET NULL,
    input_data JSONB NOT NULL,
    output_data JSONB NOT NULL,
    method_used VARCHAR(50) NOT NULL,  -- RULE_ONLY, LLM_ONLY, HYBRID, etc.
    confidence FLOAT,
    execution_time_ms INTEGER,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 피드백 로그 (Learning System용)
CREATE TABLE IF NOT EXISTS feedback_logs (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    judgment_execution_id UUID REFERENCES judgment_executions(execution_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id),
    feedback_type VARCHAR(50) NOT NULL,  -- positive, negative, correction
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    corrected_result VARCHAR(20) CHECK (corrected_result IN ('normal', 'warning', 'critical')),
    original_output JSONB,
    corrected_output JSONB,
    context_data JSONB DEFAULT '{}',
    is_processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_feedback_type CHECK (
        feedback_type IN ('correct', 'incorrect', 'partial', 'helpful', 'not_helpful', 'positive', 'negative', 'correction')
    )
);

-- Workflow 실행 인스턴스
CREATE TABLE IF NOT EXISTS workflow_instances (
    instance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,  -- RUNNING, COMPLETED, FAILED, CANCELLED
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- 센서 데이터 (시계열)
CREATE TABLE IF NOT EXISTS sensor_data (
    sensor_id UUID DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    line_code VARCHAR(100) NOT NULL,
    sensor_type VARCHAR(100) NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sensor_id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- 센서 데이터 파티션 생성 (월별)
CREATE TABLE sensor_data_2025_11 PARTITION OF sensor_data
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE sensor_data_2025_12 PARTITION OF sensor_data
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 인덱스
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_rulesets_tenant_active ON rulesets(tenant_id, is_active);
CREATE INDEX idx_workflows_tenant_active ON workflows(tenant_id, is_active);
CREATE INDEX idx_workflows_tags ON workflows USING GIN (tags);
CREATE INDEX idx_workflows_dsl_digest ON workflows(dsl_digest);
CREATE INDEX idx_workflows_trigger_config ON workflows USING GIN (trigger_config);
CREATE INDEX idx_judgment_executions_tenant_workflow ON judgment_executions(tenant_id, workflow_id, executed_at DESC);
CREATE INDEX idx_workflow_instances_tenant_status ON workflow_instances(tenant_id, status, started_at DESC);
CREATE INDEX idx_sensor_data_line_type_time ON sensor_data(tenant_id, line_code, sensor_type, recorded_at DESC);
CREATE INDEX idx_feedback_logs_tenant ON feedback_logs(tenant_id, created_at DESC);
CREATE INDEX idx_feedback_logs_type ON feedback_logs(feedback_type, is_processed);

-- 코멘트
COMMENT ON TABLE tenants IS '멀티테넌트 관리';
COMMENT ON TABLE users IS '사용자 계정';
COMMENT ON TABLE rulesets IS 'Rhai 룰 엔진 코드';
COMMENT ON TABLE workflows IS 'Workflow DSL 정의';
COMMENT ON TABLE judgment_executions IS 'Judgment 실행 로그';
COMMENT ON TABLE feedback_logs IS '사용자 피드백 로그 (Learning System용)';
COMMENT ON TABLE workflow_instances IS 'Workflow 실행 인스턴스';
COMMENT ON TABLE sensor_data IS '센서 시계열 데이터 (파티션)';
