-- ===================================
-- TriFlow AI - Audit Schema 테이블
-- ===================================

SET search_path TO audit, public;

-- 감사 로그
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id UUID DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    user_id UUID,
    action VARCHAR(100) NOT NULL,  -- CREATE, UPDATE, DELETE, EXECUTE, etc.
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    old_value JSONB,
    new_value JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (log_id, created_at)
) PARTITION BY RANGE (created_at);

-- 감사 로그 파티션 (월별)
CREATE TABLE audit_logs_2025_11 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE audit_logs_2025_12 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 피드백 로그
CREATE TABLE IF NOT EXISTS feedback_logs (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    execution_id UUID NOT NULL,  -- judgment_executions.execution_id
    user_id UUID,
    feedback_type VARCHAR(50) NOT NULL,  -- THUMBS_UP, THUMBS_DOWN, CORRECTION
    expected_output JSONB,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LLM 호출 로그
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id UUID DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost DECIMAL(10, 6),
    latency_ms INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (call_id, created_at)
) PARTITION BY RANGE (created_at);

-- LLM 호출 로그 파티션 (월별)
CREATE TABLE llm_calls_2025_11 PARTITION OF llm_calls
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE llm_calls_2025_12 PARTITION OF llm_calls
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 배포 이력
CREATE TABLE IF NOT EXISTS deployment_history (
    deployment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    resource_type VARCHAR(50) NOT NULL,  -- RULESET, WORKFLOW, PROMPT
    resource_id UUID NOT NULL,
    version VARCHAR(50) NOT NULL,
    deployment_type VARCHAR(50) NOT NULL,  -- CANARY, BLUE_GREEN, ROLLING
    traffic_percentage INTEGER,
    status VARCHAR(50) NOT NULL,  -- PENDING, ACTIVE, ROLLED_BACK
    deployed_by UUID,
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rolled_back_at TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_audit_logs_tenant_action ON audit_logs(tenant_id, action, created_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_feedback_logs_tenant_execution ON feedback_logs(tenant_id, execution_id);
CREATE INDEX idx_feedback_logs_type ON feedback_logs(feedback_type, created_at DESC);
CREATE INDEX idx_llm_calls_tenant_model ON llm_calls(tenant_id, model, created_at DESC);
CREATE INDEX idx_deployment_history_tenant ON deployment_history(tenant_id, deployed_at DESC);

-- 코멘트
COMMENT ON TABLE audit_logs IS '감사 로그 (파티션)';
COMMENT ON TABLE feedback_logs IS '사용자 피드백';
COMMENT ON TABLE llm_calls IS 'LLM API 호출 로그 (파티션)';
COMMENT ON TABLE deployment_history IS '배포 이력';
