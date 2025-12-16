-- ===================================
-- Migration 013: Workflows 테이블 스키마 확장
-- B-3-1 Core Schema 스펙 준수
-- ===================================

SET search_path TO core, public;

-- ===================================
-- 1. Workflows 테이블 컬럼 추가
-- ===================================

-- dsl_digest: DSL JSON의 SHA256 해시 (변경 추적용)
ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS dsl_digest VARCHAR(64);

-- trigger_config: 트리거 설정 JSONB (schedule, event, webhook 등)
ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS trigger_config JSONB;

-- timeout_seconds: 워크플로우 타임아웃 (초)
ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS timeout_seconds INTEGER DEFAULT 300;

-- max_retry: 최대 재시도 횟수
ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS max_retry INTEGER DEFAULT 3;

-- tags: 태그 배열 (검색용)
ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';

-- metadata: 추가 메타데이터 JSONB
-- 주의: 기존 'metadata' 컬럼이 없는 경우에만 추가
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core'
        AND table_name = 'workflows'
        AND column_name = 'metadata'
    ) THEN
        ALTER TABLE workflows ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
END $$;

-- activated_at: 활성화 시각 (is_active = true로 변경된 시점)
ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS activated_at TIMESTAMP;

-- ===================================
-- 2. 인덱스 추가
-- ===================================

-- tags 배열 검색용 GIN 인덱스
CREATE INDEX IF NOT EXISTS idx_workflows_tags ON workflows USING GIN (tags);

-- dsl_digest 검색용 인덱스 (중복 DSL 감지)
CREATE INDEX IF NOT EXISTS idx_workflows_dsl_digest ON workflows (dsl_digest);

-- trigger_config 검색용 GIN 인덱스
CREATE INDEX IF NOT EXISTS idx_workflows_trigger_config ON workflows USING GIN (trigger_config);

-- ===================================
-- 3. 기존 데이터 처리
-- ===================================

-- 기존 행에 기본값 적용
UPDATE workflows
SET
    timeout_seconds = COALESCE(timeout_seconds, 300),
    max_retry = COALESCE(max_retry, 3),
    tags = COALESCE(tags, '{}'),
    metadata = COALESCE(metadata, '{}')
WHERE timeout_seconds IS NULL
   OR max_retry IS NULL
   OR tags IS NULL
   OR metadata IS NULL;

-- ===================================
-- 4. 코멘트 추가
-- ===================================

COMMENT ON COLUMN workflows.dsl_digest IS 'DSL JSON의 SHA256 해시 (변경 추적)';
COMMENT ON COLUMN workflows.trigger_config IS '트리거 설정 (schedule, event, webhook 등)';
COMMENT ON COLUMN workflows.timeout_seconds IS '워크플로우 타임아웃 (초)';
COMMENT ON COLUMN workflows.max_retry IS '최대 재시도 횟수';
COMMENT ON COLUMN workflows.tags IS '태그 배열 (검색용)';
COMMENT ON COLUMN workflows.metadata IS '추가 메타데이터';
COMMENT ON COLUMN workflows.activated_at IS '활성화 시각';

-- ===================================
-- 완료 메시지
-- ===================================
DO $$
BEGIN
    RAISE NOTICE 'Migration 013: Workflows 스키마 확장 완료';
    RAISE NOTICE '추가된 컬럼: dsl_digest, trigger_config, timeout_seconds, max_retry, tags, metadata, activated_at';
END $$;
