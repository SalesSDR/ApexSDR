"""add linkedin accounts

Revision ID: a2ab531ee2c3
Revises: 84ac32dfb7a6
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2ab531ee2c3'
down_revision: Union[str, Sequence[str], None] = '84ac32dfb7a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'linkedin_accounts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('account_id', sa.String(length=100), nullable=False),
        sa.Column('daily_send_count', sa.Integer(), nullable=False),
        sa.Column('daily_count_date', sa.Date(), nullable=False),
        sa.Column('daily_limit', sa.Integer(), nullable=False),
        sa.Column('is_paused', sa.Boolean(), nullable=False),
        sa.Column('paused_reason', sa.String(length=50), nullable=True),
        sa.Column('paused_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_linkedin_accounts_tenant_id'), 'linkedin_accounts', ['tenant_id'], unique=False)
    op.create_index('ix_linkedin_accounts_tenant_account', 'linkedin_accounts', ['tenant_id', 'account_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_linkedin_accounts_tenant_account', table_name='linkedin_accounts')
    op.drop_index(op.f('ix_linkedin_accounts_tenant_id'), table_name='linkedin_accounts')
    op.drop_table('linkedin_accounts')
