"""decision_log_qualification_snapshot

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-05 09:00:00.000000

Sprint 6, item 4 (Historical Analytics): decision_logs gains
qualification_level_at_decision and qualification_score_at_decision - a
true point-in-time snapshot of the prospect's priority/score when each
decision was made, rather than analytics joining to Prospect's current
(possibly since-changed) qualification_level. Both nullable/additive: rows
logged before this sprint simply have neither.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # qualificationlevel already exists (created explicitly in a1b2c3d4e5f6)
    # - create_type=False so this doesn't attempt (and fail on) a redundant
    # CREATE TYPE.
    qualification_level_enum = postgresql.ENUM(
        'HOT', 'HIGH', 'MEDIUM', 'LOW', name='qualificationlevel', create_type=False,
    )
    op.add_column(
        'decision_logs',
        sa.Column('qualification_level_at_decision', qualification_level_enum, nullable=True),
    )
    op.add_column('decision_logs', sa.Column('qualification_score_at_decision', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('decision_logs', 'qualification_score_at_decision')
    op.drop_column('decision_logs', 'qualification_level_at_decision')
