-- ===================================
-- Migration 014: workflow_steps 컬럼명 수정
-- id → step_id (SQLAlchemy 모델과 동기화)
-- ===================================

SET search_path TO core, public;

-- ===================================
-- 1. workflow_execution_logs FK 임시 제거
-- ===================================
ALTER TABLE core.workflow_execution_logs
    DROP CONSTRAINT IF EXISTS workflow_execution_logs_step_id_fkey;

-- ===================================
-- 2. workflow_steps.id → step_id 컬럼명 변경
-- ===================================
ALTER TABLE core.workflow_steps
    RENAME COLUMN id TO step_id;

-- ===================================
-- 3. workflow_execution_logs FK 재생성
-- ===================================
ALTER TABLE core.workflow_execution_logs
    ADD CONSTRAINT workflow_execution_logs_step_id_fkey
    FOREIGN KEY (step_id) REFERENCES core.workflow_steps(step_id);

-- ===================================
-- 완료 메시지
-- ===================================
DO $$
BEGIN
    RAISE NOTICE 'Migration 014: workflow_steps.id → step_id 컬럼명 변경 완료';
END $$;
