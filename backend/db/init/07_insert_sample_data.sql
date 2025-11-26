-- ===================================
-- TriFlow AI - 샘플 데이터 삽입
-- ===================================

-- 샘플 테넌트
INSERT INTO core.tenants (tenant_id, name, slug, settings)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'Demo Factory', 'demo-factory', '{"timezone": "Asia/Seoul"}')
ON CONFLICT (tenant_id) DO NOTHING;

-- 샘플 사용자
INSERT INTO core.users (user_id, tenant_id, email, username, password_hash, role)
VALUES
    (
        '00000000-0000-0000-0000-000000000101',
        '00000000-0000-0000-0000-000000000001',
        'admin@demo-factory.com',
        'Admin User',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYk9YmxRqWO',  -- password: admin123
        'admin'
    )
ON CONFLICT (email) DO NOTHING;

-- 샘플 Ruleset
INSERT INTO core.rulesets (ruleset_id, tenant_id, name, description, rhai_code, version, is_active, created_by)
VALUES
    (
        '00000000-0000-0000-0000-000000000201',
        '00000000-0000-0000-0000-000000000001',
        'Defect Rate Check',
        '불량률 임계값 체크',
        'let defect_rate = input.defect_count / input.production_count;
if defect_rate > 0.05 {
    #{status: "HIGH_DEFECT", confidence: 0.95}
} else if defect_rate > 0.02 {
    #{status: "WARNING", confidence: 0.80}
} else {
    #{status: "NORMAL", confidence: 0.90}
}',
        'v1.0.0',
        true,
        '00000000-0000-0000-0000-000000000101'
    )
ON CONFLICT (tenant_id, name, version) DO NOTHING;

-- 샘플 Workflow
INSERT INTO core.workflows (workflow_id, tenant_id, name, description, dsl_json, version, is_active, created_by)
VALUES
    (
        '00000000-0000-0000-0000-000000000301',
        '00000000-0000-0000-0000-000000000001',
        'Simple Quality Check',
        '간단한 품질 체크 워크플로우',
        '{
            "nodes": [
                {
                    "id": "node-1",
                    "type": "JUDGMENT",
                    "config": {
                        "ruleset_id": "00000000-0000-0000-0000-000000000201",
                        "policy": "RULE_ONLY"
                    }
                }
            ],
            "edges": []
        }',
        'v1.0.0',
        true,
        '00000000-0000-0000-0000-000000000101'
    )
ON CONFLICT (tenant_id, name, version) DO NOTHING;

-- 샘플 Dashboard
INSERT INTO bi.dashboards (dashboard_id, tenant_id, name, description, is_public, created_by)
VALUES
    (
        '00000000-0000-0000-0000-000000000401',
        '00000000-0000-0000-0000-000000000001',
        'Production Overview',
        '생산 현황 대시보드',
        true,
        '00000000-0000-0000-0000-000000000101'
    )
ON CONFLICT (tenant_id, name) DO NOTHING;

-- 샘플 지식 베이스
INSERT INTO rag.knowledge_base (kb_id, tenant_id, category, question, answer)
VALUES
    (
        '00000000-0000-0000-0000-000000000501',
        '00000000-0000-0000-0000-000000000001',
        'Quality',
        'What is the acceptable defect rate?',
        'The acceptable defect rate is below 2%. Between 2-5% is a warning level, and above 5% is considered high defect.'
    )
ON CONFLICT (kb_id) DO NOTHING;
