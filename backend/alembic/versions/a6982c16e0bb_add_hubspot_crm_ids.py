"""add hubspot crm ids

Revision ID: a6982c16e0bb
Revises: 83a7af0da17a
Create Date: 2026-07-30 13:14:52.186991

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6982c16e0bb'
down_revision: Union[str, Sequence[str], None] = '83a7af0da17a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('prospects', sa.Column('hubspot_contact_id', sa.String(length=64), nullable=True))
    op.add_column('prospects', sa.Column('hubspot_deal_id', sa.String(length=64), nullable=True))
    # NOTE: autogenerate also detected 'ix_prospects_provider_id' as missing -
    # a pre-existing drift on databases created before that column's index=True
    # was added (their tables predate Alembic and were never altered to add
    # it). That index is already correctly created by the baseline migration
    # for any database that runs the full chain from scratch, so it's applied
    # here as a separate, idempotent statement rather than folded into this
    # migration's schema diff (which would fail with "already exists" on
    # fresh databases that already got it from the baseline).
    op.execute("CREATE INDEX IF NOT EXISTS ix_prospects_provider_id ON prospects (provider_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('prospects', 'hubspot_deal_id')
    op.drop_column('prospects', 'hubspot_contact_id')
