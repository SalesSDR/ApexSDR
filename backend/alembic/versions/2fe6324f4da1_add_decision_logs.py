"""add decision logs

Revision ID: 2fe6324f4da1
Revises: 843af22da15f
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fe6324f4da1'
down_revision: Union[str, Sequence[str], None] = '843af22da15f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'decision_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('prospect_id', sa.String(length=36), nullable=False),
        sa.Column('decision_type', sa.Enum(
            'WAIT', 'SEND_LINKEDIN', 'SEND_FOLLOWUP', 'SEND_EMAIL', 'SCHEDULE_CALL',
            'RETRY_LATER', 'BOOK_MEETING', 'MARK_QUALIFIED', 'MARK_DISQUALIFIED', 'END_SEQUENCE',
            name='decisiontype',
        ), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('prospect_status_at_decision', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_decision_logs_prospect_id'), 'decision_logs', ['prospect_id'], unique=False)
    op.create_index(op.f('ix_decision_logs_created_at'), 'decision_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_decision_logs_tenant_id'), 'decision_logs', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_decision_logs_tenant_id'), table_name='decision_logs')
    op.drop_index(op.f('ix_decision_logs_created_at'), table_name='decision_logs')
    op.drop_index(op.f('ix_decision_logs_prospect_id'), table_name='decision_logs')
    op.drop_table('decision_logs')
    # autogenerate's drop_table doesn't drop the native enum type it created;
    # do so explicitly or a later upgrade fails with "type already exists"
    # (same recurring issue as the Module 1/2 migrations).
    sa.Enum(name='decisiontype').drop(op.get_bind(), checkfirst=True)
