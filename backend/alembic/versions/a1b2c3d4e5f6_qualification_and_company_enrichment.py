"""qualification_and_company_enrichment

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-08-03 10:00:00.000000

Sprint 4: replaces the binary email/phone qualification gate with a
configurable, weighted scoring engine (item 1/2), and extends enrichment to
capture company-level data used by both scoring and AI personalization
(item 5).

1. `workspace_settings` gains `icp_profile` and `qualification_config`
   (both JSONB, default '{}') - per-tenant configuration for the scoring
   engine's target-ICP criteria and factor weights/thresholds.
2. `prospects` gains:
   - `job_title` (person-level, needed for the seniority/decision-maker
     scoring factors and AI personalization)
   - nine company-enrichment columns (industry, employee_count, revenue,
     hq_location, company_linkedin_url, company_website, funding_stage,
     funding_amount, tech_stack, company_description)
   - `qualification_score` / `qualification_reason` / `qualification_level`
     (the last backed by a new `qualificationlevel` enum: HOT/HIGH/MEDIUM/LOW)

No existing data is modified - only new, nullable/defaulted columns and one
new enum type are added.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'workspace_settings',
        sa.Column('icp_profile', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    )
    op.add_column(
        'workspace_settings',
        sa.Column('qualification_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    )

    op.add_column('prospects', sa.Column('job_title', sa.String(length=255), nullable=True))

    op.add_column('prospects', sa.Column('industry', sa.String(length=255), nullable=True))
    op.add_column('prospects', sa.Column('employee_count', sa.Integer(), nullable=True))
    op.add_column('prospects', sa.Column('revenue', sa.String(length=100), nullable=True))
    op.add_column('prospects', sa.Column('hq_location', sa.String(length=255), nullable=True))
    op.add_column('prospects', sa.Column('company_linkedin_url', sa.Text(), nullable=True))
    op.add_column('prospects', sa.Column('company_website', sa.String(length=255), nullable=True))
    op.add_column('prospects', sa.Column('funding_stage', sa.String(length=50), nullable=True))
    op.add_column('prospects', sa.Column('funding_amount', sa.Float(), nullable=True))
    op.add_column(
        'prospects',
        sa.Column('tech_stack', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
    )
    op.add_column('prospects', sa.Column('company_description', sa.Text(), nullable=True))

    op.add_column('prospects', sa.Column('qualification_score', sa.Float(), nullable=True))
    op.add_column('prospects', sa.Column('qualification_reason', sa.Text(), nullable=True))
    # Unlike an inline sa.Enum() inside op.create_table() (which auto-emits
    # CREATE TYPE as part of compiling the table), op.add_column() on an
    # existing table does not - the enum type must be created explicitly
    # first, or ADD COLUMN fails with "type ... does not exist".
    qualification_level_enum = sa.Enum('HOT', 'HIGH', 'MEDIUM', 'LOW', name='qualificationlevel')
    qualification_level_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('prospects', sa.Column('qualification_level', qualification_level_enum, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('prospects', 'qualification_level')
    op.drop_column('prospects', 'qualification_reason')
    op.drop_column('prospects', 'qualification_score')

    op.drop_column('prospects', 'company_description')
    op.drop_column('prospects', 'tech_stack')
    op.drop_column('prospects', 'funding_amount')
    op.drop_column('prospects', 'funding_stage')
    op.drop_column('prospects', 'company_website')
    op.drop_column('prospects', 'company_linkedin_url')
    op.drop_column('prospects', 'hq_location')
    op.drop_column('prospects', 'revenue')
    op.drop_column('prospects', 'employee_count')
    op.drop_column('prospects', 'industry')

    op.drop_column('prospects', 'job_title')

    sa.Enum(name='qualificationlevel').drop(op.get_bind(), checkfirst=True)

    op.drop_column('workspace_settings', 'qualification_config')
    op.drop_column('workspace_settings', 'icp_profile')
