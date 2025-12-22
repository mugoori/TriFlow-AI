-- =====================================================
-- Migration 022: Workflow Approvals & Events
-- 스펙 참조: B-5_Workflow_Tab_Spec.md
--
-- 추가 테이블:
--   1. workflow_approvals - 워크플로우 승인 요청/처리
--   2. workflow_events - 이벤트 기반 트리거/대기
--   3. workflow_scheduled_triggers - 스케줄 트리거 등록
-- =====================================================

SET search_path TO core, public;

-- =====================================================
-- 1. workflow_approvals (워크플로우 승인)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.workflow_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 워크플로우 연관
    workflow_id UUID NOT NULL REFERENCES core.workflows(workflow_id) ON DELETE CASCADE,
    instance_id UUID REFERENCES core.workflow_instances(instance_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,

    -- 승인 정보
    approval_type TEXT NOT NULL DEFAULT 'single' CHECK (approval_type IN ('single', 'multi', 'quorum')),
    title TEXT NOT NULL,
    description TEXT,

    -- 승인자 목록 (JSONB: [{"user_id": "...", "email": "...", "status": "pending"}])
    approvers JSONB NOT NULL DEFAULT '[]',
    quorum_count INT DEFAULT 1,

    -- 상태
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'timeout', 'cancelled')),

    -- 결과
    decided_by UUID REFERENCES core.users(user_id),
    decided_at TIMESTAMPTZ,
    decision_comment TEXT,

    -- 알림 설정
    notification_channels JSONB DEFAULT '["email"]',
    notification_sent_at TIMESTAMPTZ,
    reminder_count INT DEFAULT 0,

    -- 타임아웃
    timeout_at TIMESTAMPTZ,
    auto_approve_on_timeout BOOLEAN DEFAULT false,

    -- 메타데이터
    context_data JSONB DEFAULT '{}',

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_workflow_approvals_tenant ON core.workflow_approvals (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_approvals_instance ON core.workflow_approvals (instance_id) WHERE instance_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_workflow_approvals_status ON core.workflow_approvals (status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_workflow_approvals_timeout ON core.workflow_approvals (timeout_at) WHERE status = 'pending';

COMMENT ON TABLE core.workflow_approvals IS '워크플로우 승인 요청 및 처리';
COMMENT ON COLUMN core.workflow_approvals.approvers IS 'JSONB: [{"user_id": "...", "email": "...", "status": "pending|approved|rejected", "decided_at": "..."}]';

-- =====================================================
-- 2. workflow_events (워크플로우 이벤트)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.workflow_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 이벤트 정보
    event_type TEXT NOT NULL,
    event_source TEXT,  -- sensor, api, webhook, schedule, manual
    event_data JSONB NOT NULL DEFAULT '{}',

    -- 연관 워크플로우
    workflow_id UUID REFERENCES core.workflows(workflow_id) ON DELETE SET NULL,
    instance_id UUID REFERENCES core.workflow_instances(instance_id) ON DELETE SET NULL,
    node_id TEXT,

    -- 처리 상태
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMPTZ,
    processed_by_instance UUID REFERENCES core.workflow_instances(instance_id),

    -- 메타데이터
    correlation_id TEXT,
    trace_id TEXT,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ  -- 이벤트 만료 시간 (null = never)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_workflow_events_tenant_type ON core.workflow_events (tenant_id, event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_events_unprocessed ON core.workflow_events (tenant_id, event_type)
    WHERE processed = false;
CREATE INDEX IF NOT EXISTS idx_workflow_events_correlation ON core.workflow_events (correlation_id)
    WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_workflow_events_expires ON core.workflow_events (expires_at)
    WHERE expires_at IS NOT NULL AND processed = false;

COMMENT ON TABLE core.workflow_events IS '워크플로우 이벤트 (트리거, 대기 노드용)';

-- =====================================================
-- 3. workflow_scheduled_triggers (스케줄 트리거)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.workflow_scheduled_triggers (
    trigger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 워크플로우 연관
    workflow_id UUID NOT NULL REFERENCES core.workflows(workflow_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,

    -- 스케줄 설정
    cron_expression TEXT,
    interval_seconds INT,
    timezone TEXT DEFAULT 'UTC',

    -- 상태
    is_active BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMPTZ,
    next_trigger_at TIMESTAMPTZ,

    -- 실행 통계
    trigger_count INT DEFAULT 0,
    error_count INT DEFAULT 0,
    last_error TEXT,

    -- 메타데이터
    trigger_config JSONB DEFAULT '{}',

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (workflow_id, node_id)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_wf_sched_triggers_tenant ON core.workflow_scheduled_triggers (tenant_id);
CREATE INDEX IF NOT EXISTS idx_wf_sched_triggers_active ON core.workflow_scheduled_triggers (is_active, next_trigger_at)
    WHERE is_active = true;

COMMENT ON TABLE core.workflow_scheduled_triggers IS '스케줄 기반 워크플로우 트리거';

-- =====================================================
-- 4. updated_at 트리거
-- =====================================================
DROP TRIGGER IF EXISTS trigger_workflow_approvals_updated_at ON core.workflow_approvals;
CREATE TRIGGER trigger_workflow_approvals_updated_at
    BEFORE UPDATE ON core.workflow_approvals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_wf_sched_triggers_updated_at ON core.workflow_scheduled_triggers;
CREATE TRIGGER trigger_wf_sched_triggers_updated_at
    BEFORE UPDATE ON core.workflow_scheduled_triggers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE 'Migration 022: Workflow Approvals & Events 완료';
    RAISE NOTICE '추가된 테이블: workflow_approvals, workflow_events, workflow_scheduled_triggers';
END $$;
