import logging
from typing import Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.schemas import SequenceRule, WorkspaceSetting

logger = logging.getLogger(__name__)

class SequenceEngine:
    @staticmethod
    async def get_next_scheduled_action(
        db: AsyncSession, 
        tenant_id: str, 
        current_step: int, 
        current_channel: str
    ) -> Dict[str, Any]:
        """
        Dynamically evaluates channel step limits to manage channel transitions.
        Returns the next channel, delay in hours, and the updated sequence number.
        """
        # Fetch custom sequence rule or fallback to WorkspaceSetting
        rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
        rule = rule_res.scalar_one_or_none()

        sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
        settings = sett_res.scalar_one_or_none() or WorkspaceSetting(tenant_id=tenant_id)

        # Safely extract fallback settings values (Default 24 hours if None)
        default_follow_up_delay = (settings.follow_up_delay_hours or 24)
        default_call_delay = (settings.call_delay_hours or 24)
        default_max_follow_ups = (settings.max_follow_ups or 3)

        # Retrieve Caps and Intervals (with fallbacks)
        max_linkedin = rule.max_linkedin_msgs if rule and rule.max_linkedin_msgs is not None else default_max_follow_ups
        linkedin_interval = rule.linkedin_interval_minutes if rule and rule.linkedin_interval_minutes is not None else (default_follow_up_delay * 60)

        max_emails = rule.max_emails if rule and rule.max_emails is not None else default_max_follow_ups
        email_interval = rule.email_interval_minutes if rule and rule.email_interval_minutes is not None else (default_follow_up_delay * 60)

        call_interval = rule.call_interval_minutes if rule and rule.call_interval_minutes is not None else (default_call_delay * 60)
        
        # Ensure minimums
        linkedin_interval = max(linkedin_interval, 1)
        email_interval = max(email_interval, 1)
        call_interval = max(call_interval, 1)

        # Logic for progression
        next_channel = current_channel
        delay_minutes = 1440  # Default fallback 24 hours
        next_step = current_step + 1

        if current_channel == "LINKEDIN":
            if next_step <= max_linkedin:
                delay_minutes = linkedin_interval
            else:
                next_channel = "EMAIL"
                next_step = 1
                delay_minutes = email_interval

        elif current_channel == "EMAIL":
            if next_step <= max_emails:
                delay_minutes = email_interval
            else:
                next_channel = "CALL"
                next_step = 1
                delay_minutes = call_interval

        # Return metadata for next execution
        return {
            "next_channel": next_channel,
            "delay_minutes": delay_minutes,
            "next_step": next_step
        }
