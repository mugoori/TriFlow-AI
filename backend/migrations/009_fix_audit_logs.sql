-- Migration: 009_fix_audit_logs.sql
-- Description: Audit Log 테이블에 누락된 컬럼 추가
-- Author: Claude
-- Date: 2025-12-03
--
-- 문제: audit_service.py가 사용하는 컬럼이 실제 DB에 없음
-- 해결: 파티션 테이블에 컬럼 추가 (자동으로 모든 파티션에 적용됨)

-- 1. resource 컬럼 추가 (기존 resource_type을 대체하지 않고 새로 추가)
ALTER TABLE audit.audit_logs ADD COLUMN IF NOT EXISTS resource VARCHAR(100);

-- 2. method 컬럼 추가 (HTTP 메서드: GET, POST, PUT, DELETE 등)
ALTER TABLE audit.audit_logs ADD COLUMN IF NOT EXISTS method VARCHAR(10);

-- 3. path 컬럼 추가 (API 경로)
ALTER TABLE audit.audit_logs ADD COLUMN IF NOT EXISTS path VARCHAR(500);

-- 4. status_code 컬럼 추가 (HTTP 상태 코드)
ALTER TABLE audit.audit_logs ADD COLUMN IF NOT EXISTS status_code INTEGER;

-- 5. request_body 컬럼 추가 (요청 본문, 마스킹됨)
ALTER TABLE audit.audit_logs ADD COLUMN IF NOT EXISTS request_body JSONB;

-- 6. response_summary 컬럼 추가 (응답 요약)
ALTER TABLE audit.audit_logs ADD COLUMN IF NOT EXISTS response_summary TEXT;

-- 7. duration_ms 컬럼 추가 (처리 시간)
ALTER TABLE audit.audit_logs ADD COLUMN IF NOT EXISTS duration_ms INTEGER;

-- 8. 기존 resource_id 컬럼 타입 수정 (UUID -> VARCHAR)
-- 파티션 테이블에서는 ALTER COLUMN TYPE이 제한적이므로, 새 컬럼으로 처리
-- resource_id가 UUID 타입이면 VARCHAR로 변환
DO $$
BEGIN
    -- resource_id 컬럼이 UUID 타입인지 확인 후 변환
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'audit'
        AND table_name = 'audit_logs'
        AND column_name = 'resource_id'
        AND data_type = 'uuid'
    ) THEN
        -- UUID 값을 VARCHAR로 변환하여 새 컬럼에 복사
        ALTER TABLE audit.audit_logs ADD COLUMN IF NOT EXISTS resource_id_str VARCHAR(255);
        UPDATE audit.audit_logs SET resource_id_str = resource_id::VARCHAR WHERE resource_id IS NOT NULL;
        ALTER TABLE audit.audit_logs DROP COLUMN IF EXISTS resource_id;
        ALTER TABLE audit.audit_logs RENAME COLUMN resource_id_str TO resource_id;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'resource_id column conversion skipped or already done: %', SQLERRM;
END $$;

-- 9. 인덱스 추가 (성능 향상)
CREATE INDEX IF NOT EXISTS idx_audit_logs_path ON audit.audit_logs(path);
CREATE INDEX IF NOT EXISTS idx_audit_logs_status_code ON audit.audit_logs(status_code);
CREATE INDEX IF NOT EXISTS idx_audit_logs_method ON audit.audit_logs(method);

-- 10. 기존 데이터 마이그레이션 (resource_type -> resource)
UPDATE audit.audit_logs
SET resource = resource_type
WHERE resource IS NULL AND resource_type IS NOT NULL;

-- Verification query (주석 처리, 수동 실행용)
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_schema = 'audit' AND table_name = 'audit_logs'
-- ORDER BY ordinal_position;
