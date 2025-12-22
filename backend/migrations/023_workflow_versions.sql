-- =====================================================
-- Migration 023: Workflow Versions
-- 스펙 참조: B-5_Workflow_Tab_Spec.md
--
-- 추가 테이블:
--   1. workflow_versions - 워크플로우 버전 관리
-- =====================================================

SET search_path TO core, public;

-- =====================================================
-- 1. workflow_versions (워크플로우 버전)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.workflow_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    -- 워크플로우 연관
    workflow_id UUID NOT NULL REFERENCES core.workflows(workflow_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,

    -- DSL 스냅샷
    dsl_definition JSONB NOT NULL,

    -- 버전 메타데이터
    change_log TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'deprecated', 'archived')),

    -- 생성자
    created_by UUID REFERENCES core.users(user_id),

    -- 배포 정보
    published_at TIMESTAMPTZ,
    published_by UUID REFERENCES core.users(user_id),

    -- 타임스탬프
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 제약 조건: workflow_id + version 유니크
    UNIQUE (workflow_id, version)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_workflow_versions_tenant ON core.workflow_versions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflow_versions_workflow ON core.workflow_versions (workflow_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_versions_status ON core.workflow_versions (workflow_id, status)
    WHERE status = 'active';

COMMENT ON TABLE core.workflow_versions IS '워크플로우 버전 관리 (DSL 스냅샷)';
COMMENT ON COLUMN core.workflow_versions.status IS 'draft: 작성 중, active: 현재 배포됨, deprecated: 더 이상 사용 안 함, archived: 보관';

-- =====================================================
-- 2. workflows 테이블에 current_version 컬럼 추가 (존재하지 않는 경우)
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core'
        AND table_name = 'workflows'
        AND column_name = 'current_version'
    ) THEN
        ALTER TABLE core.workflows ADD COLUMN current_version INTEGER DEFAULT 1;
    END IF;
END $$;

-- =====================================================
-- 3. 버전 자동 증가 함수
-- =====================================================
CREATE OR REPLACE FUNCTION core.get_next_workflow_version(p_workflow_id UUID)
RETURNS INTEGER AS $$
DECLARE
    next_version INTEGER;
BEGIN
    SELECT COALESCE(MAX(version), 0) + 1 INTO next_version
    FROM core.workflow_versions
    WHERE workflow_id = p_workflow_id;

    RETURN next_version;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION core.get_next_workflow_version(UUID) IS '워크플로우의 다음 버전 번호 반환';

-- =====================================================
-- 마이그레이션 완료
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE 'Migration 023: Workflow Versions 완료';
    RAISE NOTICE '추가된 테이블: workflow_versions';
    RAISE NOTICE '추가된 함수: get_next_workflow_version()';
END $$;
