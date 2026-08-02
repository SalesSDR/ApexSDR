"""priority_pipeline_and_revenue

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-04 09:00:00.000000

Sprint 5: unblocks the priority-driven, score-aware live pipeline.

1. DecisionType gains PAUSE and HUMAN_REVIEW (item 3) - the qualification
   score and active buying signals can now override a would-be send into
   one of these, instead of the old binary QUALIFIED/DISQUALIFIED gate
   being the only lever.
2. ProspectState gains CLOSED_WON (item 5) - a MEETING_BOOKED deal that
   actually closed, distinct from COMPLETED_DECLINED/LOST (neither of
   which means "won").
3. prospects gains estimated_deal_value (item 5), feeding
   estimated_pipeline_value/meeting_value/won_value/lost_value in
   analytics.

No existing data is modified - only new enum values and one new nullable
column are added. Downgrades of the two enum additions are documented
no-ops (see b1c2d3e4f5a6/c2d3e4f5a6b7 for the same Postgres constraint:
no DROP VALUE, and rewriting rows that may already use the new values
would modify existing data).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE decisiontype ADD VALUE IF NOT EXISTS 'PAUSE'")
    op.execute("ALTER TYPE decisiontype ADD VALUE IF NOT EXISTS 'HUMAN_REVIEW'")
    op.execute("ALTER TYPE prospectstatus ADD VALUE IF NOT EXISTS 'CLOSED_WON'")

    op.add_column('prospects', sa.Column('estimated_deal_value', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('prospects', 'estimated_deal_value')
    # No downgrade for the three added enum values - see
    # b1c2d3e4f5a6's downgrade for why (would require rewriting rows that
    # already use them, which modifies existing data).
