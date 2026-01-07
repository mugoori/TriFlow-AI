# -*- coding: utf-8 -*-
"""001 Core Schema Baseline

Revision ID: 001_core_baseline
Revises:
Create Date: 2025-12-26

Core Schema (based on B-3-1 spec)
- Create core schema
- Sync with existing ORM models
- Define all Core tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_core_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # Create Core Schema
    # ============================================
    op.execute("CREATE SCHEMA IF NOT EXISTS core")

    # ============================================
    # 1. Base Tables (tenants, users)
    # ============================================

    # tenants table
    op.create_table(
        'tenants',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('settings', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('subscription_plan', sa.String(20), nullable=False, server_default='standard'),
        sa.Column('max_users', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_workflows', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('max_judgments_per_day', sa.Integer(), nullable=False, server_default='10000'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('industry_code', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id'),
        sa.CheckConstraint("subscription_plan IN ('trial', 'standard', 'enterprise', 'custom')", name='ck_tenants_subscription_plan'),
        sa.CheckConstraint("status IN ('active', 'suspended', 'deleted')", name='ck_tenants_status'),
        schema='core'
    )
    op.create_index('idx_tenants_status', 'tenants', ['status'], schema='core')

    # users table
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, server_default='user'),
        sa.Column('permissions', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('oauth_provider', sa.String(50), nullable=True),
        sa.Column('oauth_provider_id', sa.String(255), nullable=True),
        sa.Column('profile_image_url', sa.String(500), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id'], ondelete='CASCADE'),
        sa.CheckConstraint("role IN ('admin', 'approver', 'operator', 'viewer', 'user')", name='ck_users_role'),
        sa.CheckConstraint("status IN ('active', 'inactive', 'locked')", name='ck_users_status'),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_users_tenant_email'),
        sa.UniqueConstraint('tenant_id', 'username', name='uq_users_tenant_username'),
        schema='core'
    )
    op.create_index('idx_users_tenant_id', 'users', ['tenant_id'], schema='core')
    op.create_index('idx_users_email', 'users', ['email'], schema='core')

    # ============================================
    # 2. Ruleset Tables
    # ============================================

    # rulesets table (Rhai script based rules)
    op.create_table(
        'rulesets',
        sa.Column('ruleset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rhai_code', sa.Text(), nullable=False),
        sa.Column('version', sa.String(50), nullable=True, server_default='1.0.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('target_kpi', sa.String(100), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('ruleset_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['core.users.user_id']),
        sa.CheckConstraint("category IN ('quality', 'production', 'equipment', 'inventory', 'safety')", name='ck_rulesets_category'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_rulesets_tenant_name'),
        schema='core'
    )
    op.create_index('idx_rulesets_tenant_id', 'rulesets', ['tenant_id'], schema='core')
    op.create_index('idx_rulesets_category', 'rulesets', ['category'], schema='core')
    op.create_index('idx_rulesets_is_active', 'rulesets', ['is_active'], schema='core')

    # ruleset_versions table (ruleset version history)
    op.create_table(
        'ruleset_versions',
        sa.Column('version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ruleset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('version_label', sa.String(50), nullable=False),
        sa.Column('rhai_script', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('change_summary', sa.String(500), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('version_id'),
        sa.ForeignKeyConstraint(['ruleset_id'], ['core.rulesets.ruleset_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_ruleset_versions_ruleset', 'ruleset_versions', ['ruleset_id', 'version_number'], schema='core')

    # ============================================
    # 3. Workflow Tables
    # ============================================

    # workflows table
    op.create_table(
        'workflows',
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('definition', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('trigger_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('workflow_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['created_by'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_workflows_tenant_status', 'workflows', ['tenant_id', 'status'], schema='core')

    # workflow_executions table
    op.create_table(
        'workflow_executions',
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('trigger_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('context', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('execution_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['core.workflows.workflow_id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        schema='core'
    )
    op.create_index('idx_workflow_executions_workflow', 'workflow_executions', ['workflow_id', 'created_at'], schema='core')
    op.create_index('idx_workflow_executions_status', 'workflow_executions', ['status'], schema='core')

    # node_executions table
    op.create_table(
        'node_executions',
        sa.Column('node_execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', sa.String(100), nullable=False),
        sa.Column('node_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('input_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('output_data', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('node_execution_id'),
        sa.ForeignKeyConstraint(['execution_id'], ['core.workflow_executions.execution_id']),
        schema='core'
    )
    op.create_index('idx_node_executions_execution', 'node_executions', ['execution_id'], schema='core')

    # ============================================
    # 3. Judgment Tables
    # ============================================

    # judgment_templates table
    op.create_table(
        'judgment_templates',
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('prompt_template', sa.Text(), nullable=False),
        sa.Column('output_schema', postgresql.JSONB(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('template_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['created_by'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_judgment_templates_tenant', 'judgment_templates', ['tenant_id', 'is_active'], schema='core')
    op.create_index('idx_judgment_templates_category', 'judgment_templates', ['category'], schema='core')

    # judgment_executions table
    op.create_table(
        'judgment_executions',
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('input_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('output_data', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('llm_model', sa.String(50), nullable=True),
        sa.Column('llm_tokens_used', sa.Integer(), nullable=True),
        sa.Column('llm_latency_ms', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('executed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('execution_id'),
        sa.ForeignKeyConstraint(['template_id'], ['core.judgment_templates.template_id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['executed_by'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_judgment_executions_template', 'judgment_executions', ['template_id', 'created_at'], schema='core')
    op.create_index('idx_judgment_executions_status', 'judgment_executions', ['status'], schema='core')

    # ============================================
    # 4. Chat Tables
    # ============================================

    # chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('agent_type', sa.String(50), nullable=False, server_default='general'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('session_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['user_id'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_chat_sessions_tenant_user', 'chat_sessions', ['tenant_id', 'user_id'], schema='core')

    # chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('tool_calls', postgresql.JSONB(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('message_id'),
        sa.ForeignKeyConstraint(['session_id'], ['core.chat_sessions.session_id']),
        schema='core'
    )
    op.create_index('idx_chat_messages_session', 'chat_messages', ['session_id', 'created_at'], schema='core')

    # ============================================
    # 5. MCP Tables
    # ============================================

    # mcp_servers table
    op.create_table(
        'mcp_servers',
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('server_type', sa.String(50), nullable=False),
        sa.Column('connection_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('health_status', sa.String(20), nullable=False, server_default='unknown'),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('server_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        schema='core'
    )
    op.create_index('idx_mcp_servers_tenant', 'mcp_servers', ['tenant_id', 'is_active'], schema='core')

    # mcp_tools table
    op.create_table(
        'mcp_tools',
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('input_schema', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('tool_id'),
        sa.ForeignKeyConstraint(['server_id'], ['core.mcp_servers.server_id']),
        schema='core'
    )
    op.create_index('idx_mcp_tools_server', 'mcp_tools', ['server_id'], schema='core')

    # mcp_tool_executions table
    op.create_table(
        'mcp_tool_executions',
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('input_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('output_data', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('executed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('execution_id'),
        sa.ForeignKeyConstraint(['tool_id'], ['core.mcp_tools.tool_id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['executed_by'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_mcp_tool_executions_tool', 'mcp_tool_executions', ['tool_id', 'created_at'], schema='core')

    # ============================================
    # 6. Feedback Table
    # ============================================

    # feedback_logs table
    op.create_table(
        'feedback_logs',
        sa.Column('feedback_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feedback_type', sa.String(50), nullable=False),
        sa.Column('original_output', postgresql.JSONB(), nullable=True),
        sa.Column('corrected_output', postgresql.JSONB(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('context_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('feedback_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        schema='core'
    )
    op.create_index('idx_feedback_logs_tenant', 'feedback_logs', ['tenant_id', 'created_at'], schema='core')
    op.create_index('idx_feedback_logs_type', 'feedback_logs', ['feedback_type'], schema='core')
    op.create_index('idx_feedback_logs_processed', 'feedback_logs', ['is_processed'], schema='core')

    # ============================================
    # 7. Audit Table
    # ============================================

    # audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('old_value', postgresql.JSONB(), nullable=True),
        sa.Column('new_value', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('log_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['user_id'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_audit_logs_tenant', 'audit_logs', ['tenant_id', 'created_at'], schema='core')
    op.create_index('idx_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'], schema='core')

    # ============================================
    # 8. System Configuration Table
    # ============================================

    # system_configs table
    op.create_table(
        'system_configs',
        sa.Column('config_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('config_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        schema='core'
    )
    op.create_index('idx_system_configs_key', 'system_configs', ['key'], schema='core')
    op.create_index('idx_system_configs_tenant', 'system_configs', ['tenant_id'], schema='core')

    # ============================================
    # 9. File Storage Table
    # ============================================

    # files table
    op.create_table(
        'files',
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('storage_type', sa.String(20), nullable=False, server_default='s3'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('file_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['uploaded_by'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_files_tenant', 'files', ['tenant_id', 'created_at'], schema='core')

    # ============================================
    # 10. Notification Table
    # ============================================

    # notifications table
    op.create_table(
        'notifications',
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('notification_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['user_id'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_notifications_user', 'notifications', ['user_id', 'is_read'], schema='core')
    op.create_index('idx_notifications_tenant', 'notifications', ['tenant_id', 'created_at'], schema='core')

    # ============================================
    # 11. API Keys Table
    # ============================================

    # api_keys table
    op.create_table(
        'api_keys',
        sa.Column('key_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('key_prefix', sa.String(10), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('key_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['core.tenants.tenant_id']),
        sa.ForeignKeyConstraint(['user_id'], ['core.users.user_id']),
        schema='core'
    )
    op.create_index('idx_api_keys_tenant', 'api_keys', ['tenant_id'], schema='core')
    op.create_index('idx_api_keys_prefix', 'api_keys', ['key_prefix'], schema='core')


def downgrade() -> None:
    # Drop tables in reverse order (due to foreign key constraints)
    op.drop_table('api_keys', schema='core')
    op.drop_table('notifications', schema='core')
    op.drop_table('files', schema='core')
    op.drop_table('system_configs', schema='core')
    op.drop_table('audit_logs', schema='core')
    op.drop_table('feedback_logs', schema='core')
    op.drop_table('mcp_tool_executions', schema='core')
    op.drop_table('mcp_tools', schema='core')
    op.drop_table('mcp_servers', schema='core')
    op.drop_table('chat_messages', schema='core')
    op.drop_table('chat_sessions', schema='core')
    op.drop_table('judgment_executions', schema='core')
    op.drop_table('judgment_templates', schema='core')
    op.drop_table('node_executions', schema='core')
    op.drop_table('workflow_executions', schema='core')
    op.drop_table('workflows', schema='core')
    op.drop_table('ruleset_versions', schema='core')
    op.drop_table('rulesets', schema='core')
    op.drop_table('users', schema='core')
    op.drop_table('tenants', schema='core')

    # Drop schema
    op.execute("DROP SCHEMA IF EXISTS core CASCADE")
