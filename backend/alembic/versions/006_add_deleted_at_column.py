# -*- coding: utf-8 -*-
"""006 Add deleted_at column to tenants

Revision ID: 006_add_deleted_at
Revises: 005_tenant_modules
Create Date: 2026-01-06

Add soft delete support to tenants table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_deleted_at'
down_revision: Union[str, None] = '005_tenant_modules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add deleted_at column to tenants table
    op.add_column(
        'tenants',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        schema='core'
    )


def downgrade() -> None:
    op.drop_column('tenants', 'deleted_at', schema='core')
