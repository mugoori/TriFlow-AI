-- =====================================================
-- Migration 011: Core Schema Extension
-- 스펙 참조: B-3-1_Core_Schema.md
--
-- 현재 구현된 테이블에 누락된 필드/테이블 추가
-- =====================================================

-- =====================================================
-- 1. workflow_steps (워크플로우 단계)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.workflow_steps (
    step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES core.workflows(workflow_id) ON DELETE CASCADE,
    step_order INT NOT NULL,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (node_type IN (
        'DATA', 'BI', 'JUDGMENT', 'MCP', 'ACTION', 'APPROVAL', 'WAIT',
        'SWITCH', 'PARALLEL', 'COMPENSATION', 'DEPLOY', 'ROLLBACK', 'SIMULATE'
    )),
    config JSONB NOT NULL,
    timeout_seconds INT NOT NULL DEFAULT 60,
    retry_policy JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workflow_id, node_id),
    UNIQUE (workflow_id, step_order)
);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_workflow ON core.workflow_steps (workflow_id, step_order);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_type ON core.workflow_steps (node_type);

COMMENT ON TABLE core.workflow_steps IS '워크플로우 단계 정규화 (B-5 13가지 노드 타입)';

-- =====================================================
-- 2. workflow_instances 확장 (기존 테이블에 필드 추가)
-- =====================================================
-- 새 필드 추가
ALTER TABLE core.workflow_instances
    ADD COLUMN IF NOT EXISTS trigger_type TEXT DEFAULT 'manual' CHECK (trigger_type IN ('manual', 'schedule', 'event', 'webhook', 'api')),
    ADD COLUMN IF NOT EXISTS triggered_by UUID REFERENCES core.users(user_id),
    ADD COLUMN IF NOT EXISTS runtime_context JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS checkpoint_data JSONB,
    ADD COLUMN IF NOT EXISTS current_step_id UUID,
    ADD COLUMN IF NOT EXISTS last_error TEXT,
    ADD COLUMN IF NOT EXISTS error_code TEXT,
    ADD COLUMN IF NOT EXISTS retry_count INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS duration_ms INT,
    ADD COLUMN IF NOT EXISTS trace_id TEXT,
    ADD COLUMN IF NOT EXISTS parent_instance_id UUID REFERENCES core.workflow_instances(instance_id),
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- status 제약 업데이트 (새 상태 추가)
-- Note: ALTER CHECK CONSTRAINT는 PostgreSQL에서 직접 지원하지 않으므로 새 제약 추가
ALTER TABLE core.workflow_instances DROP CONSTRAINT IF EXISTS workflow_instances_status_check;
ALTER TABLE core.workflow_instances ADD CONSTRAINT workflow_instances_status_check
    CHECK (status IN ('pending', 'running', 'waiting', 'paused', 'completed', 'failed', 'cancelled', 'timeout'));

