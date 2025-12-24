-- =====================================================
-- Migration 020: GenBI Schema (AWS QuickSight 동일 기능)
-- 스펙 참조: AWS QuickSight GenBI 3대 핵심 기능
--
-- 1. AI Dashboard Authoring (차트 생성 + Refinement Loop)
-- 2. Executive Summary (Fact/Reasoning/Action 인사이트)
-- 3. Data Stories (내러티브 보고서)
-- =====================================================

SET search_path TO bi, core, public;

-- bi 스키마 생성 (없을 경우)
CREATE SCHEMA IF NOT EXISTS bi;

-- =====================================================
-- 1. bi.ai_insights (Executive Summary 저장)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.ai_insights (
    insight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 인사이트 소스
    source_type TEXT NOT NULL CHECK (source_type IN ('chart', 'dashboard', 'dataset', 'chat')),
    source_id UUID,  -- 차트/대시보드 ID (nullable for ad-hoc insights)

    -- 인사이트 내용
    title TEXT NOT NULL,
    summary TEXT NOT NULL,

    -- Fact/Reasoning/Action 구조 (QuickSight GenBI 핵심)
    facts JSONB NOT NULL DEFAULT '[]',
    -- [{metric_name, current_value, previous_value, change_percent, trend, period, unit}]

    reasoning JSONB NOT NULL DEFAULT '{}',
    -- {analysis, contributing_factors: [], confidence, data_quality_notes}

    actions JSONB NOT NULL DEFAULT '[]',
    -- [{priority, action, expected_impact, responsible_team, deadline_suggestion}]

    -- AI 모델 정보
    model_used TEXT NOT NULL DEFAULT 'claude-sonnet-4-5-20250929',
    prompt_tokens INT,
    completion_tokens INT,

    -- 사용자 피드백
    feedback_score NUMERIC(3,2) CHECK (feedback_score >= -1 AND feedback_score <= 1),
    feedback_comment TEXT,
    feedback_at TIMESTAMPTZ,
    feedback_by UUID REFERENCES core.users(user_id),

    -- 감사
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES core.users(user_id)
);

