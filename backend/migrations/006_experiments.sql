-- Migration: A/B 테스트 실험 테이블 생성
-- Version: 006
-- Date: 2025-12-01

-- Experiments 테이블 (A/B 테스트 실험)
CREATE TABLE IF NOT EXISTS core.experiments (
    experiment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    description TEXT,
    hypothesis TEXT,

    status VARCHAR(50) DEFAULT 'draft',  -- draft, running, paused, completed, cancelled
    start_date TIMESTAMP,
    end_date TIMESTAMP,

    -- 트래픽 할당 설정
    traffic_percentage INTEGER DEFAULT 100,  -- 전체 트래픽 중 실험 참여 비율 (%)

    -- 통계적 유의성 설정
    min_sample_size INTEGER DEFAULT 100,
    confidence_level FLOAT DEFAULT 0.95,

    created_by UUID REFERENCES core.users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Experiment Variants 테이블 (실험 변형)
CREATE TABLE IF NOT EXISTS core.experiment_variants (
    variant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES core.experiments(experiment_id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,  -- control, treatment_a, etc.
    description TEXT,
    is_control BOOLEAN DEFAULT FALSE,

    -- 룰셋 연결
    ruleset_id UUID REFERENCES core.rulesets(ruleset_id) ON DELETE SET NULL,

    -- 트래픽 배분 비율 (실험 내 비율, 합계 100%)
    traffic_weight INTEGER DEFAULT 50,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Experiment Assignments 테이블 (사용자별 그룹 할당)
CREATE TABLE IF NOT EXISTS core.experiment_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES core.experiments(experiment_id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES core.experiment_variants(variant_id) ON DELETE CASCADE,

    -- 할당 대상 (user_id 또는 session_id)
    user_id UUID REFERENCES core.users(user_id) ON DELETE SET NULL,
    session_id VARCHAR(255),

    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 중복 할당 방지
    CONSTRAINT unique_user_experiment UNIQUE (experiment_id, user_id),
    CONSTRAINT unique_session_experiment UNIQUE (experiment_id, session_id)
);

-- Experiment Metrics 테이블 (실험 메트릭)
CREATE TABLE IF NOT EXISTS core.experiment_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES core.experiments(experiment_id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES core.experiment_variants(variant_id) ON DELETE CASCADE,

    metric_name VARCHAR(100) NOT NULL,  -- success_rate, response_time, feedback_score, etc.
    metric_value FLOAT NOT NULL,

    -- 관련 실행 정보
    execution_id UUID REFERENCES core.judgment_executions(execution_id) ON DELETE SET NULL,
    context_data JSONB DEFAULT '{}',

    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_experiments_tenant ON core.experiments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON core.experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiment_variants_experiment ON core.experiment_variants(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_assignments_experiment ON core.experiment_assignments(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_assignments_variant ON core.experiment_assignments(variant_id);
CREATE INDEX IF NOT EXISTS idx_experiment_assignments_user ON core.experiment_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_experiment_metrics_experiment ON core.experiment_metrics(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_metrics_variant ON core.experiment_metrics(variant_id);
CREATE INDEX IF NOT EXISTS idx_experiment_metrics_name ON core.experiment_metrics(metric_name);

-- 업데이트 트리거 (experiments)
CREATE OR REPLACE FUNCTION update_experiments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_experiments_updated_at ON core.experiments;
CREATE TRIGGER trigger_experiments_updated_at
    BEFORE UPDATE ON core.experiments
    FOR EACH ROW
    EXECUTE FUNCTION update_experiments_updated_at();

-- 코멘트
COMMENT ON TABLE core.experiments IS 'A/B 테스트 실험';
COMMENT ON TABLE core.experiment_variants IS '실험 변형 (Control/Treatment 그룹)';
COMMENT ON TABLE core.experiment_assignments IS '사용자별 실험 그룹 할당';
COMMENT ON TABLE core.experiment_metrics IS '실험 메트릭 기록';
