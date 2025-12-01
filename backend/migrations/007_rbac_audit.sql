-- V1 Sprint 4: RBAC & Audit Log
-- 역할 기반 접근 제어 및 감사 로그 테이블

-- ============================================
-- 1. Permission 테이블 (권한 정의)
-- ============================================
CREATE TABLE IF NOT EXISTS core.permissions (
    permission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    resource VARCHAR(100) NOT NULL,  -- 리소스 (workflows, rulesets, sensors, etc.)
    action VARCHAR(50) NOT NULL,      -- 액션 (create, read, update, delete, execute)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- 2. Role-Permission 매핑 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS core.role_permissions (
    role VARCHAR(50) NOT NULL,        -- admin, user, viewer
    permission_id UUID NOT NULL REFERENCES core.permissions(permission_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (role, permission_id)
);

-- ============================================
-- 3. Audit Log 테이블 (감사 로그)
-- ============================================
CREATE TABLE IF NOT EXISTS audit.audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES core.users(user_id) ON DELETE SET NULL,
    tenant_id UUID REFERENCES core.tenants(tenant_id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,      -- API 액션 (create, read, update, delete, login, logout)
    resource VARCHAR(100) NOT NULL,   -- 리소스 타입 (workflow, ruleset, sensor, auth)
    resource_id VARCHAR(255),         -- 리소스 ID (있는 경우)
    method VARCHAR(10) NOT NULL,      -- HTTP 메서드 (GET, POST, PUT, DELETE)
    path VARCHAR(500) NOT NULL,       -- API 경로
    status_code INTEGER NOT NULL,     -- HTTP 상태 코드
    ip_address VARCHAR(50),           -- 클라이언트 IP
    user_agent TEXT,                  -- User-Agent 헤더
    request_body JSONB,               -- 요청 본문 (민감 정보 마스킹)
    response_summary TEXT,            -- 응답 요약
    duration_ms INTEGER,              -- 처리 시간 (밀리초)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit.audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit.audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit.audit_logs(resource, action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit.audit_logs(status_code);

-- ============================================
-- 4. 기본 권한 데이터 삽입
-- ============================================

-- Workflows 권한
INSERT INTO core.permissions (name, description, resource, action) VALUES
('workflows:create', '워크플로우 생성', 'workflows', 'create'),
('workflows:read', '워크플로우 조회', 'workflows', 'read'),
('workflows:update', '워크플로우 수정', 'workflows', 'update'),
('workflows:delete', '워크플로우 삭제', 'workflows', 'delete'),
('workflows:execute', '워크플로우 실행', 'workflows', 'execute')
ON CONFLICT (name) DO NOTHING;

-- Rulesets 권한
INSERT INTO core.permissions (name, description, resource, action) VALUES
('rulesets:create', '룰셋 생성', 'rulesets', 'create'),
('rulesets:read', '룰셋 조회', 'rulesets', 'read'),
('rulesets:update', '룰셋 수정', 'rulesets', 'update'),
('rulesets:delete', '룰셋 삭제', 'rulesets', 'delete'),
('rulesets:execute', '룰셋 테스트 실행', 'rulesets', 'execute')
ON CONFLICT (name) DO NOTHING;

-- Sensors 권한
INSERT INTO core.permissions (name, description, resource, action) VALUES
('sensors:read', '센서 데이터 조회', 'sensors', 'read'),
('sensors:write', '센서 데이터 기록', 'sensors', 'write')
ON CONFLICT (name) DO NOTHING;

-- Experiments 권한
INSERT INTO core.permissions (name, description, resource, action) VALUES
('experiments:create', '실험 생성', 'experiments', 'create'),
('experiments:read', '실험 조회', 'experiments', 'read'),
('experiments:update', '실험 수정', 'experiments', 'update'),
('experiments:delete', '실험 삭제', 'experiments', 'delete'),
('experiments:execute', '실험 실행', 'experiments', 'execute')
ON CONFLICT (name) DO NOTHING;

-- Users 권한 (관리자 전용)
INSERT INTO core.permissions (name, description, resource, action) VALUES
('users:create', '사용자 생성', 'users', 'create'),
('users:read', '사용자 조회', 'users', 'read'),
('users:update', '사용자 수정', 'users', 'update'),
('users:delete', '사용자 삭제', 'users', 'delete')
ON CONFLICT (name) DO NOTHING;

-- Settings 권한
INSERT INTO core.permissions (name, description, resource, action) VALUES
('settings:read', '설정 조회', 'settings', 'read'),
('settings:update', '설정 수정', 'settings', 'update')
ON CONFLICT (name) DO NOTHING;

-- Audit 권한 (관리자 전용)
INSERT INTO core.permissions (name, description, resource, action) VALUES
('audit:read', '감사 로그 조회', 'audit', 'read')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- 5. 역할별 권한 매핑
-- ============================================

-- Admin: 모든 권한
INSERT INTO core.role_permissions (role, permission_id)
SELECT 'admin', permission_id FROM core.permissions
ON CONFLICT DO NOTHING;

-- User: 생성, 조회, 수정, 실행 (삭제 제외, 사용자/감사 관리 제외)
INSERT INTO core.role_permissions (role, permission_id)
SELECT 'user', permission_id FROM core.permissions
WHERE action IN ('create', 'read', 'update', 'execute')
  AND resource NOT IN ('users', 'audit')
ON CONFLICT DO NOTHING;

-- Viewer: 조회만
INSERT INTO core.role_permissions (role, permission_id)
SELECT 'viewer', permission_id FROM core.permissions
WHERE action = 'read' AND resource NOT IN ('users', 'audit')
ON CONFLICT DO NOTHING;