CREATE INDEX IF NOT EXISTS ix_ai_insights_tenant ON bi.ai_insights(tenant_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS ix_ai_insights_source ON bi.ai_insights(source_type, source_id);
CREATE INDEX IF NOT EXISTS ix_ai_insights_feedback ON bi.ai_insights(feedback_score) WHERE feedback_score IS NOT NULL;

COMMENT ON TABLE bi.ai_insights IS 'AI 생성 인사이트 (Executive Summary)';
COMMENT ON COLUMN bi.ai_insights.facts IS 'QuickSight GenBI Fact 구조: 객관적 사실 목록';
COMMENT ON COLUMN bi.ai_insights.reasoning IS 'QuickSight GenBI Reasoning 구조: 분석 및 원인 추론';
COMMENT ON COLUMN bi.ai_insights.actions IS 'QuickSight GenBI Action 구조: 권장 조치 목록';
COMMENT ON COLUMN bi.ai_insights.feedback_score IS '-1: 부정, 0: 중립, 1: 긍정';

-- =====================================================
-- 2. bi.data_stories (내러티브 보고서)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.data_stories (
    story_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 스토리 메타데이터
    title TEXT NOT NULL,
    description TEXT,

    -- 공개 설정
    is_public BOOLEAN NOT NULL DEFAULT FALSE,

    -- 작성자 정보
    created_by UUID NOT NULL REFERENCES core.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ  -- NULL이면 미발행 (드래프트)
);

CREATE INDEX IF NOT EXISTS ix_data_stories_tenant ON bi.data_stories(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_data_stories_author ON bi.data_stories(created_by);
CREATE INDEX IF NOT EXISTS ix_data_stories_public ON bi.data_stories(is_public) WHERE is_public = TRUE;

COMMENT ON TABLE bi.data_stories IS 'Data Stories (내러티브 보고서)';
COMMENT ON COLUMN bi.data_stories.published_at IS 'NULL이면 드래프트 상태';

-- =====================================================
-- 3. bi.story_sections (스토리 섹션)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.story_sections (
    section_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES bi.data_stories(story_id) ON DELETE CASCADE,

    -- 섹션 정보
    section_type TEXT NOT NULL CHECK (section_type IN ('introduction', 'analysis', 'finding', 'conclusion')),
    "order" INT NOT NULL,
    title TEXT NOT NULL,
    narrative TEXT NOT NULL,  -- Markdown 형식

    -- 섹션 내 차트
    charts JSONB NOT NULL DEFAULT '[]',
    -- [{chart_config: {...}, caption: "...", order: 0}]

    -- AI 생성 여부
    ai_generated BOOLEAN NOT NULL DEFAULT TRUE,

    -- 감사
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_story_sections_story ON bi.story_sections(story_id, "order");
CREATE INDEX IF NOT EXISTS ix_story_sections_type ON bi.story_sections(section_type);

COMMENT ON TABLE bi.story_sections IS '스토리 섹션 (슬라이드/페이지 단위)';
COMMENT ON COLUMN bi.story_sections.section_type IS 'introduction: 도입, analysis: 분석, finding: 발견, conclusion: 결론';
COMMENT ON COLUMN bi.story_sections.narrative IS 'Markdown 형식의 내러티브 텍스트';
COMMENT ON COLUMN bi.story_sections.charts IS '섹션 내 차트 설정: [{chart_config, caption, order}]';

-- =====================================================
-- 4. bi.chart_refinements (차트 수정 이력)
-- Refinement Loop 지원용
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.chart_refinements (
    refinement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 원본/수정 차트
    original_chart_config JSONB NOT NULL,
    refined_chart_config JSONB NOT NULL,

    -- 수정 지시
    instruction TEXT NOT NULL,
    changes_made JSONB NOT NULL DEFAULT '[]',  -- ["차트 유형 변경: bar → line", "제목 변경"]

    -- AI 모델 정보
    model_used TEXT NOT NULL DEFAULT 'claude-sonnet-4-5-20250929',
    processing_time_ms INT,

    -- 감사
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES core.users(user_id)
);

CREATE INDEX IF NOT EXISTS ix_chart_refinements_tenant ON bi.chart_refinements(tenant_id, created_at DESC);

COMMENT ON TABLE bi.chart_refinements IS '차트 수정 이력 (Refinement Loop)';
COMMENT ON COLUMN bi.chart_refinements.instruction IS '사용자 수정 지시 (예: "막대 차트로 바꿔줘")';
COMMENT ON COLUMN bi.chart_refinements.changes_made IS '적용된 변경 사항 목록';

-- =====================================================
-- 5. bi.saved_charts (대시보드 고정 차트)
-- =====================================================
CREATE TABLE IF NOT EXISTS bi.saved_charts (
    chart_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 차트 정보
    title TEXT NOT NULL,
    chart_config JSONB NOT NULL,

    -- 원본 쿼리/데이터
    source_query TEXT,
    source_insight_id UUID REFERENCES bi.ai_insights(insight_id) ON DELETE SET NULL,

    -- 대시보드 위치
    dashboard_order INT NOT NULL DEFAULT 0,
    grid_position JSONB,  -- {x, y, w, h} for future grid layout

    -- 상태
    is_pinned BOOLEAN NOT NULL DEFAULT TRUE,

    -- 감사
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID NOT NULL REFERENCES core.users(user_id)
);

CREATE INDEX IF NOT EXISTS ix_saved_charts_tenant ON bi.saved_charts(tenant_id, dashboard_order);
CREATE INDEX IF NOT EXISTS ix_saved_charts_pinned ON bi.saved_charts(tenant_id, is_pinned) WHERE is_pinned = TRUE;

COMMENT ON TABLE bi.saved_charts IS '대시보드에 고정된 차트';
COMMENT ON COLUMN bi.saved_charts.grid_position IS '대시보드 그리드 위치 (향후 드래그 앤 드롭용)';

-- =====================================================
-- 6. updated_at 트리거
-- =====================================================
DROP TRIGGER IF EXISTS trigger_data_stories_updated_at ON bi.data_stories;
CREATE TRIGGER trigger_data_stories_updated_at
    BEFORE UPDATE ON bi.data_stories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_story_sections_updated_at ON bi.story_sections;
CREATE TRIGGER trigger_story_sections_updated_at
    BEFORE UPDATE ON bi.story_sections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_saved_charts_updated_at ON bi.saved_charts;
CREATE TRIGGER trigger_saved_charts_updated_at
    BEFORE UPDATE ON bi.saved_charts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 7. RLS (Row Level Security) 정책
-- =====================================================
ALTER TABLE bi.ai_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi.data_stories ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi.story_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi.chart_refinements ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi.saved_charts ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 후 재생성
DROP POLICY IF EXISTS rls_ai_insights_tenant ON bi.ai_insights;
CREATE POLICY rls_ai_insights_tenant ON bi.ai_insights
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

DROP POLICY IF EXISTS rls_data_stories_tenant ON bi.data_stories;
CREATE POLICY rls_data_stories_tenant ON bi.data_stories
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

DROP POLICY IF EXISTS rls_story_sections_tenant ON bi.story_sections;
CREATE POLICY rls_story_sections_tenant ON bi.story_sections
    USING (story_id IN (
        SELECT story_id FROM bi.data_stories
        WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID
    ));

DROP POLICY IF EXISTS rls_chart_refinements_tenant ON bi.chart_refinements;
CREATE POLICY rls_chart_refinements_tenant ON bi.chart_refinements
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

DROP POLICY IF EXISTS rls_saved_charts_tenant ON bi.saved_charts;
CREATE POLICY rls_saved_charts_tenant ON bi.saved_charts
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

-- =====================================================
-- 8. 뷰: 대시보드용 인사이트 요약
-- =====================================================
CREATE OR REPLACE VIEW bi.v_dashboard_insights AS
SELECT
    i.insight_id,
    i.tenant_id,
    i.title,
    i.summary,
    i.source_type,
    i.source_id,
    jsonb_array_length(i.facts) AS fact_count,
    jsonb_array_length(i.actions) AS action_count,
    (i.reasoning->>'confidence')::NUMERIC AS confidence,
    i.feedback_score,
    i.generated_at,
    u.email AS created_by_email
FROM bi.ai_insights i
LEFT JOIN core.users u ON i.created_by = u.user_id
ORDER BY i.generated_at DESC;

COMMENT ON VIEW bi.v_dashboard_insights IS '대시보드용 인사이트 요약 뷰';

-- =====================================================
-- 9. 뷰: 스토리 목록
-- =====================================================
CREATE OR REPLACE VIEW bi.v_story_list AS
SELECT
    s.story_id,
    s.tenant_id,
    s.title,
    s.description,
    s.is_public,
    s.created_at,
    s.updated_at,
    s.published_at,
    u.email AS author_email,
    COUNT(sec.section_id) AS section_count,
    COALESCE(SUM(jsonb_array_length(sec.charts)), 0) AS total_charts
FROM bi.data_stories s
LEFT JOIN core.users u ON s.created_by = u.user_id
LEFT JOIN bi.story_sections sec ON s.story_id = sec.story_id
GROUP BY s.story_id, u.email
ORDER BY s.updated_at DESC;

COMMENT ON VIEW bi.v_story_list IS '스토리 목록 뷰 (섹션/차트 수 포함)';

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
