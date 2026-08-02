"""fix_memorytype_buying_signal

Revision ID: b1c2d3e4f5a6
Revises: 7aef95d2f6de
Create Date: 2026-07-31 12:00:00.000000

The Python MemoryType enum (app.models.schemas) has included BUYING_SIGNAL
since the signals engine (services/signals/engine.py) started writing
ConversationMemory rows with memory_type=BUYING_SIGNAL, but the Postgres
enum type `memorytype` was never altered to add it - it was created by
4b083897ce1b_add_conversation_memory with only the original 7 values. Any
insert of a BUYING_SIGNAL memory therefore fails at the database with
"invalid input value for enum memorytype" in a real Postgres, even though
the ORM/Python side has always accepted it.

This migration only ADDS the missing enum value. It does not touch any
existing row, table, or other enum value - no existing data is modified.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '7aef95d2f6de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction that
    # then uses the new value, but simply adding it (never using it here) is
    # safe within Alembic's default transactional DDL on Postgres 12+.
    op.execute("ALTER TYPE memorytype ADD VALUE IF NOT EXISTS 'BUYING_SIGNAL'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no ALTER TYPE ... DROP VALUE. Rebuilding the enum type
    # without BUYING_SIGNAL would require rewriting every row that already
    # uses it, which would modify existing data - explicitly out of scope
    # ("do not modify existing data"). This is intentionally a no-op;
    # rolling back this migration leaves the additive enum value in place.
    pass
