# -*- coding: utf-8 -*-
"""010 Canary Deployment Infrastructure

Revision ID: 010_canary_deployment
Revises: 009_fix_materialized_views
Create Date: 2026-01-09

- RuleDeployment 확장 (canary_config, compensation_strategy 등)
- CanaryAssignment 테이블 (Sticky Session)
- DeploymentMetrics 테이블 (v1/v2 비교 메트릭)
- CanaryExecutionLog 테이블 (Canary 기간 실행 로그 격리)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '010_canary_deployment'
down_revision: Union[str, None] = '009_fix_materialized_views'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # 1. RuleDeployment 테이블 확장
    # ============================================

    # canary_config: Canary 설정 (auto_rollback_enabled, min_samples 등)
    op.add_column(
        'rule_deployments',
        sa.Column('canary_config', JSONB, server_default='{}', nullable=False),
        schema='core'
    )

    # started_at: Canary 시작 시점
    op.add_column(
        'rule_deployments',
        sa.Column('started_at', sa.DateTime, nullable=True),
        schema='core'
    )

    # promoted_at: 100% 승격 시점
    op.add_column(
        'rule_deployments',
        sa.Column('promoted_at', sa.DateTime, nullable=True),
        schema='core'
    )

    # rollback_reason: 롤백 사유 (자동/수동)
    op.add_column(
        'rule_deployments',
        sa.Column('rollback_reason', sa.Text, nullable=True),
        schema='core'
    )

    # compensation_strategy: 롤백 시 데이터 처리 전략
    op.add_column(
        'rule_deployments',
        sa.Column(
            'compensation_strategy',
            sa.String(50),
            server_default='ignore',
            nullable=False
        ),
        schema='core'
    )

    # compensation_strategy 체크 제약
    op.execute("""
        ALTER TABLE core.rule_deployments
        ADD CONSTRAINT ck_rule_deployments_compensation_strategy
        CHECK (compensation_strategy IN ('ignore', 'mark_and_reprocess', 'soft_delete'))
    """)

    # ============================================
    # 2. CanaryAssignment 테이블 (Sticky Session)
    # ============================================
    op.execute("""
        CREATE TABLE core.canary_assignments (
            assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
            deployment_id UUID NOT NULL REFERENCES core.rule_deployments(deployment_id) ON DELETE CASCADE,

            -- 식별자: user_id, session_id, workflow_instance_id
            identifier VARCHAR(255) NOT NULL,
            identifier_type VARCHAR(30) NOT NULL,  -- 'user', 'session', 'workflow_instance'

            -- 할당된 버전
            assigned_version VARCHAR(10) NOT NULL,  -- 'v1' (stable), 'v2' (canary)

            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            expires_at TIMESTAMP,  -- NULL이면 만료 없음 (workflow_instance)

            CONSTRAINT ck_canary_assignments_identifier_type
                CHECK (identifier_type IN ('user', 'session', 'workflow_instance')),
            CONSTRAINT ck_canary_assignments_version
                CHECK (assigned_version IN ('v1', 'v2')),
            CONSTRAINT uq_canary_assignments_deployment_identifier
                UNIQUE (deployment_id, identifier)
        )
    """)

    # 인덱스
    op.execute("""
        CREATE INDEX idx_canary_assignments_tenant_deployment
        ON core.canary_assignments(tenant_id, deployment_id)
    """)
    op.execute("""
        CREATE INDEX idx_canary_assignments_expires
        ON core.canary_assignments(expires_at)
        WHERE expires_at IS NOT NULL
    """)

    op.execute("COMMENT ON TABLE core.canary_assignments IS 'Sticky session assignments for canary deployments'")

    # ============================================
    # 3. DeploymentMetrics 테이블 (v1/v2 메트릭)
    # ============================================
    op.execute("""
        CREATE TABLE core.deployment_metrics (
            metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
            deployment_id UUID NOT NULL REFERENCES core.rule_deployments(deployment_id) ON DELETE CASCADE,

            -- 버전 타입
            version_type VARCHAR(10) NOT NULL,  -- 'canary' (v2), 'stable' (v1)

            -- 집계 통계
            sample_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            error_rate NUMERIC(5, 4) NOT NULL DEFAULT 0,  -- 0.0000 ~ 1.0000

            -- 레이턴시 (밀리초)
            latency_p50_ms INTEGER,
            latency_p95_ms INTEGER,
            latency_p99_ms INTEGER,
            latency_avg_ms INTEGER,

            -- 연속 실패 카운터 (Circuit Breaker용)
            consecutive_failures INTEGER NOT NULL DEFAULT 0,

            -- 시간 윈도우
            window_start TIMESTAMP NOT NULL,
            window_end TIMESTAMP NOT NULL,

            created_at TIMESTAMP DEFAULT NOW() NOT NULL,

            CONSTRAINT ck_deployment_metrics_version_type
                CHECK (version_type IN ('canary', 'stable'))
        )
    """)

    # 인덱스
    op.execute("""
        CREATE INDEX idx_deployment_metrics_deployment_version
        ON core.deployment_metrics(deployment_id, version_type, window_end DESC)
    """)
    op.execute("""
        CREATE INDEX idx_deployment_metrics_window
        ON core.deployment_metrics(window_start, window_end)
    """)

    op.execute("COMMENT ON TABLE core.deployment_metrics IS 'Time-windowed metrics for canary vs stable version comparison'")

    # ============================================
    # 4. CanaryExecutionLog 테이블 (실행 로그 격리)
    # ============================================
    op.execute("""
        CREATE TABLE core.canary_execution_logs (
            log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
            deployment_id UUID NOT NULL REFERENCES core.rule_deployments(deployment_id) ON DELETE CASCADE,

            -- 원본 실행 참조 (JudgmentExecution)
            execution_id UUID,  -- 참조만, FK 없음 (유연성)

            -- 버전 정보
            canary_version VARCHAR(10) NOT NULL,  -- 'v1', 'v2'

            -- 실행 결과
            success BOOLEAN NOT NULL,
            latency_ms INTEGER,
            error_message TEXT,

            -- 롤백 관련
            rollback_safe BOOLEAN DEFAULT TRUE,  -- 롤백 가능 여부
            needs_reprocess BOOLEAN DEFAULT FALSE,  -- 재처리 필요 여부
            reprocessed_at TIMESTAMP,

            -- 메타데이터
            execution_metadata JSONB DEFAULT '{}',

            created_at TIMESTAMP DEFAULT NOW() NOT NULL,

            CONSTRAINT ck_canary_execution_logs_version
                CHECK (canary_version IN ('v1', 'v2'))
        )
    """)

    # 인덱스
    op.execute("""
        CREATE INDEX idx_canary_execution_logs_deployment_version
        ON core.canary_execution_logs(deployment_id, canary_version, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_canary_execution_logs_needs_reprocess
        ON core.canary_execution_logs(deployment_id)
        WHERE needs_reprocess = TRUE
    """)
    op.execute("""
        CREATE INDEX idx_canary_execution_logs_execution
        ON core.canary_execution_logs(execution_id)
        WHERE execution_id IS NOT NULL
    """)

    op.execute("COMMENT ON TABLE core.canary_execution_logs IS 'Isolated execution logs during canary deployment period'")

    # ============================================
    # 5. 만료된 할당 정리 함수
    # ============================================
    op.execute("""
        CREATE OR REPLACE FUNCTION core.cleanup_expired_canary_assignments()
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM core.canary_assignments
            WHERE expires_at IS NOT NULL AND expires_at < NOW();

            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("COMMENT ON FUNCTION core.cleanup_expired_canary_assignments() IS 'Cleanup expired canary session assignments'")


def downgrade() -> None:
    # 함수 삭제
    op.execute("DROP FUNCTION IF EXISTS core.cleanup_expired_canary_assignments()")

    # 테이블 삭제 (역순)
    op.execute("DROP TABLE IF EXISTS core.canary_execution_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS core.deployment_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS core.canary_assignments CASCADE")

    # RuleDeployment 컬럼 삭제
    op.execute("ALTER TABLE core.rule_deployments DROP CONSTRAINT IF EXISTS ck_rule_deployments_compensation_strategy")
    op.drop_column('rule_deployments', 'compensation_strategy', schema='core')
    op.drop_column('rule_deployments', 'rollback_reason', schema='core')
    op.drop_column('rule_deployments', 'promoted_at', schema='core')
    op.drop_column('rule_deployments', 'started_at', schema='core')
    op.drop_column('rule_deployments', 'canary_config', schema='core')
