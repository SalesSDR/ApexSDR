"""email_verification_and_bounce

Revision ID: f4a5b6c7d8e9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-31 13:00:00.000000

Sprint 3, item 1 (Email Verification): two new, non-tenant-scoped tables.

1. `email_verifications` - caches the verification outcome (VALID/INVALID/
   RISKY/UNKNOWN) for an email address so it is checked once before its
   first send rather than on every send.
2. `email_bounce_suppressions` - a permanent send-suppression list, checked
   ahead of verification, populated from bounce/complaint webhook events.

Both are keyed by email address only (not tenant_id): deliverability is a
property of the address itself, independent of which tenant is emailing
it. Purely additive - no existing data is modified.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'email_verifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column(
            'status',
            sa.Enum('VALID', 'INVALID', 'RISKY', 'UNKNOWN', name='emailverificationstatus'),
            nullable=False,
        ),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_email_verifications_email'), 'email_verifications', ['email'], unique=True)

    op.create_table(
        'email_bounce_suppressions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_email_bounce_suppressions_email'), 'email_bounce_suppressions', ['email'], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_email_bounce_suppressions_email'), table_name='email_bounce_suppressions')
    op.drop_table('email_bounce_suppressions')

    op.drop_index(op.f('ix_email_verifications_email'), table_name='email_verifications')
    op.drop_table('email_verifications')

    sa.Enum(name='emailverificationstatus').drop(op.get_bind(), checkfirst=True)
