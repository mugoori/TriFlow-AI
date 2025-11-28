-- ===================================
-- TriFlow AI - workflow_instances 마이그레이션
-- context -> input_data, output_data 변경
-- ===================================

SET search_path TO core, public;

-- 1. input_data 컬럼 추가 (없는 경우)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core'
        AND table_name = 'workflow_instances'
        AND column_name = 'input_data'
    ) THEN
        ALTER TABLE core.workflow_instances
        ADD COLUMN input_data JSONB DEFAULT '{}';
        RAISE NOTICE 'Added input_data column';
    END IF;
END $$;

-- 2. output_data 컬럼 추가 (없는 경우)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core'
        AND table_name = 'workflow_instances'
        AND column_name = 'output_data'
    ) THEN
        ALTER TABLE core.workflow_instances
        ADD COLUMN output_data JSONB DEFAULT '{}';
        RAISE NOTICE 'Added output_data column';
    END IF;
END $$;

-- 3. context 컬럼에서 데이터 마이그레이션 (존재하는 경우)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core'
        AND table_name = 'workflow_instances'
        AND column_name = 'context'
    ) THEN
        -- context 데이터를 input_data로 복사
        UPDATE core.workflow_instances
        SET input_data = COALESCE(context, '{}')
        WHERE input_data = '{}' OR input_data IS NULL;

        RAISE NOTICE 'Migrated context data to input_data';
    END IF;
END $$;

-- 마이그레이션 완료 확인
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_schema = 'core' AND table_name = 'workflow_instances'
ORDER BY ordinal_position;
