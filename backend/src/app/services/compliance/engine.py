import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ComplianceLog, DecisionType, Prospect, WorkspaceSetting
from app.services.compliance.base import ComplianceCheck
from app.services.compliance.factory import get_compliance_provider
from app.services.metrics.service import compliance_blocks_total

logger = logging.getLogger(__name__)

class ComplianceEngine:
    """The central authority for validating actions before execution."""

    async def validate(self, db: AsyncSession, prospect: Prospect, proposed_action: DecisionType) -> ComplianceCheck:
        """
        Runs all active compliance policies.
        Returns a ComplianceCheck which indicates whether the action is permitted,
        and if not, returns the details of the block.
        """
        provider = get_compliance_provider(prospect.tenant_id)

        # We only check compliance for outreach tasks
        outreach_actions = {
            DecisionType.SEND_EMAIL,
            DecisionType.SEND_LINKEDIN,
            DecisionType.SEND_FOLLOWUP,
            DecisionType.SCHEDULE_CALL
        }

        if proposed_action not in outreach_actions:
            return ComplianceCheck(is_allowed=True)

        # The prospect's actual timezone - previously business-hours checks
        # hardcoded "America/New_York" regardless of the tenant's real
        # configuration. WorkspaceSetting.timezone is the tenant-level
        # default; there is no per-prospect timezone column today.
        ws_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == prospect.tenant_id))
        workspace = ws_res.scalar_one_or_none()
        prospect_tz = workspace.timezone if workspace and workspace.timezone else "UTC"

        check = await provider.validate(db, prospect, proposed_action, prospect_tz)
        return check

    async def record_violation(self, db: AsyncSession, prospect: Prospect, proposed_action: DecisionType, check: ComplianceCheck, cid: str | None = None) -> ComplianceLog:
        """Logs a blocked action."""
        # Determine channel loosely based on proposed action
        channel = None
        if proposed_action == DecisionType.SEND_EMAIL:
            channel = "EMAIL"
        elif proposed_action in (DecisionType.SEND_LINKEDIN, DecisionType.SEND_FOLLOWUP):
            channel = "LINKEDIN"
        elif proposed_action == DecisionType.SCHEDULE_CALL:
            channel = "CALL"

        log = ComplianceLog(
            tenant_id=prospect.tenant_id,
            prospect_id=prospect.id,
            policy_type=check.policy_type,
            severity=check.severity,
            channel=channel,
            reason=check.reason,
            action_taken="BLOCKED" if check.severity.value == "PERMANENT_BLOCK" else "DELAYED",
            correlation_id=cid,
            metadata_={"proposed_action": proposed_action.value}
        )
        db.add(log)
        await db.flush()
        
        # Increment operational metric
        compliance_blocks_total.labels(policy_type=check.policy_type.value, severity=check.severity.value).inc()
        
        logger.warning(f"Compliance Block for prospect {prospect.id}: {check.policy_type.value} - {check.reason}")
        return log
