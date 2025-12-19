-- =====================================================
-- Migration 015: Critical Schema Additions
-- 스펙 참조: B-3_Data_DB_Schema_Design.md
--
-- 🔴 Critical 누락 테이블 추가:
--   1. feedbacks - 사용자 피드백 수집 (학습 루프)
--   2. rule_scripts - 룰 버전 관리 분리
-- =====================================================

SET search_path TO core, public;

-- =====================================================
-- 1. feedbacks (사용자 피드백)
-- 스펙: B-3 섹션 2 - 판단/워크플로우/학습/배포
-- =====================================================
CREATE TABLE IF NOT EXISTS core.feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 연관 엔티티
    judgment_execution_id UUID REFERENCES core.judgment_executions(execution_id) ON DELETE SET NULL,
    workflow_instance_id UUID REFERENCES core.workflow_instances(instance_id) ON DELETE SET NULL,
    chat_message_id UUID REFERENCES core.chat_messages(id) ON DELETE SET NULL,

    -- 피드백 제공자
    user_id UUID NOT NULL REFERENCES core.users(user_id),

    -- 피드백 내용
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('thumbs_up', 'thumbs_down', 'rating', 'correction', 'suggestion')),
    rating INT CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,

    -- 수정 제안 (correction 타입용)
    original_result TEXT,
    corrected_result TEXT,
    correction_reason TEXT,

    -- 메타데이터
    context JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',

    -- 처리 상태
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'applied', 'rejected')),
    reviewed_by UUID REFERENCES core.users(user_id),
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- feedbacks 인덱스
CREATE INDEX IF NOT EXISTS idx_feedbacks_tenant ON core.feedbacks (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedbacks_judgment ON core.feedbacks (judgment_execution_id) WHERE judgment_execution_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_feedbacks_workflow ON core.feedbacks (workflow_instance_id) WHERE workflow_instance_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_feedbacks_user ON core.feedbacks (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedbacks_status ON core.feedbacks (status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_feedbacks_type ON core.feedbacks (feedback_type);

COMMENT ON TABLE core.feedbacks IS '사용자 피드백 - 학습 루프 및 품질 개선용';
COMMENT ON COLUMN core.feedbacks.feedback_type IS 'thumbs_up/down: 간단 평가, rating: 1-5점, correction: 수정 제안, suggestion: 개선 의견';

-- =====================================================
-- 2. rule_scripts (룰 스크립트 버전 관리)
-- 스펙: B-3 섹션 3 - rulesets / rule_scripts / rule_deployments
-- =====================================================
CREATE TABLE IF NOT EXISTS core.rule_scripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ruleset_id UUID NOT NULL REFERENCES core.rulesets(ruleset_id) ON DELETE CASCADE,

    -- 버전 정보
    version INT NOT NULL,

    -- 스크립트 내용
    language TEXT NOT NULL DEFAULT 'rhai' CHECK (language IN ('rhai', 'json_logic', 'python')),
    script TEXT NOT NULL,
    script_hash TEXT NOT NULL,  -- SHA256 해시 (변경 감지)

    -- 메타데이터
    description TEXT,
    changelog TEXT,

    -- 검증 정보
    is_validated BOOLEAN NOT NULL DEFAULT false,
    validation_result JSONB,
    validated_at TIMESTAMPTZ,

    -- 성능 메트릭
    avg_execution_time_ms FLOAT,
    execution_count INT DEFAULT 0,
    error_count INT DEFAULT 0,

    -- 감사 정보
    created_by UUID REFERENCES core.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 유니크 제약: 룰셋당 버전 유일
    UNIQUE (ruleset_id, version)
);

-- rule_scripts 인덱스
CREATE INDEX IF NOT EXISTS idx_rule_scripts_ruleset ON core.rule_scripts (ruleset_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_rule_scripts_hash ON core.rule_scripts (script_hash);
CREATE INDEX IF NOT EXISTS idx_rule_scripts_validated ON core.rule_scripts (is_validated) WHERE is_validated = true;

COMMENT ON TABLE core.rule_scripts IS '룰 스크립트 버전 관리 - rulesets와 분리하여 버전별 이력 추적';
COMMENT ON COLUMN core.rule_scripts.script_hash IS 'SHA256(script) - 중복/변경 감지용';

-- =====================================================
-- 3. rulesets 테이블 연동 (기존 rhai_code → rule_scripts 마이그레이션 지원)
-- =====================================================

-- rulesets에 current_version 컬럼 추가 (현재 활성 버전 참조)
ALTER TABLE core.rulesets
    ADD COLUMN IF NOT EXISTS current_script_id UUID REFERENCES core.rule_scripts(id),
    ADD COLUMN IF NOT EXISTS target_kpi TEXT;

-- 기존 rulesets.rhai_code → rule_scripts로 마이그레이션
-- (기존 데이터가 있는 경우에만 실행)
DO $$
DECLARE
    r RECORD;
    new_script_id UUID;
BEGIN
    FOR r IN
        SELECT ruleset_id, rhai_code, version, created_by, created_at
        FROM core.rulesets
        WHERE rhai_code IS NOT NULL
          AND rhai_code != ''
          AND NOT EXISTS (
              SELECT 1 FROM core.rule_scripts rs
              WHERE rs.ruleset_id = rulesets.ruleset_id
          )
    LOOP
        INSERT INTO core.rule_scripts (
            ruleset_id, version, language, script, script_hash,
            description, created_by, created_at
        ) VALUES (
            r.ruleset_id,
            COALESCE(r.version::INT, 1),
            'rhai',
            r.rhai_code,
            encode(sha256(r.rhai_code::bytea), 'hex'),
            'Migrated from rulesets.rhai_code',
            r.created_by,
            r.created_at
        )
        RETURNING id INTO new_script_id;

        -- current_script_id 업데이트
        UPDATE core.rulesets
        SET current_script_id = new_script_id
        WHERE ruleset_id = r.ruleset_id;
    END LOOP;
END $$;

COMMENT ON COLUMN core.rulesets.current_script_id IS '현재 활성 스크립트 버전 참조';
COMMENT ON COLUMN core.rulesets.target_kpi IS '이 룰셋이 타겟하는 KPI (예: defect_rate, oee)';

-- =====================================================
-- 4. updated_at 트리거 추가
-- =====================================================
DROP TRIGGER IF EXISTS trigger_feedbacks_updated_at ON core.feedbacks;
CREATE TRIGGER trigger_feedbacks_updated_at
    BEFORE UPDATE ON core.feedbacks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
