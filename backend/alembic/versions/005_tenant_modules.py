"""Tenant module configuration tables

Revision ID: 005_tenant_modules
Revises: 004_v2_trust_fields
Create Date: 2026-01-05

Multi-Tenant Module Configuration:
- module_definitions: 모듈 마스터 데이터
- tenant_modules: 테넌트별 모듈 활성화 설정
- industry_profiles: 산업별 프로필 템플릿
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '005_tenant_modules'
down_revision = '004_v2_trust'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 산업별 프로필 테이블 (먼저 생성 - FK 참조 대상)
    op.create_table(
        'industry_profiles',
        sa.Column('industry_code', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('default_modules', sa.ARRAY(sa.String)),
        sa.Column('default_kpis', sa.ARRAY(sa.String)),
        sa.Column('sample_rulesets', sa.ARRAY(sa.String)),
        sa.Column('icon', sa.String(50)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        schema='core'
    )

    # 2. 모듈 정의 테이블 (마스터 데이터)
    op.create_table(
        'module_definitions',
        sa.Column('module_code', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('icon', sa.String(50)),
        sa.Column('default_enabled', sa.Boolean, server_default='false'),
        sa.Column('requires_subscription', sa.String(50)),
        sa.Column('depends_on', sa.ARRAY(sa.String)),
        sa.Column('config_schema', JSONB),
        sa.Column('display_order', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "category IN ('core', 'feature', 'industry')",
            name='ck_module_definitions_category'
        ),
        schema='core'
    )

    # 3. 테넌트별 모듈 설정 테이블
    op.create_table(
        'tenant_modules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('core.tenants.tenant_id', ondelete='CASCADE'), nullable=False),
        sa.Column('module_code', sa.String(50), sa.ForeignKey('core.module_definitions.module_code', ondelete='CASCADE'), nullable=False),
        sa.Column('is_enabled', sa.Boolean, server_default='true'),
        sa.Column('config', JSONB, server_default='{}'),
        sa.Column('enabled_at', sa.DateTime),
        sa.Column('disabled_at', sa.DateTime),
        sa.Column('enabled_by', UUID(as_uuid=True), sa.ForeignKey('core.users.user_id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'module_code', name='uq_tenant_module'),
        schema='core'
    )

    # 4. 인덱스 생성
    op.create_index('idx_tenant_modules_tenant', 'tenant_modules', ['tenant_id'], schema='core')
    op.create_index('idx_tenant_modules_enabled', 'tenant_modules', ['tenant_id', 'is_enabled'], schema='core')
    op.create_index('idx_module_definitions_category', 'module_definitions', ['category'], schema='core')

    # 5. tenants 테이블에 industry_code 컬럼 추가
    op.add_column('tenants', sa.Column('industry_code', sa.String(50)), schema='core')
    op.create_foreign_key(
        'fk_tenant_industry',
        'tenants', 'industry_profiles',
        ['industry_code'], ['industry_code'],
        source_schema='core', referent_schema='core',
        ondelete='SET NULL'
    )

    # 6. 초기 데이터 삽입 - Industry Profiles
    op.execute("""
        INSERT INTO core.industry_profiles (industry_code, name, description, default_modules, default_kpis, sample_rulesets, icon) VALUES
        ('general', '일반 제조', '범용 제조업 프로필', ARRAY['dashboard', 'chat', 'workflows', 'data', 'settings'], ARRAY['defect_rate', 'yield_rate', 'downtime', 'oee'], ARRAY[]::varchar[], 'Factory'),
        ('pharma', '제약/화학', '제약, 화학, 바이오 산업 프로필', ARRAY['dashboard', 'chat', 'rulesets', 'quality_pharma', 'learning', 'data', 'settings'], ARRAY['batch_yield', 'mixing_ratio', 'contamination_rate', 'sterility_pass_rate'], ARRAY['pharma_mixing_check', 'pharma_temp_humidity_control', 'pharma_batch_release'], 'Pill'),
        ('food', '식품/발효', '식품, 음료, 발효 산업 프로필', ARRAY['dashboard', 'chat', 'rulesets', 'quality_food', 'data', 'settings'], ARRAY['fermentation_level', 'salinity', 'ph_level', 'moisture_content'], ARRAY['food_salinity_check', 'food_fermentation_control', 'food_haccp_monitoring'], 'UtensilsCrossed'),
        ('electronics', '전자/반도체', '전자, 반도체, PCB 산업 프로필', ARRAY['dashboard', 'chat', 'workflows', 'quality_elec', 'experiments', 'data', 'settings'], ARRAY['defect_rate', 'yield_rate', 'cycle_time', 'first_pass_yield'], ARRAY['elec_defect_detection', 'elec_aoi_check', 'elec_solder_quality'], 'Cpu')
    """)

    # 7. 초기 데이터 삽입 - Module Definitions
    op.execute("""
        INSERT INTO core.module_definitions (module_code, name, description, category, icon, default_enabled, requires_subscription, display_order) VALUES
        -- Core 모듈 (항상 포함)
        ('dashboard', '대시보드', '핵심 지표 및 현황 대시보드', 'core', 'LayoutDashboard', true, NULL, 1),
        ('chat', 'AI Chat', 'AI 어시스턴트와 대화', 'core', 'MessageSquare', true, NULL, 2),
        ('data', '데이터 관리', 'ERP/MES/센서 데이터 관리', 'core', 'Database', true, NULL, 7),
        ('settings', '설정', '시스템 설정 관리', 'core', 'Settings', true, NULL, 10),

        -- Feature 모듈 (구독 플랜에 따라)
        ('workflows', '워크플로우', '자동화 워크플로우 관리', 'feature', 'GitBranch', true, NULL, 3),
        ('rulesets', '판단 규칙', 'Rhai 스크립트 기반 규칙 관리', 'feature', 'FileCode', false, 'standard', 4),
        ('experiments', 'A/B 실험', '규칙 A/B 테스트 관리', 'feature', 'FlaskConical', false, 'enterprise', 5),
        ('learning', '학습', 'AI 학습 및 규칙 자동 생성', 'feature', 'GraduationCap', false, 'enterprise', 6),

        -- Industry 모듈 (도메인 특화)
        ('quality_pharma', '품질관리 (제약)', '제약 산업 특화 품질 관리', 'industry', 'Pill', false, NULL, 100),
        ('quality_food', '품질관리 (식품)', '식품 산업 특화 품질 관리', 'industry', 'UtensilsCrossed', false, NULL, 101),
        ('quality_elec', '품질관리 (전자)', '전자 산업 특화 품질 관리', 'industry', 'Cpu', false, NULL, 102)
    """)

    # 8. 기존 테넌트에 기본 모듈 활성화 (general 프로필)
    op.execute("""
        INSERT INTO core.tenant_modules (tenant_id, module_code, is_enabled, enabled_at)
        SELECT t.tenant_id, m.module_code, true, NOW()
        FROM core.tenants t
        CROSS JOIN core.module_definitions m
        WHERE m.default_enabled = true
        AND NOT EXISTS (
            SELECT 1 FROM core.tenant_modules tm
            WHERE tm.tenant_id = t.tenant_id AND tm.module_code = m.module_code
        )
    """)

    # 9. 기존 테넌트에 general 프로필 적용
    op.execute("""
        UPDATE core.tenants
        SET industry_code = 'general'
        WHERE industry_code IS NULL
    """)


def downgrade():
    # 역순으로 삭제
    op.execute("DELETE FROM core.tenant_modules")
    op.execute("DELETE FROM core.module_definitions")
    op.execute("DELETE FROM core.industry_profiles")

    op.drop_constraint('fk_tenant_industry', 'tenants', schema='core', type_='foreignkey')
    op.drop_column('tenants', 'industry_code', schema='core')

    op.drop_index('idx_module_definitions_category', table_name='module_definitions', schema='core')
    op.drop_index('idx_tenant_modules_enabled', table_name='tenant_modules', schema='core')
    op.drop_index('idx_tenant_modules_tenant', table_name='tenant_modules', schema='core')

    op.drop_table('tenant_modules', schema='core')
    op.drop_table('module_definitions', schema='core')
    op.drop_table('industry_profiles', schema='core')
