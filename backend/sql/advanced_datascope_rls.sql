-- Advanced DataScope RLS (Row-Level Security) Policies
-- PostgreSQL Row-Level Security를 사용한 멀티테넌트 격리
--
-- 설치 방법:
--   psql -U postgres -d triflow_ai -f backend/sql/advanced_datascope_rls.sql
--
-- 주의:
--   - RLS는 PostgreSQL 9.5 이상에서 지원됩니다
--   - RLS 정책은 superuser를 제외한 모든 사용자에게 적용됩니다
--   - application_name과 current_setting을 사용하여 사용자 컨텍스트를 전달합니다

-- ============================================
-- 1. SensorData RLS Policy
-- ============================================

-- RLS 활성화
ALTER TABLE core.sensor_data ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS sensor_data_tenant_isolation ON core.sensor_data;
DROP POLICY IF EXISTS sensor_data_line_scope ON core.sensor_data;

-- Tenant 격리 정책 (모든 작업에 적용)
-- tenant_id 세션 변수와 일치하는 행만 접근 가능
CREATE POLICY sensor_data_tenant_isolation ON core.sensor_data
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

-- Line Code 스코프 정책 (SELECT만 적용)
-- line_codes 세션 변수에 포함된 라인만 조회 가능
-- Admin (all_access=true)은 전체 접근
CREATE POLICY sensor_data_line_scope ON core.sensor_data
    FOR SELECT
    USING (
        current_setting('app.all_access', true)::boolean = true
        OR line_code = ANY(string_to_array(current_setting('app.line_codes', true), ','))
    );

-- ============================================
-- 2. ErpMesData RLS Policy
-- ============================================

-- RLS 활성화
ALTER TABLE core.erp_mes_data ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS erp_mes_data_tenant_isolation ON core.erp_mes_data;

-- Tenant 격리 정책
CREATE POLICY erp_mes_data_tenant_isolation ON core.erp_mes_data
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

-- ============================================
-- 3. JudgmentExecution RLS Policy
-- ============================================

-- RLS 활성화
ALTER TABLE core.judgment_executions ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS judgment_executions_tenant_isolation ON core.judgment_executions;

-- Tenant 격리 정책
CREATE POLICY judgment_executions_tenant_isolation ON core.judgment_executions
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

-- ============================================
-- 4. Workflow RLS Policy
-- ============================================

-- RLS 활성화
ALTER TABLE core.workflows ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS workflows_tenant_isolation ON core.workflows;

-- Tenant 격리 정책
CREATE POLICY workflows_tenant_isolation ON core.workflows
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

-- ============================================
-- 5. Ruleset RLS Policy
-- ============================================

-- RLS 활성화
ALTER TABLE core.rulesets ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS rulesets_tenant_isolation ON core.rulesets;

-- Tenant 격리 정책
CREATE POLICY rulesets_tenant_isolation ON core.rulesets
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

-- ============================================
-- 6. User RLS Policy
-- ============================================

-- RLS 활성화
ALTER TABLE core.users ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS users_tenant_isolation ON core.users;

-- Tenant 격리 정책
CREATE POLICY users_tenant_isolation ON core.users
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

-- ============================================
-- 7. 헬퍼 함수: 세션 변수 설정
-- ============================================

-- 현재 테넌트 ID 설정
CREATE OR REPLACE FUNCTION core.set_current_tenant(p_tenant_id UUID)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', p_tenant_id::text, false);
END;
$$ LANGUAGE plpgsql;

-- DataScope 설정 (line_codes, all_access)
CREATE OR REPLACE FUNCTION core.set_data_scope(
    p_tenant_id UUID,
    p_line_codes TEXT[],
    p_all_access BOOLEAN DEFAULT false
)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', p_tenant_id::text, false);
    PERFORM set_config('app.line_codes', array_to_string(p_line_codes, ','), false);
    PERFORM set_config('app.all_access', p_all_access::text, false);
END;
$$ LANGUAGE plpgsql;

-- DataScope 초기화 (세션 변수 제거)
CREATE OR REPLACE FUNCTION core.clear_data_scope()
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', false);
    PERFORM set_config('app.line_codes', '', false);
    PERFORM set_config('app.all_access', 'false', false);
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 8. 테스트 쿼리
-- ============================================

-- 사용 예시:
--
-- -- Tenant A 사용자 (LINE_A, LINE_B 접근)
-- SELECT core.set_data_scope(
--     'tenant-a-uuid'::uuid,
--     ARRAY['LINE_A', 'LINE_B'],
--     false
-- );
-- SELECT * FROM core.sensor_data;  -- LINE_A, LINE_B 데이터만 반환
--
-- -- Admin (전체 접근)
-- SELECT core.set_data_scope(
--     'tenant-a-uuid'::uuid,
--     ARRAY[]::text[],
--     true
-- );
-- SELECT * FROM core.sensor_data;  -- 모든 데이터 반환
--
-- -- DataScope 초기화
-- SELECT core.clear_data_scope();

-- ============================================
-- 9. 권한 부여 (Application 사용자용)
-- ============================================

-- Application 사용자 권한 부여 (triflow_app 사용자가 있다고 가정)
-- GRANT EXECUTE ON FUNCTION core.set_current_tenant(UUID) TO triflow_app;
-- GRANT EXECUTE ON FUNCTION core.set_data_scope(UUID, TEXT[], BOOLEAN) TO triflow_app;
-- GRANT EXECUTE ON FUNCTION core.clear_data_scope() TO triflow_app;

-- ============================================
-- 완료
-- ============================================

-- RLS 정책 목록 확인
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE schemaname = 'core'
ORDER BY tablename, policyname;

COMMENT ON POLICY sensor_data_tenant_isolation ON core.sensor_data IS
'Tenant 격리: 각 테넌트는 자신의 데이터만 접근 가능';

COMMENT ON POLICY sensor_data_line_scope ON core.sensor_data IS
'Line Code 스코프: 사용자의 data_scope.line_codes에 포함된 라인만 조회 가능';

SELECT 'Advanced DataScope RLS Policies installed successfully!' AS status;
