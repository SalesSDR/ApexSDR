"""decision_log_sequence_number

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-07-31 12:10:00.000000

DecisionLog.created_at uses the ORM default=func.now() - in Postgres,
now()/CURRENT_TIMESTAMP returns the *transaction* start time, not the
statement's actual execution time. When two decisions are recorded for the
same prospect inside one transaction (a common case - e.g. the qualification
task's MARK_QUALIFIED decision followed immediately by the supervisor's
SEND_LINKEDIN decision within the same DB session), both rows get an
identical created_at, so "ORDER BY created_at DESC" has no defined tiebreak
and can return either row first.

Fix: add a database-generated, strictly-monotonic `sequence_number` (a real
Postgres IDENTITY column - atomic and race-free even under true concurrency,
unlike relying on clock precision) and make it the ordering key instead of
created_at. Existing rows are backfilled by Postgres itself when the
IDENTITY column is added (in insertion order, since no other order is
recorded) - no existing column's data is modified.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE decision_logs ADD COLUMN sequence_number BIGINT GENERATED ALWAYS AS IDENTITY")
    op.create_index(
        op.f('ix_decision_logs_sequence_number'), 'decision_logs', ['sequence_number'], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_decision_logs_sequence_number'), table_name='decision_logs')
    op.execute("ALTER TABLE decision_logs DROP COLUMN sequence_number")
