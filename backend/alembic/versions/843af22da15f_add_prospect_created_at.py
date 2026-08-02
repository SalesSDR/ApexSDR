"""add prospect created_at

Revision ID: 843af22da15f
Revises: a2ab531ee2c3
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '843af22da15f'
down_revision: Union[str, Sequence[str], None] = 'a2ab531ee2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills existing rows with now() at migration time -
    # inaccurate for their true historical creation date, but non-breaking
    # and the only sane option since no prior timestamp exists to recover.
    op.add_column('prospects', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_index(op.f('ix_prospects_created_at'), 'prospects', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_prospects_created_at'), table_name='prospects')
    op.drop_column('prospects', 'created_at')
