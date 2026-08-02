"""sequence_engine_and_crm_company

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-31 12:05:00.000000

Two independent, additive schema changes bundled together since both are
needed for this sprint's Sequence Engine + CRM Company work:

1. Sequence Engine: prospects need a `sequence_step_index` counter (which
   SequenceStep row, ordered by step_number, they're currently on) and three
   new ProspectState values (EMAIL_2_SENT, VOICEMAIL_LEFT,
   BREAKUP_EMAIL_SENT) so the pipeline can represent all 7 named channels
   (LinkedIn, LinkedIn Follow-up, Email 1, Email 2, Call, Voicemail, Breakup
   Email) instead of stopping after Email 1/Call.

2. CRM Company sync: prospects need a `hubspot_company_id` column
   (mirroring the existing hubspot_contact_id/hubspot_deal_id) plus a new
   `crm_sync_logs` table recording every CRM sync attempt's outcome
   (success/failure, the provider's raw response or error, and a
   timestamp) - there was previously no audit trail for CRM syncs at all.

No existing data is modified - only new columns/values/tables are added.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Sequence Engine ---
    op.execute("ALTER TYPE prospectstatus ADD VALUE IF NOT EXISTS 'EMAIL_2_SENT'")
    op.execute("ALTER TYPE prospectstatus ADD VALUE IF NOT EXISTS 'VOICEMAIL_LEFT'")
    op.execute("ALTER TYPE prospectstatus ADD VALUE IF NOT EXISTS 'BREAKUP_EMAIL_SENT'")

    op.add_column(
        'prospects',
        sa.Column('sequence_step_index', sa.Integer(), nullable=False, server_default='0'),
    )

    # --- CRM Company sync ---
    op.add_column('prospects', sa.Column('hubspot_company_id', sa.String(length=64), nullable=True))

    op.create_table(
        'crm_sync_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('prospect_id', sa.String(length=36), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('sync_type', sa.String(length=30), nullable=False),
        sa.Column('status', sa.Enum('SUCCESS', 'FAILURE', name='crmsyncstatus'), nullable=False),
        sa.Column('provider_response', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_crm_sync_logs_tenant_id'), 'crm_sync_logs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_crm_sync_logs_prospect_id'), 'crm_sync_logs', ['prospect_id'], unique=False)
    op.create_index(op.f('ix_crm_sync_logs_created_at'), 'crm_sync_logs', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_crm_sync_logs_created_at'), table_name='crm_sync_logs')
    op.drop_index(op.f('ix_crm_sync_logs_prospect_id'), table_name='crm_sync_logs')
    op.drop_index(op.f('ix_crm_sync_logs_tenant_id'), table_name='crm_sync_logs')
    op.drop_table('crm_sync_logs')
    sa.Enum(name='crmsyncstatus').drop(op.get_bind(), checkfirst=True)

    op.drop_column('prospects', 'hubspot_company_id')
    op.drop_column('prospects', 'sequence_step_index')
    # No downgrade for the three added prospectstatus enum values - see
    # b1c2d3e4f5a6's downgrade for why (would require rewriting rows that
    # already use them, which modifies existing data).
