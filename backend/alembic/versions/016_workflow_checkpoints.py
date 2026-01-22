"""Add workflow_checkpoints table

Revision ID: 016_checkpoints
Revises: 013_encrypt_credentials
Create Date: 2026-01-22

Workflow 실행 중 Checkpoint를 영구 저장하여 서버 재시작 후 재개 가능
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '016_checkpoints'
down_revision = '013_encrypt_credentials'
branch_labels = None
depends_on = None


def upgrade():
    """workflow_checkpoints 테이블 생성"""

    # workflow_checkpoints 테이블
    op.create_table(
        'workflow_checkpoints',
        sa.Column('checkpoint_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('instance_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('core.tenants.tenant_id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow_id', UUID(as_uuid=True), sa.ForeignKey('core.workflows.workflow_id', ondelete='CASCADE'), nullable=False),

        # Checkpoint 정보
        sa.Column('node_id', sa.String(255), nullable=False),
        sa.Column('node_name', sa.String(255), nullable=True),
        sa.Column('checkpoint_type', sa.String(50), nullable=False, server_default='manual'),  # manual, auto, error

        # 실행 상태
        sa.Column('state', JSONB, nullable=False),  # 전체 실행 컨텍스트
        sa.Column('completed_nodes', sa.ARRAY(sa.String), nullable=True),  # 완료된 노드 목록
        sa.Column('outputs', JSONB, nullable=True),  # 노드별 출력 결과

        # 메타데이터
        sa.Column('progress_percentage', sa.Integer, nullable=True),  # 진행률 (0-100)
        sa.Column('estimated_remaining_seconds', sa.Integer, nullable=True),
        sa.Column('checkpoint_metadata', JSONB, nullable=True, server_default='{}'),

        # 타임스탬프
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime, nullable=True),  # TTL (7일 후 자동 삭제)

        schema='core'
    )

    # 인덱스 생성
    op.create_index(
        'idx_workflow_checkpoints_instance',
        'workflow_checkpoints',
        ['instance_id', 'created_at'],
        schema='core'
    )

    op.create_index(
        'idx_workflow_checkpoints_tenant',
        'workflow_checkpoints',
        ['tenant_id', 'created_at'],
        schema='core'
    )

    # 만료된 Checkpoint 자동 삭제용 인덱스
    op.create_index(
        'idx_workflow_checkpoints_expires',
        'workflow_checkpoints',
        ['expires_at'],
        schema='core',
        postgresql_where=sa.text('expires_at IS NOT NULL')
    )


def downgrade():
    """테이블 삭제"""
    op.drop_index('idx_workflow_checkpoints_expires', table_name='workflow_checkpoints', schema='core')
    op.drop_index('idx_workflow_checkpoints_tenant', table_name='workflow_checkpoints', schema='core')
    op.drop_index('idx_workflow_checkpoints_instance', table_name='workflow_checkpoints', schema='core')
    op.drop_table('workflow_checkpoints', schema='core')
