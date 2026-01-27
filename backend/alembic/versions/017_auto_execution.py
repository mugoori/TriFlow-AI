# -*- coding: utf-8 -*-
"""Auto Execution 테이블 생성

Revision ID: 017_auto_execution
Revises: 016_checkpoints
Create Date: 2026-01-27

Auto Execution 시스템 테이블:
- decision_matrix: Trust Level × Risk Level → 실행 결정 매핑
- action_risk_definitions: 작업 유형별 위험도 정의
- auto_execution_logs: 자동 실행 이력 로깅
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '017_auto_execution'
down_revision = '016_checkpoints'
branch_labels = None
depends_on = None


def upgrade():
    """Auto Execution 테이블 생성"""

    # 1. decision_matrix 테이블
    # Trust Level과 Risk Level 조합에 따른 실행 결정 매핑
    op.create_table(
        'decision_matrix',
        sa.Column('matrix_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('core.tenants.tenant_id', ondelete='CASCADE'), nullable=False),

        # 조건: Trust Level (0-3) × Risk Level (LOW, MEDIUM, HIGH, CRITICAL)
        sa.Column('trust_level', sa.Integer, nullable=False),
        sa.Column('risk_level', sa.String(20), nullable=False),

        # 결정: auto_execute, require_approval, reject
        sa.Column('decision', sa.String(30), nullable=False),

        # 추가 조건 (선택적)
        sa.Column('min_trust_score', sa.Numeric(5, 4), nullable=True),  # 최소 Trust Score
        sa.Column('max_consecutive_failures', sa.Integer, nullable=True),  # 최대 연속 실패 허용
        sa.Column('require_recent_success', sa.Boolean, default=False),  # 최근 성공 필요 여부
        sa.Column('cooldown_seconds', sa.Integer, nullable=True),  # 재실행 대기 시간

        # 메타데이터
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('matrix_metadata', JSONB, nullable=True, server_default='{}'),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),

        # 타임스탬프
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('core.users.user_id'), nullable=True),

        # 제약조건
        sa.CheckConstraint("trust_level >= 0 AND trust_level <= 3", name="ck_decision_matrix_trust_level"),
        sa.CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_decision_matrix_risk_level"),
        sa.CheckConstraint("decision IN ('auto_execute', 'require_approval', 'reject')", name="ck_decision_matrix_decision"),
        sa.UniqueConstraint('tenant_id', 'trust_level', 'risk_level', name='uq_decision_matrix_tenant_levels'),

        schema='core'
    )

    # 인덱스 생성
    op.create_index(
        'idx_decision_matrix_tenant_active',
        'decision_matrix',
        ['tenant_id', 'is_active'],
        schema='core'
    )

    # 2. action_risk_definitions 테이블
    # 작업 유형별 위험도 정의
    op.create_table(
        'action_risk_definitions',
        sa.Column('risk_def_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('core.tenants.tenant_id', ondelete='CASCADE'), nullable=False),

        # 작업 식별
        sa.Column('action_type', sa.String(100), nullable=False),  # 작업 유형 (예: mes_parameter_change, erp_order_create)
        sa.Column('action_pattern', sa.String(255), nullable=True),  # 패턴 매칭 (예: mes_* → 모든 MES 작업)
        sa.Column('category', sa.String(50), nullable=True),  # 카테고리 (mes, erp, notification, data)

        # 위험도 정의
        sa.Column('risk_level', sa.String(20), nullable=False),  # LOW, MEDIUM, HIGH, CRITICAL
        sa.Column('risk_score', sa.Integer, nullable=True),  # 0-100 점수 (세부 분류용)

        # 위험 요소
        sa.Column('reversible', sa.Boolean, default=True),  # 되돌릴 수 있는 작업인지
        sa.Column('affects_production', sa.Boolean, default=False),  # 생산에 영향을 미치는지
        sa.Column('affects_finance', sa.Boolean, default=False),  # 재무에 영향을 미치는지
        sa.Column('affects_compliance', sa.Boolean, default=False),  # 컴플라이언스 관련인지

        # 메타데이터
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('risk_factors', JSONB, nullable=True, server_default='{}'),  # 위험 요소 상세
        sa.Column('mitigation_notes', sa.Text, nullable=True),  # 위험 완화 방법
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),

        # 우선순위 (패턴 매칭 시 우선순위)
        sa.Column('priority', sa.Integer, default=100, nullable=False),

        # 타임스탬프
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),

        # 제약조건
        sa.CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_action_risk_risk_level"),
        sa.UniqueConstraint('tenant_id', 'action_type', name='uq_action_risk_tenant_type'),

        schema='core'
    )

    # 인덱스 생성
    op.create_index(
        'idx_action_risk_tenant_type',
        'action_risk_definitions',
        ['tenant_id', 'action_type'],
        schema='core'
    )

    op.create_index(
        'idx_action_risk_tenant_category',
        'action_risk_definitions',
        ['tenant_id', 'category'],
        schema='core'
    )

    # 3. auto_execution_logs 테이블
    # 자동 실행 이력 로깅
    op.create_table(
        'auto_execution_logs',
        sa.Column('log_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('core.tenants.tenant_id', ondelete='CASCADE'), nullable=False),

        # 실행 컨텍스트
        sa.Column('workflow_id', UUID(as_uuid=True), sa.ForeignKey('core.workflows.workflow_id', ondelete='SET NULL'), nullable=True),
        sa.Column('instance_id', UUID(as_uuid=True), nullable=True),
        sa.Column('node_id', sa.String(255), nullable=True),
        sa.Column('ruleset_id', UUID(as_uuid=True), sa.ForeignKey('core.rulesets.ruleset_id', ondelete='SET NULL'), nullable=True),

        # 실행 정보
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('action_params', JSONB, nullable=True),  # 실행 파라미터

        # Trust/Risk 평가 결과
        sa.Column('trust_level', sa.Integer, nullable=False),
        sa.Column('trust_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False),
        sa.Column('risk_score', sa.Integer, nullable=True),

        # 결정 및 결과
        sa.Column('decision', sa.String(30), nullable=False),  # auto_execute, require_approval, reject
        sa.Column('decision_reason', sa.Text, nullable=True),
        sa.Column('execution_status', sa.String(30), nullable=False),  # pending, executed, approved, rejected, failed
        sa.Column('execution_result', JSONB, nullable=True),  # 실행 결과

        # 승인 관련 (require_approval인 경우)
        sa.Column('approval_id', UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by', UUID(as_uuid=True), sa.ForeignKey('core.users.user_id'), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),

        # 에러 정보
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_details', JSONB, nullable=True),

        # 메타데이터
        sa.Column('execution_metadata', JSONB, nullable=True, server_default='{}'),
        sa.Column('latency_ms', sa.Integer, nullable=True),  # 실행 소요 시간

        # 타임스탬프
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('executed_at', sa.DateTime, nullable=True),

        # 제약조건
        sa.CheckConstraint("trust_level >= 0 AND trust_level <= 3", name="ck_auto_exec_log_trust_level"),
        sa.CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_auto_exec_log_risk_level"),
        sa.CheckConstraint(
            "decision IN ('auto_execute', 'require_approval', 'reject')",
            name="ck_auto_exec_log_decision"
        ),
        sa.CheckConstraint(
            "execution_status IN ('pending', 'executed', 'approved', 'rejected', 'failed', 'skipped')",
            name="ck_auto_exec_log_status"
        ),

        schema='core'
    )

    # 인덱스 생성
    op.create_index(
        'idx_auto_exec_log_tenant_created',
        'auto_execution_logs',
        ['tenant_id', 'created_at'],
        schema='core'
    )

    op.create_index(
        'idx_auto_exec_log_ruleset',
        'auto_execution_logs',
        ['ruleset_id', 'created_at'],
        schema='core'
    )

    op.create_index(
        'idx_auto_exec_log_workflow',
        'auto_execution_logs',
        ['workflow_id', 'instance_id'],
        schema='core'
    )

    op.create_index(
        'idx_auto_exec_log_status',
        'auto_execution_logs',
        ['execution_status', 'created_at'],
        schema='core'
    )


def downgrade():
    """테이블 삭제"""
    # auto_execution_logs 인덱스 및 테이블 삭제
    op.drop_index('idx_auto_exec_log_status', table_name='auto_execution_logs', schema='core')
    op.drop_index('idx_auto_exec_log_workflow', table_name='auto_execution_logs', schema='core')
    op.drop_index('idx_auto_exec_log_ruleset', table_name='auto_execution_logs', schema='core')
    op.drop_index('idx_auto_exec_log_tenant_created', table_name='auto_execution_logs', schema='core')
    op.drop_table('auto_execution_logs', schema='core')

    # action_risk_definitions 인덱스 및 테이블 삭제
    op.drop_index('idx_action_risk_tenant_category', table_name='action_risk_definitions', schema='core')
    op.drop_index('idx_action_risk_tenant_type', table_name='action_risk_definitions', schema='core')
    op.drop_table('action_risk_definitions', schema='core')

    # decision_matrix 인덱스 및 테이블 삭제
    op.drop_index('idx_decision_matrix_tenant_active', table_name='decision_matrix', schema='core')
    op.drop_table('decision_matrix', schema='core')
