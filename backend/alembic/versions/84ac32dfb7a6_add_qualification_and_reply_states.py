"""add qualification and reply states

Revision ID: 84ac32dfb7a6
Revises: 9d1e2763b279
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84ac32dfb7a6'
down_revision: Union[str, Sequence[str], None] = '9d1e2763b279'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Module 3: pre-outreach qualification phase (NEW/ENRICHING/QUALIFIED/
# DISQUALIFIED) plus explicit reply markers (LINKEDIN_REPLIED/EMAIL_REPLIED)
# and a distinct "answered" call state (CALL_CONNECTED, vs. CALL_IN_PROGRESS
# which means dialing).
NEW_VALUES = [
    "NEW",
    "ENRICHING",
    "QUALIFIED",
    "DISQUALIFIED",
    "LINKEDIN_REPLIED",
    "EMAIL_REPLIED",
    "CALL_CONNECTED",
]

OLD_VALUES = [
    'IDLE', 'LI_REQ_SENT', 'LI_ACCEPTED_NO_MSG', 'LI_MSG_SENT', 'LINKEDIN_NO_RESPONSE',
    'EMAIL_SENT', 'EMAIL_OPENED', 'EMAIL_CLICKED', 'EMAIL_FAILED',
    'CALL_QUEUED', 'CALL_IN_PROGRESS', 'CALL_NO_ANSWER_1', 'CALL_NO_ANSWER_2', 'CALL_FAILED', 'CALL_RETRY',
    'MEETING_BOOKED', 'PAUSED_NUDGED', 'COMPLETED_DECLINED', 'UNRESPONSIVE_DEAD', 'LOST',
    'ERROR_NEEDS_HUMAN', 'ENGAGED_ON_WEBSITE',
]


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block (and,
    # even where Postgres allows it, the new value can't be used in the same
    # transaction it was added in) - autocommit_block() runs each statement
    # outside Alembic's normal transaction wrapping.
    with op.get_context().autocommit_block():
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE prospectstatus ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    in_use = bind.execute(
        sa.text(
            "SELECT DISTINCT status::text FROM prospects WHERE status::text = ANY(:vals)"
        ),
        {"vals": NEW_VALUES},
    ).scalars().all()
    if in_use:
        raise RuntimeError(
            "Cannot downgrade: prospects table has rows using new status "
            f"values that don't exist in the pre-Module-3 enum: {sorted(in_use)}. "
            "Migrate those rows to a pre-Module-3 status before downgrading."
        )

    # Postgres has no ALTER TYPE ... DROP VALUE - recreate the type without
    # the new values via rename-create-swap-drop, matching the checkfirst
    # enum-drop pattern used in the Module 1/2 migrations.
    old_enum = sa.Enum(*OLD_VALUES, name="prospectstatus")
    op.execute("ALTER TYPE prospectstatus RENAME TO prospectstatus_old")
    old_enum.create(bind, checkfirst=False)
    op.execute(
        "ALTER TABLE prospects ALTER COLUMN status TYPE prospectstatus "
        "USING status::text::prospectstatus"
    )
    op.execute("DROP TYPE prospectstatus_old")
