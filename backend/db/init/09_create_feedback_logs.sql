-- ===================================
-- TriFlow AI - Feedback Logs Migration
-- 기존 DB에 core.feedback_logs 테이블 추가
-- ===================================

SET search_path TO core, public;

-- 피드백 로그 테이블 생성 (없을 경우)
CREATE TABLE IF NOT EXISTS feedback_logs (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    judgment_execution_id UUID REFERENCES judgment_executions(execution_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id),
    feedback_type VARCHAR(50) NOT NULL,  -- positive, negative, correction
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    corrected_result VARCHAR(20) CHECK (corrected_result IN ('normal', 'warning', 'critical')),
    original_output JSONB,
    corrected_output JSONB,
    context_data JSONB DEFAULT '{}',
    is_processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_feedback_type CHECK (
        feedback_type IN ('correct', 'incorrect', 'partial', 'helpful', 'not_helpful', 'positive', 'negative', 'correction')
    )
);

-- 인덱스 생성 (없을 경우)
CREATE INDEX IF NOT EXISTS idx_feedback_logs_tenant ON feedback_logs(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_logs_type ON feedback_logs(feedback_type, is_processed);

-- 코멘트
COMMENT ON TABLE feedback_logs IS '사용자 피드백 로그 (Learning System용)';

-- 확인 메시지
DO $$
BEGIN
    RAISE NOTICE 'feedback_logs 테이블이 core 스키마에 생성되었습니다.';
END $$;