-- 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_workflow_instances_tenant_status ON core.workflow_instances (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_status ON core.workflow_instances (status) WHERE status IN ('running', 'waiting', 'paused');
CREATE INDEX IF NOT EXISTS idx_workflow_instances_trace ON core.workflow_instances (trace_id) WHERE trace_id IS NOT NULL;

COMMENT ON COLUMN core.workflow_instances.checkpoint_data IS '장기 실행 워크플로우 체크포인트 (B-5 참조)';

-- =====================================================
-- 3. workflow_execution_logs (워크플로우 실행 로그)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.workflow_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID NOT NULL REFERENCES core.workflow_instances(instance_id) ON DELETE CASCADE,
    step_id UUID REFERENCES core.workflow_steps(step_id),
    node_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED', 'RETRYING')),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    error_code TEXT,
    retry_attempt INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    duration_ms INT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_wf_exec_logs_instance ON core.workflow_execution_logs (instance_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_wf_exec_logs_step ON core.workflow_execution_logs (step_id);
CREATE INDEX IF NOT EXISTS idx_wf_exec_logs_status ON core.workflow_execution_logs (status) WHERE status IN ('RUNNING', 'RETRYING');

COMMENT ON TABLE core.workflow_execution_logs IS '워크플로우 단계별 실행 로그';

-- =====================================================
-- 4. judgment_executions 확장
-- =====================================================
ALTER TABLE core.judgment_executions
    ADD COLUMN IF NOT EXISTS workflow_instance_id UUID REFERENCES core.workflow_instances(instance_id),
    ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'api' CHECK (source IN ('workflow', 'api', 'manual', 'schedule')),
    ADD COLUMN IF NOT EXISTS result TEXT DEFAULT 'unknown' CHECK (result IN ('normal', 'warning', 'critical', 'unknown')),
    ADD COLUMN IF NOT EXISTS explanation TEXT,
    ADD COLUMN IF NOT EXISTS recommended_actions JSONB,
    ADD COLUMN IF NOT EXISTS rule_trace JSONB,
    ADD COLUMN IF NOT EXISTS llm_metadata JSONB,
    ADD COLUMN IF NOT EXISTS evidence JSONB,
    ADD COLUMN IF NOT EXISTS feature_importance JSONB,
    ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS cache_key TEXT,
    ADD COLUMN IF NOT EXISTS latency_ms INT,
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES core.users(user_id),
    ADD COLUMN IF NOT EXISTS trace_id TEXT,
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_judgment_exec_result ON core.judgment_executions (tenant_id, result, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_judgment_exec_trace ON core.judgment_executions (trace_id) WHERE trace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_judgment_exec_cache_key ON core.judgment_executions (cache_key) WHERE cache_hit = true;

COMMENT ON COLUMN core.judgment_executions.method_used IS 'rule_only: 룰만, llm_only: LLM만, hybrid: 룰+LLM, cache: 캐시 히트';
COMMENT ON COLUMN core.judgment_executions.evidence IS 'JSON: {data_refs[], urls[], charts[]}';

-- =====================================================
-- 5. judgment_cache (판단 캐시)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.judgment_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    cache_key TEXT NOT NULL,
    judgment_execution_id UUID NOT NULL REFERENCES core.judgment_executions(execution_id),
    input_hash TEXT NOT NULL,
    result TEXT NOT NULL,
    confidence FLOAT,
    ttl_seconds INT NOT NULL DEFAULT 3600,
    hit_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_hit_at TIMESTAMPTZ,
    UNIQUE (tenant_id, cache_key)
);

CREATE INDEX IF NOT EXISTS idx_judgment_cache_expires ON core.judgment_cache (expires_at) WHERE expires_at > now();
CREATE INDEX IF NOT EXISTS idx_judgment_cache_tenant_key ON core.judgment_cache (tenant_id, cache_key);

COMMENT ON TABLE core.judgment_cache IS '판단 캐시 - TTL 기반 무효화';
COMMENT ON COLUMN core.judgment_cache.cache_key IS 'judgment:{workflow_id}:{sha256(input_data)}';

-- =====================================================
-- 6. rule_conflicts (룰 충돌 감지)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.rule_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    ruleset_id UUID NOT NULL REFERENCES core.rulesets(ruleset_id),
    rule_version_1 INT NOT NULL,
    rule_version_2 INT NOT NULL,
    conflict_type TEXT NOT NULL CHECK (conflict_type IN ('output_conflict', 'condition_overlap', 'circular_dependency')),
    description TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    resolution_status TEXT NOT NULL DEFAULT 'unresolved' CHECK (resolution_status IN ('unresolved', 'investigating', 'resolved', 'accepted')),
    resolution_note TEXT,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES core.users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_rule_conflicts_ruleset ON core.rule_conflicts (ruleset_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_rule_conflicts_status ON core.rule_conflicts (resolution_status) WHERE resolution_status = 'unresolved';

COMMENT ON TABLE core.rule_conflicts IS '룰 충돌 감지 및 해결 이력';

-- =====================================================
-- 7. rule_deployments (룰 배포 이력)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.rule_deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    ruleset_id UUID NOT NULL REFERENCES core.rulesets(ruleset_id),
    version INT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'canary', 'active', 'rolled_back', 'deprecated')),
    canary_pct FLOAT CHECK (canary_pct >= 0 AND canary_pct <= 1),
    canary_target_filter JSONB,
    rollback_to INT,
    changelog TEXT NOT NULL,
    approver_id UUID REFERENCES core.users(user_id),
    approved_at TIMESTAMPTZ,
    deployed_at TIMESTAMPTZ,
    rolled_back_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_rule_deployments_ruleset ON core.rule_deployments (ruleset_id, deployed_at DESC);
CREATE INDEX IF NOT EXISTS idx_rule_deployments_status ON core.rule_deployments (status);

COMMENT ON TABLE core.rule_deployments IS '룰 배포 및 카나리 릴리즈 추적';
COMMENT ON COLUMN core.rule_deployments.canary_pct IS '카나리 비율: 0.1 = 10% 트래픽에만 적용';

-- =====================================================
-- 8. learning_samples (학습 샘플)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.learning_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    judgment_execution_id UUID REFERENCES core.judgment_executions(execution_id),
    input_features JSONB NOT NULL,
    label JSONB NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('feedback', 'auto', 'manual', 'import')),
    quality_score FLOAT CHECK (quality_score >= 0 AND quality_score <= 1),
    is_validated BOOLEAN NOT NULL DEFAULT false,
    validated_by UUID REFERENCES core.users(user_id),
    validated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_learning_samples_tenant ON core.learning_samples (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_samples_judgment ON core.learning_samples (judgment_execution_id);
CREATE INDEX IF NOT EXISTS idx_learning_samples_validated ON core.learning_samples (is_validated) WHERE is_validated = true;

COMMENT ON TABLE core.learning_samples IS 'LLM/ML 학습용 샘플 자동 수집';

-- =====================================================
-- 9. auto_rule_candidates (자동 룰 후보)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.auto_rule_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    ruleset_id UUID REFERENCES core.rulesets(ruleset_id),
    generated_rule TEXT NOT NULL,
    rule_language TEXT NOT NULL DEFAULT 'rhai',
    generation_method TEXT NOT NULL CHECK (generation_method IN ('llm', 'pattern_mining', 'ensemble')),
    coverage FLOAT CHECK (coverage >= 0 AND coverage <= 1),
    precision_score FLOAT CHECK (precision_score >= 0 AND precision_score <= 1),
    recall FLOAT CHECK (recall >= 0 AND recall <= 1),
    f1_score FLOAT,
    conflict_with TEXT[],
    is_approved BOOLEAN NOT NULL DEFAULT false,
    approval_status TEXT NOT NULL DEFAULT 'pending' CHECK (approval_status IN ('pending', 'approved', 'rejected', 'testing')),
    approver_id UUID REFERENCES core.users(user_id),
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    test_results JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_auto_rule_candidates_ruleset ON core.auto_rule_candidates (ruleset_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auto_rule_candidates_status ON core.auto_rule_candidates (approval_status);

COMMENT ON TABLE core.auto_rule_candidates IS 'LLM 생성 룰 후보 및 승인 관리';

-- =====================================================
-- 10. prompt_templates (프롬프트 템플릿)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    version INT NOT NULL,
    template_type TEXT NOT NULL CHECK (template_type IN ('judgment', 'chat', 'reasoning', 'extraction')),
    model_config JSONB NOT NULL,
    variables JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    a_b_test_group TEXT,
    created_by UUID REFERENCES core.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_tenant_active ON core.prompt_templates (tenant_id, is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_prompt_templates_name ON core.prompt_templates (tenant_id, name, version DESC);

COMMENT ON TABLE core.prompt_templates IS 'LLM 프롬프트 템플릿 버전 관리';

-- =====================================================
-- 11. prompt_template_bodies (프롬프트 본문)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.prompt_template_bodies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES core.prompt_templates(id) ON DELETE CASCADE,
    locale TEXT NOT NULL DEFAULT 'ko-KR',
    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,
    few_shot_examples JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (template_id, locale)
);

CREATE INDEX IF NOT EXISTS idx_prompt_bodies_template ON core.prompt_template_bodies (template_id);

COMMENT ON TABLE core.prompt_template_bodies IS '다국어 프롬프트 본문';

-- =====================================================
-- 12. llm_calls (LLM 호출 로그)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.llm_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    judgment_execution_id UUID REFERENCES core.judgment_executions(execution_id),
    prompt_template_id UUID REFERENCES core.prompt_templates(id),
    call_type TEXT NOT NULL CHECK (call_type IN ('judgment', 'chat', 'reasoning', 'embedding')),
    model TEXT NOT NULL,
    prompt_summary TEXT,
    prompt_tokens INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens INT NOT NULL,
    cost_estimate_usd NUMERIC(10, 6),
    latency_ms INT,
    success BOOLEAN NOT NULL DEFAULT true,
    validation_error BOOLEAN NOT NULL DEFAULT false,
    error_message TEXT,
    response_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    trace_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_tenant_created ON core.llm_calls (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_calls_judgment ON core.llm_calls (judgment_execution_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_model ON core.llm_calls (model, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_calls_validation_error ON core.llm_calls (validation_error) WHERE validation_error = true;

COMMENT ON TABLE core.llm_calls IS 'LLM API 호출 로그 및 비용 추적';

-- =====================================================
-- 13. chat_sessions (채팅 세션)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(user_id),
    title TEXT NOT NULL DEFAULT 'New Chat',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    context JSONB NOT NULL DEFAULT '{}',
    message_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_message_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON core.chat_sessions (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_tenant ON core.chat_sessions (tenant_id, updated_at DESC);

COMMENT ON TABLE core.chat_sessions IS '채팅 세션 관리';

-- =====================================================
-- 14. intent_logs (인텐트 로그)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.intent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    user_id UUID REFERENCES core.users(user_id),
    user_query TEXT NOT NULL,
    predicted_intent TEXT NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    extracted_slots JSONB,
    feedback_score INT CHECK (feedback_score >= 1 AND feedback_score <= 5),
    feedback_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_intent_logs_tenant ON core.intent_logs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intent_logs_intent ON core.intent_logs (predicted_intent);

COMMENT ON TABLE core.intent_logs IS '사용자 의도 분석 로그';

-- =====================================================
-- 15. chat_messages (채팅 메시지)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES core.chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    intent_log_id UUID REFERENCES core.intent_logs(id),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON core.chat_messages (session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_intent ON core.chat_messages (intent_log_id);

COMMENT ON TABLE core.chat_messages IS '채팅 메시지 이력';

-- =====================================================
-- 16. data_connectors (데이터 커넥터)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.data_connectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('postgres', 'mysql', 'mssql', 'oracle', 'rest_api', 'graphql', 'kafka')),
    engine TEXT,
    config JSONB NOT NULL,
    credentials_encrypted BYTEA,
    status TEXT NOT NULL DEFAULT 'inactive' CHECK (status IN ('active', 'inactive', 'error')),
    last_health_check_at TIMESTAMPTZ,
    last_health_status TEXT,
    created_by UUID REFERENCES core.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_data_connectors_tenant ON core.data_connectors (tenant_id);
CREATE INDEX IF NOT EXISTS idx_data_connectors_status ON core.data_connectors (status);

COMMENT ON TABLE core.data_connectors IS '외부 데이터 소스 연동 설정';

-- =====================================================
-- 17. mcp_servers (MCP 서버)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    protocol TEXT NOT NULL DEFAULT 'stdio' CHECK (protocol IN ('stdio', 'sse', 'websocket')),
    config JSONB NOT NULL,
    auth_config JSONB,
    status TEXT NOT NULL DEFAULT 'inactive' CHECK (status IN ('active', 'inactive', 'error')),
    last_health_check_at TIMESTAMPTZ,
    circuit_breaker_state TEXT NOT NULL DEFAULT 'closed' CHECK (circuit_breaker_state IN ('closed', 'open', 'half_open')),
    fail_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_tenant ON core.mcp_servers (tenant_id);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_status ON core.mcp_servers (status);

COMMENT ON TABLE core.mcp_servers IS 'MCP (Model Context Protocol) 서버 연동';
COMMENT ON COLUMN core.mcp_servers.circuit_breaker_state IS '회로 차단기 상태: closed(정상), open(차단), half_open(복구 시도)';

-- =====================================================
-- 18. mcp_tools (MCP 도구)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.mcp_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_server_id UUID NOT NULL REFERENCES core.mcp_servers(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    description TEXT,
    input_schema JSONB NOT NULL,
    output_schema JSONB,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    usage_count INT NOT NULL DEFAULT 0,
    avg_latency_ms INT,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (mcp_server_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_mcp_tools_server ON core.mcp_tools (mcp_server_id);
CREATE INDEX IF NOT EXISTS idx_mcp_tools_enabled ON core.mcp_tools (is_enabled) WHERE is_enabled = true;

COMMENT ON TABLE core.mcp_tools IS 'MCP 서버가 제공하는 도구 목록';

-- =====================================================
-- 19. mcp_call_logs (MCP 호출 로그)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.mcp_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    mcp_tool_id UUID NOT NULL REFERENCES core.mcp_tools(id),
    workflow_instance_id UUID REFERENCES core.workflow_instances(instance_id),
    input_data JSONB NOT NULL,
    output_data JSONB,
    success BOOLEAN NOT NULL DEFAULT true,
    error_message TEXT,
    latency_ms INT,
    retry_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    trace_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_mcp_call_logs_tenant ON core.mcp_call_logs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_call_logs_tool ON core.mcp_call_logs (mcp_tool_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_call_logs_workflow ON core.mcp_call_logs (workflow_instance_id);

COMMENT ON TABLE core.mcp_call_logs IS 'MCP 도구 호출 로그';

-- =====================================================
-- 20. model_training_jobs (모델 학습 작업)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.model_training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    job_type TEXT NOT NULL CHECK (job_type IN ('rule_learning', 'llm_finetuning', 'embedding_update')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    dataset_size INT,
    training_config JSONB NOT NULL,
    metrics JSONB,
    model_artifact_url TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INT,
    triggered_by UUID REFERENCES core.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_training_jobs_tenant ON core.model_training_jobs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_training_jobs_status ON core.model_training_jobs (status);

COMMENT ON TABLE core.model_training_jobs IS '모델 재학습 작업 추적';

-- =====================================================
-- 21. tenants 확장 (구독 플랜, 제한 등)
-- =====================================================
ALTER TABLE core.tenants
    ADD COLUMN IF NOT EXISTS display_name TEXT,
    ADD COLUMN IF NOT EXISTS subscription_plan TEXT DEFAULT 'standard' CHECK (subscription_plan IN ('trial', 'standard', 'enterprise', 'custom')),
    ADD COLUMN IF NOT EXISTS max_users INT DEFAULT 10,
    ADD COLUMN IF NOT EXISTS max_workflows INT DEFAULT 50,
    ADD COLUMN IF NOT EXISTS max_judgments_per_day INT DEFAULT 10000,
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- display_name 기본값 설정
UPDATE core.tenants SET display_name = name WHERE display_name IS NULL;

-- =====================================================
-- 22. users 확장 (권한 배열, 상태 등)
-- =====================================================
ALTER TABLE core.users
    ADD COLUMN IF NOT EXISTS permissions TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'locked'));

-- =====================================================
-- 23. updated_at 트리거 함수
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 새 테이블들에 트리거 추가
DO $$
DECLARE
    tbl TEXT;
    tables TEXT[] := ARRAY[
        'prompt_templates', 'chat_sessions', 'data_connectors', 'mcp_servers'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS trigger_%s_updated_at ON core.%s;
            CREATE TRIGGER trigger_%s_updated_at
                BEFORE UPDATE ON core.%s
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        ', tbl, tbl, tbl, tbl);
    END LOOP;
END $$;

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
