-- =====================================================
-- Migration 021: BI Chat History (대화형 GenBI)
--
-- AWS QuickSight GenBI 채팅 기능 지원:
-- - 대화 세션 관리
-- - 메시지 히스토리
-- - 인사이트 → 차트 Pin 연동
-- =====================================================

SET search_path TO bi, core, public;

-- =====================================================
-- 1. bi.chat_sessions (채팅 세션)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(user_id) ON DELETE CASCADE,

    -- 세션 메타데이터
    title TEXT NOT NULL DEFAULT '새 대화',
    context_type TEXT NOT NULL DEFAULT 'general'
        CHECK (context_type IN ('general', 'dashboard', 'chart', 'dataset')),
    context_id UUID,  -- 특정 대시보드/차트/데이터셋 컨텍스트

    -- 상태
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_message_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_chat_sessions_tenant_user
    ON bi.chat_sessions(tenant_id, user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_active
    ON bi.chat_sessions(tenant_id, user_id, is_active) WHERE is_active = TRUE;

COMMENT ON TABLE bi.chat_sessions IS 'BI 채팅 세션 (대화형 GenBI)';
COMMENT ON COLUMN bi.chat_sessions.context_type IS '컨텍스트 유형: general, dashboard, chart, dataset';

-- =====================================================
-- 2. bi.chat_messages (채팅 메시지)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES bi.chat_sessions(session_id) ON DELETE CASCADE,

    -- 메시지 내용
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,

    -- AI 응답 메타데이터 (role='assistant'일 때)
    response_type TEXT CHECK (response_type IN ('text', 'insight', 'chart', 'story', 'error')),
    response_data JSONB,  -- 인사이트/차트/스토리 데이터

    -- 연결된 객체
    linked_insight_id UUID REFERENCES bi.ai_insights(insight_id) ON DELETE SET NULL,
    linked_chart_id UUID REFERENCES bi.saved_charts(chart_id) ON DELETE SET NULL,

    -- 토큰 사용량
    prompt_tokens INT,
    completion_tokens INT,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_session
    ON bi.chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS ix_chat_messages_linked_insight
    ON bi.chat_messages(linked_insight_id) WHERE linked_insight_id IS NOT NULL;

COMMENT ON TABLE bi.chat_messages IS 'BI 채팅 메시지';
COMMENT ON COLUMN bi.chat_messages.response_type IS '응답 유형: text, insight, chart, story, error';
COMMENT ON COLUMN bi.chat_messages.response_data IS '구조화된 응답 데이터 (인사이트/차트 설정 등)';

-- =====================================================
-- 3. bi.pinned_insights (고정된 인사이트)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.pinned_insights (
    pin_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 원본 인사이트
    insight_id UUID NOT NULL REFERENCES bi.ai_insights(insight_id) ON DELETE CASCADE,

    -- 대시보드 위치
    dashboard_order INT NOT NULL DEFAULT 0,
    grid_position JSONB,  -- {x, y, w, h}

    -- 디스플레이 설정
    display_mode TEXT NOT NULL DEFAULT 'card'
        CHECK (display_mode IN ('card', 'compact', 'expanded')),
    show_facts BOOLEAN NOT NULL DEFAULT TRUE,
    show_reasoning BOOLEAN NOT NULL DEFAULT TRUE,
    show_actions BOOLEAN NOT NULL DEFAULT TRUE,

    -- 타임스탬프
    pinned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    pinned_by UUID NOT NULL REFERENCES core.users(user_id)
);

CREATE INDEX IF NOT EXISTS ix_pinned_insights_tenant
    ON bi.pinned_insights(tenant_id, dashboard_order);
CREATE UNIQUE INDEX IF NOT EXISTS ix_pinned_insights_unique
    ON bi.pinned_insights(tenant_id, insight_id);

COMMENT ON TABLE bi.pinned_insights IS '대시보드에 고정된 인사이트';
COMMENT ON COLUMN bi.pinned_insights.display_mode IS '표시 모드: card(기본), compact(축소), expanded(확장)';

-- =====================================================
-- 4. updated_at 트리거
-- =====================================================
DROP TRIGGER IF EXISTS trigger_chat_sessions_updated_at ON bi.chat_sessions;
CREATE TRIGGER trigger_chat_sessions_updated_at
    BEFORE UPDATE ON bi.chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 5. RLS (Row Level Security) 정책
-- =====================================================
ALTER TABLE bi.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi.pinned_insights ENABLE ROW LEVEL SECURITY;

-- chat_sessions: 본인 세션만 접근
DROP POLICY IF EXISTS rls_chat_sessions_owner ON bi.chat_sessions;
CREATE POLICY rls_chat_sessions_owner ON bi.chat_sessions
    USING (
        tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID
        AND user_id = current_setting('app.current_user_id', TRUE)::UUID
    );

-- chat_messages: 세션 소유자만 접근
DROP POLICY IF EXISTS rls_chat_messages_owner ON bi.chat_messages;
CREATE POLICY rls_chat_messages_owner ON bi.chat_messages
    USING (session_id IN (
        SELECT session_id FROM bi.chat_sessions
        WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID
          AND user_id = current_setting('app.current_user_id', TRUE)::UUID
    ));

-- pinned_insights: 테넌트 기반 접근
DROP POLICY IF EXISTS rls_pinned_insights_tenant ON bi.pinned_insights;
CREATE POLICY rls_pinned_insights_tenant ON bi.pinned_insights
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
