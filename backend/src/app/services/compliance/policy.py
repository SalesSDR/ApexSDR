import zoneinfo
from datetime import UTC, datetime

from sqlalchemy import select

from app.models.schemas import (
    CompliancePolicyType,
    DecisionType,
    DoNotContactList,
    PolicySeverity,
    Prospect,
    WorkspaceSetting,
)
from app.services.compliance.base import ComplianceCheck

# Every policy function shares this signature - (db_session, prospect,
# proposed_action, prospect_tz) - even ones (like DNC) that don't need the
# timezone, so BaseComplianceProvider.validate() can iterate a
# configurable list of policies generically without special-casing which
# ones need which arguments.

async def check_do_not_contact(db_session, prospect: Prospect, proposed_action: DecisionType, prospect_tz: str = "UTC") -> ComplianceCheck:
    """Checks if the prospect's email or domain is on the DNC list."""
    if proposed_action not in (DecisionType.SEND_EMAIL, DecisionType.SEND_LINKEDIN, DecisionType.SEND_FOLLOWUP, DecisionType.SCHEDULE_CALL):
        return ComplianceCheck(is_allowed=True)

    query = select(DoNotContactList).where(DoNotContactList.tenant_id == prospect.tenant_id)
    dnc_items = (await db_session.execute(query)).scalars().all()

    for dnc in dnc_items:
        if dnc.type == "EMAIL" and prospect.email and prospect.email.lower() == dnc.value.lower():
            return ComplianceCheck(
                is_allowed=False,
                policy_type=CompliancePolicyType.DO_NOT_CONTACT,
                severity=PolicySeverity.PERMANENT_BLOCK,
                reason=f"Email {prospect.email} is on the DNC list."
            )
        elif dnc.type == "DOMAIN" and prospect.email and prospect.email.lower().endswith(f"@{dnc.value.lower()}"):
            return ComplianceCheck(
                is_allowed=False,
                policy_type=CompliancePolicyType.DO_NOT_CONTACT,
                severity=PolicySeverity.PERMANENT_BLOCK,
                reason=f"Domain for {prospect.email} is on the DNC list."
            )
        elif dnc.type == "PHONE" and prospect.phone_number and prospect.phone_number == dnc.value:
            # Only blocks calls, not emails
            if proposed_action == DecisionType.SCHEDULE_CALL:
                return ComplianceCheck(
                    is_allowed=False,
                    policy_type=CompliancePolicyType.DO_NOT_CONTACT,
                    severity=PolicySeverity.PERMANENT_BLOCK,
                    reason=f"Phone {prospect.phone_number} is on the DNC list."
                )

    return ComplianceCheck(is_allowed=True)


def is_within_business_hours(
    now_utc: datetime,
    prospect_tz: str,
    start_hour: int = 9,
    end_hour: int = 17,
    exclude_weekends: bool = True,
) -> bool:
    """Real timezone-aware check: [start_hour, end_hour) local time in the
    prospect's own timezone, Mon-Fri only when `exclude_weekends` is True
    (the default, matching this check's original always-block-weekends
    behavior) - not a UTC-only weekend check. Falls back to UTC for an
    unrecognized timezone name rather than raising."""
    try:
        tz = zoneinfo.ZoneInfo(prospect_tz)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")
    local_time = now_utc.astimezone(tz)
    if exclude_weekends and local_time.weekday() >= 5:
        return False
    return start_hour <= local_time.hour < end_hour


async def check_business_hours(db_session, prospect: Prospect, proposed_action: DecisionType, prospect_tz: str = "UTC") -> ComplianceCheck:
    """Ensures outreach is only sent during business hours (9am-5pm) in the
    prospect's own timezone - previously this only checked the weekend in
    UTC and ignored the passed-in timezone/hour-of-day entirely, despite the
    docstring's claim.

    Whether weekends are excluded from the allowed window is per-tenant
    configurable via WorkspaceSetting.exclude_weekends. Defaults to True
    (weekends blocked, the original hardcoded behavior) whenever no
    db_session is available to look it up."""
    exclude_weekends = True
    if db_session is not None:
        result = await db_session.execute(
            select(WorkspaceSetting.exclude_weekends).where(WorkspaceSetting.tenant_id == prospect.tenant_id)
        )
        configured = result.scalar_one_or_none()
        if configured is not None:
            exclude_weekends = configured

    now_utc = datetime.now(UTC)
    if not is_within_business_hours(now_utc, prospect_tz, exclude_weekends=exclude_weekends):
        day_scope = "Mon-Fri" if exclude_weekends else "any day"
        return ComplianceCheck(
            is_allowed=False,
            policy_type=CompliancePolicyType.BUSINESS_HOURS,
            severity=PolicySeverity.TEMPORARY_BLOCK,
            reason=f"Outside business hours (9am-5pm, {day_scope}) in {prospect_tz}."
        )
    return ComplianceCheck(is_allowed=True)


# Name -> policy function registry, used by ProductionComplianceProvider to
# load its enabled policy set from settings.COMPLIANCE_ENABLED_POLICIES.
POLICY_REGISTRY = {
    "DO_NOT_CONTACT": check_do_not_contact,
    "BUSINESS_HOURS": check_business_hours,
}
