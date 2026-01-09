# -*- coding: utf-8 -*-
"""011 Sample Curation Infrastructure

Revision ID: 011_sample_curation
Revises: 010_canary_deployment
Create Date: 2026-01-09

- Sample 테이블 (학습 샘플)
- GoldenSampleSet 테이블 (골든 샘플셋)
- GoldenSampleSetMember 테이블 (N:M 연결)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '011_sample_curation'
down_revision: Union[str, None] = '010_canary_deployment'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # 1. Sample 테이블 (학습 샘플)
    # ============================================
    op.execute("""
        CREATE TABLE core.samples (
            sample_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

            -- 출처 정보
            feedback_id UUID REFERENCES core.feedback_logs(feedback_id) ON DELETE SET NULL,
            execution_id UUID REFERENCES core.judgment_executions(execution_id) ON DELETE SET NULL,
            source_type VARCHAR(20) NOT NULL,  -- feedback, validation, manual

            -- 샘플 데이터
            category VARCHAR(50) NOT NULL,  -- threshold_adjustment, field_correction, validation_failure
            input_data JSONB NOT NULL,
            expected_output JSONB NOT NULL,
            context JSONB DEFAULT '{}' NOT NULL,

            -- 품질 지표
            quality_score NUMERIC(5, 4) DEFAULT 0.0 NOT NULL,  -- 0.0000 ~ 1.0000
            confidence NUMERIC(5, 4) DEFAULT 0.0 NOT NULL,

            -- 중복 제거용 해시 (MD5)
            content_hash VARCHAR(32) NOT NULL,

            -- 상태
            status VARCHAR(20) DEFAULT 'pending' NOT NULL,  -- pending, approved, rejected, archived
            rejection_reason TEXT,

            -- 타임스탬프
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
            approved_at TIMESTAMP,
            approved_by UUID REFERENCES core.users(user_id) ON DELETE SET NULL,

            -- 제약조건
            CONSTRAINT ck_samples_source_type
                CHECK (source_type IN ('feedback', 'validation', 'manual')),
            CONSTRAINT ck_samples_status
                CHECK (status IN ('pending', 'approved', 'rejected', 'archived')),
            CONSTRAINT ck_samples_quality_score
                CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
            CONSTRAINT ck_samples_confidence
                CHECK (confidence >= 0.0 AND confidence <= 1.0)
        )
    """)

    # 인덱스
    op.execute("""
        CREATE INDEX idx_samples_tenant_category
        ON core.samples(tenant_id, category)
    """)
    op.execute("""
        CREATE INDEX idx_samples_tenant_status
        ON core.samples(tenant_id, status)
    """)
    op.execute("""
        CREATE INDEX idx_samples_content_hash
        ON core.samples(content_hash)
    """)
    op.execute("""
        CREATE INDEX idx_samples_quality_score
        ON core.samples(tenant_id, quality_score DESC)
    """)
    op.execute("""
        CREATE UNIQUE INDEX idx_samples_unique_content
        ON core.samples(tenant_id, content_hash)
    """)
    op.execute("""
        CREATE INDEX idx_samples_feedback
        ON core.samples(feedback_id)
        WHERE feedback_id IS NOT NULL
    """)

    op.execute("COMMENT ON TABLE core.samples IS 'Learning samples extracted from feedback and validation data'")

    # ============================================
    # 2. GoldenSampleSet 테이블 (골든 샘플셋)
    # ============================================
    op.execute("""
        CREATE TABLE core.golden_sample_sets (
            set_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,

            name VARCHAR(100) NOT NULL,
            description TEXT,
            category VARCHAR(50),  -- 특정 카테고리로 제한 (NULL이면 전체)

            -- 설정
            min_quality_score NUMERIC(5, 4) DEFAULT 0.7 NOT NULL,  -- 최소 품질 점수
            max_samples INTEGER DEFAULT 1000 NOT NULL,  -- 최대 샘플 수
            auto_update BOOLEAN DEFAULT TRUE NOT NULL,  -- 자동 업데이트 여부

            -- 메타데이터
            config JSONB DEFAULT '{}' NOT NULL,  -- 추가 설정

            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
            created_by UUID REFERENCES core.users(user_id) ON DELETE SET NULL,

            -- 제약조건
            CONSTRAINT ck_golden_sample_sets_min_quality
                CHECK (min_quality_score >= 0.0 AND min_quality_score <= 1.0),
            CONSTRAINT ck_golden_sample_sets_max_samples
                CHECK (max_samples > 0 AND max_samples <= 100000)
        )
    """)

    # 인덱스
    op.execute("""
        CREATE INDEX idx_golden_sample_sets_tenant
        ON core.golden_sample_sets(tenant_id, is_active)
    """)
    op.execute("""
        CREATE INDEX idx_golden_sample_sets_category
        ON core.golden_sample_sets(tenant_id, category)
        WHERE category IS NOT NULL
    """)

    op.execute("COMMENT ON TABLE core.golden_sample_sets IS 'Curated sets of high-quality learning samples'")

    # ============================================
    # 3. GoldenSampleSetMember 테이블 (N:M 연결)
    # ============================================
    op.execute("""
        CREATE TABLE core.golden_sample_set_members (
            set_id UUID NOT NULL REFERENCES core.golden_sample_sets(set_id) ON DELETE CASCADE,
            sample_id UUID NOT NULL REFERENCES core.samples(sample_id) ON DELETE CASCADE,
            added_at TIMESTAMP DEFAULT NOW() NOT NULL,
            added_by UUID REFERENCES core.users(user_id) ON DELETE SET NULL,

            PRIMARY KEY (set_id, sample_id)
        )
    """)

    # 인덱스
    op.execute("""
        CREATE INDEX idx_golden_sample_set_members_sample
        ON core.golden_sample_set_members(sample_id)
    """)

    op.execute("COMMENT ON TABLE core.golden_sample_set_members IS 'Many-to-many relationship between golden sample sets and samples'")

    # ============================================
    # 4. updated_at 자동 업데이트 트리거
    # ============================================
    op.execute("""
        CREATE OR REPLACE FUNCTION core.update_samples_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER trg_samples_updated_at
        BEFORE UPDATE ON core.samples
        FOR EACH ROW EXECUTE FUNCTION core.update_samples_updated_at()
    """)

    op.execute("""
        CREATE TRIGGER trg_golden_sample_sets_updated_at
        BEFORE UPDATE ON core.golden_sample_sets
        FOR EACH ROW EXECUTE FUNCTION core.update_samples_updated_at()
    """)

    # ============================================
    # 5. 샘플 통계 뷰
    # ============================================
    op.execute("""
        CREATE OR REPLACE VIEW core.sample_stats_by_category AS
        SELECT
            tenant_id,
            category,
            status,
            COUNT(*) as sample_count,
            AVG(quality_score) as avg_quality_score,
            MIN(quality_score) as min_quality_score,
            MAX(quality_score) as max_quality_score,
            COUNT(*) FILTER (WHERE status = 'approved') as approved_count,
            COUNT(*) FILTER (WHERE status = 'pending') as pending_count
        FROM core.samples
        GROUP BY tenant_id, category, status
    """)

    op.execute("COMMENT ON VIEW core.sample_stats_by_category IS 'Aggregated sample statistics by category and status'")


def downgrade() -> None:
    # 뷰 삭제
    op.execute("DROP VIEW IF EXISTS core.sample_stats_by_category")

    # 트리거 삭제
    op.execute("DROP TRIGGER IF EXISTS trg_golden_sample_sets_updated_at ON core.golden_sample_sets")
    op.execute("DROP TRIGGER IF EXISTS trg_samples_updated_at ON core.samples")
    op.execute("DROP FUNCTION IF EXISTS core.update_samples_updated_at()")

    # 테이블 삭제 (역순)
    op.execute("DROP TABLE IF EXISTS core.golden_sample_set_members CASCADE")
    op.execute("DROP TABLE IF EXISTS core.golden_sample_sets CASCADE")
    op.execute("DROP TABLE IF EXISTS core.samples CASCADE")
