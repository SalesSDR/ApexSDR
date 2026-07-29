import time
import uuid
import json
import random
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, update
from redis.asyncio import Redis

from app.config import settings
from app.models.schemas import Prospect, WorkspaceSetting, SequenceRule, ProspectStatus
from app.services.ai import generate_outreach_message
from app.services.email import send_native_email
from app.services.twilio_voice import TwilioVoiceService
from app.services.enrichment_waterfall import (
    check_unipile_profile,
    enrich_email_waterfall,
    enrich_phone_waterfall
)

logger = logging.getLogger(__name__)

async def apply_jitter(ctx, dev_mode=False):
    """
    Applies a dynamic random jitter delay to prevent anti-scraping triggers.
    In dev_mode, delays are truncated for performance.
    """
    delay = random.uniform(0.5, 1.5) if dev_mode else random.uniform(10.0, 30.0)
    logger.info(f"Compliance: Pausing sequence for {delay:.2f} seconds.")
    await asyncio.sleep(delay)

import zoneinfo

def get_next_business_time(current_time: datetime, prospect_timezone: str = "America/New_York") -> datetime:
    """
    Guarantees next_action_at lands between Mon-Fri, 9 AM - 5 PM in the prospect's local timezone.
    """
    try:
        tz = zoneinfo.ZoneInfo(prospect_timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/New_York")
        
    local_time = current_time.astimezone(tz)
    
    # If weekend, move to Monday 9 AM
    if local_time.weekday() >= 5:
        days_ahead = 7 - local_time.weekday()
        local_time = local_time + timedelta(days=days_ahead)
        local_time = local_time.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Check if target hour lands during 9 AM - 5 PM
    elif local_time.hour < 9:
        local_time = local_time.replace(hour=9, minute=0, second=0, microsecond=0)
    
    elif local_time.hour >= 17:
        local_time = local_time + timedelta(days=1)
        if local_time.weekday() >= 5:
            local_time = local_time + timedelta(days=2)
        local_time = local_time.replace(hour=9, minute=0, second=0, microsecond=0)
        
    return local_time.astimezone(timezone.utc)

def get_next_action_time(settings_obj, rule_obj, dev_mode: bool, delay_days: int) -> datetime:
    """
    Calculates the exact execution time. Overridden to 60s in dev_mode.
    """
    now_utc = datetime.now(timezone.utc)
    if dev_mode:
        return now_utc + timedelta(seconds=60)
        
    scheduled_time = now_utc + timedelta(days=delay_days)
    prospect_tz = settings_obj.timezone if settings_obj and hasattr(settings_obj, "timezone") else "UTC"
    return get_next_business_time(scheduled_time, prospect_tz)

async def start_outbound_sequence(ctx, prospect_id: str, tenant_id: str):
    """
    Task to explicitly kick off a prospect from IDLE.
    """
    sessionmaker = ctx['sessionmaker']
    unipile = ctx['unipile_client']
    
    async with sessionmaker() as db:
        async with db.begin():
            # SELECT ... FOR UPDATE
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()
            
            if not prospect or prospect.status != ProspectStatus.IDLE:
                return

            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False

            rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
            rule_obj = rule_res.scalar_one_or_none()

            await apply_jitter(ctx, dev_mode)

            # Request invitation transmission
            try:
                invite_res = await unipile.send_linkedin_connection(
                    prospect.linkedin_url,
                    account_id=settings.UNIPILE_ACCOUNT_ID or f"profile_{tenant_id}",
                    message=f"Hi {prospect.first_name}, looking forward to connecting!"
                )
            except Exception as e:
                logger.error(f"Failed to send LI req to {prospect_id}: {e}")
                if dev_mode:
                    logger.info("Dev mode active: Bypassing Unipile exception to continue sequence...")
                else:
                    if prospect.retry_count >= 3:
                        prospect.status = ProspectStatus.ERROR_NEEDS_HUMAN
                        prospect.next_action_at = None
                    else:
                        prospect.retry_count += 1
                        prospect.next_action_at = datetime.now(timezone.utc) + timedelta(hours=1 * prospect.retry_count)
                    return

            prospect.retry_count = 0
            # Transition
            prospect.status = ProspectStatus.LI_REQ_SENT
            
            interval_days = rule_obj.linkedin_interval_minutes // 1440 if rule_obj else 2
            prospect.next_action_at = get_next_action_time(settings_obj, rule_obj, dev_mode, interval_days)

            logger.info(f"Prospect {prospect_id} moved to LI_REQ_SENT. Next action at {prospect.next_action_at}")

async def send_linkedin_followup_task(ctx, prospect_id: str):
    """
    Task triggered by Unipile webhook when prospect accepts but doesn't message.
    """
    sessionmaker = ctx['sessionmaker']
    unipile = ctx['unipile_client']
    
    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()
            
            if not prospect or prospect.status != ProspectStatus.LI_ACCEPTED_NO_MSG:
                return

            tenant_id = prospect.tenant_id
            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False

            rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
            rule_obj = rule_res.scalar_one_or_none()

            await apply_jitter(ctx, dev_mode)
            
            # Generate AI message
            ai_message = await generate_outreach_message(
                prospect_name=prospect.first_name,
                company=prospect.company_name,
                prompt_type="linkedin"
            )

            import re
            match = re.search(r"in/([^/?]+)", prospect.linkedin_url or "")
            li_identifier = match.group(1) if match else prospect_id

            try:
                await unipile.send_linkedin_message(
                    account_id=settings.UNIPILE_ACCOUNT_ID or f"profile_{tenant_id}",
                    provider_id=li_identifier,
                    text=ai_message
                )
            except Exception as e:
                logger.error(f"Failed to send LI followup to {prospect_id}: {e}")
                if dev_mode:
                    logger.info("Dev mode active: Bypassing Unipile followup exception to continue sequence...")
                else:
                    if prospect.retry_count >= 3:
                        prospect.status = ProspectStatus.ERROR_NEEDS_HUMAN
                        prospect.next_action_at = None
                    else:
                        prospect.retry_count += 1
                        prospect.next_action_at = datetime.now(timezone.utc) + timedelta(hours=1 * prospect.retry_count)
                    return

            prospect.retry_count = 0
            prospect.status = ProspectStatus.LI_MSG_SENT
            interval_days = rule_obj.email_interval_minutes // 1440 if rule_obj else 2
            prospect.next_action_at = get_next_action_time(settings_obj, rule_obj, dev_mode, interval_days)
            logger.info(f"Prospect {prospect_id} moved to LI_MSG_SENT. Next action at {prospect.next_action_at}")


async def execute_email_dispatch_task(ctx, prospect_id: str):
    """
    Task triggered if no reply to LI_REQ_SENT or LI_MSG_SENT.
    """
    sessionmaker = ctx['sessionmaker']
    
    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()
            
            if not prospect or prospect.status not in (ProspectStatus.LI_REQ_SENT, ProspectStatus.LI_MSG_SENT):
                return

            tenant_id = prospect.tenant_id
            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False

            rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
            rule_obj = rule_res.scalar_one_or_none()

            await apply_jitter(ctx, dev_mode)
            
            ai_message = await generate_outreach_message(
                prospect_name=prospect.first_name,
                company=prospect.company_name,
                prompt_type="email"
            )
            if "ApexSDR" not in ai_message:
                ai_message += "\n\nSent via ApexSDR"

            try:
                await send_native_email(
                    recipient=prospect.email,
                    subject="ApexSDR Outreach",
                    text=ai_message
                )
            except Exception as e:
                logger.error(f"Failed to send email to {prospect_id}: {e}")
                if dev_mode:
                    logger.info("Dev mode active: Bypassing Resend email exception to continue sequence...")
                else:
                    if prospect.retry_count >= 3:
                        prospect.status = ProspectStatus.ERROR_NEEDS_HUMAN
                        prospect.next_action_at = None
                    else:
                        prospect.retry_count += 1
                        prospect.next_action_at = datetime.now(timezone.utc) + timedelta(hours=1 * prospect.retry_count)
                    return

            prospect.retry_count = 0
            prospect.status = ProspectStatus.EMAIL_SENT
            interval_days = rule_obj.call_interval_minutes // 1440 if rule_obj else 3
            prospect.next_action_at = get_next_action_time(settings_obj, rule_obj, dev_mode, interval_days)
            logger.info(f"Prospect {prospect_id} moved to EMAIL_SENT. Next action at {prospect.next_action_at}")

async def execute_call_task(ctx, prospect_id: str):
    """
    Triggered when no response to Email. Escalate to Twilio Voice.
    """
    sessionmaker = ctx['sessionmaker']
    twilio_service = TwilioVoiceService()
    
    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()
            
            if not prospect or prospect.status not in (ProspectStatus.EMAIL_SENT, ProspectStatus.CALL_QUEUED):
                return

            if not prospect.phone_number:
                logger.info(f"No phone number on record for prospect {prospect_id}. Transitioning to DEAD.")
                prospect.status = ProspectStatus.UNRESPONSIVE_DEAD
                prospect.next_action_at = None
                return

            try:
                call_res = await twilio_service.initiate_call(
                    to_number=prospect.phone_number,
                    twimlet_url="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical"
                )
            except Exception as e:
                logger.error(f"Failed to initiate call for {prospect_id}: {e}")
                if dev_mode:
                    logger.info("Dev mode active: Bypassing Twilio call exception to continue sequence...")
                else:
                    if prospect.retry_count >= 3:
                        prospect.status = ProspectStatus.ERROR_NEEDS_HUMAN
                        prospect.next_action_at = None
                    else:
                        prospect.retry_count += 1
                        prospect.next_action_at = datetime.now(timezone.utc) + timedelta(hours=1 * prospect.retry_count)
                    return

            prospect.retry_count = 0
            prospect.call_attempts += 1
            prospect.last_call_attempt_at = datetime.now(timezone.utc)
            prospect.status = ProspectStatus.CALL_IN_PROGRESS
            prospect.next_action_at = None # Await webhook for result
            logger.info(f"Prospect {prospect_id} moved to CALL_IN_PROGRESS. Call attempts: {prospect.call_attempts}")

async def autonomous_pipeline_supervisor_task(ctx):
    """
    The main heartbeat of the AI SDR. It autonomously evaluates prospects 
    where now() >= next_action_at and triggers the correct transition.
    Runs every 5 minutes (or whatever cron schedules).
    """
    sessionmaker = ctx['sessionmaker']
    redis = ctx['redis']
    
    async with sessionmaker() as db:
        now_utc = datetime.now(timezone.utc)
        
        # Select all prospects that are due for action
        due_query = select(Prospect).where(Prospect.next_action_at <= now_utc)
        result = await db.execute(due_query)
        due_prospects = result.scalars().all()
        
        for prospect in due_prospects:
            logger.info(f"Supervisor: Prospect {prospect.id} in state {prospect.status.value} is due.")
            
            if prospect.status == ProspectStatus.IDLE:
                await redis.enqueue_job('start_outbound_sequence', prospect.id, tenant_id=prospect.tenant_id)
            
            elif prospect.status == ProspectStatus.LI_REQ_SENT:
                # No reply to LI req, escalate to cold email
                await redis.enqueue_job('execute_email_dispatch_task', prospect.id)
                
            elif prospect.status == ProspectStatus.LI_ACCEPTED_NO_MSG:
                # Only rescue if 24 hours have passed since they accepted the invite
                if prospect.last_status_change_at and now_utc > prospect.last_status_change_at + timedelta(hours=24):
                    await redis.enqueue_job('send_linkedin_followup_task', prospect.id)
                
            elif prospect.status == ProspectStatus.LI_MSG_SENT:
                # No reply to LI followup, escalate to cold email
                await redis.enqueue_job('execute_email_dispatch_task', prospect.id)
                
            elif prospect.status == ProspectStatus.EMAIL_SENT:
                # No reply to Email, escalate to call
                await redis.enqueue_job('execute_call_task', prospect.id)
                
            elif prospect.status == ProspectStatus.CALL_QUEUED:
                # Retry calling
                await redis.enqueue_job('execute_call_task', prospect.id)
                
            elif prospect.status in [ProspectStatus.CALL_NO_ANSWER_1, ProspectStatus.CALL_NO_ANSWER_2]:
                await redis.enqueue_job('execute_call_task', prospect.id)
                
            # To avoid duplicate enqueuing on next tick, we could clear next_action_at here,
            # but then if the task fails, it gets stuck.
            # Ideally the enqueued task updates next_action_at immediately.
            # To be safe, we just let the task do the update.
            # For this exact implementation, we could just clear it here:
            async with db.begin():
                query = select(Prospect).where(Prospect.id == prospect.id).with_for_update()
                p = await db.execute(query)
                p_obj = p.scalar_one_or_none()
                if p_obj:
                    p_obj.next_action_at = None

async def run_waterfall_enrichment_task(ctx, prospect_id: str):
    """
    Cascades through free enrichment providers to fetch missing emails and phone numbers.
    """
    sessionmaker = ctx['sessionmaker']
    
    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            res = await db.execute(query)
            prospect = res.scalar_one_or_none()
            
            if not prospect:
                logger.warning(f"run_waterfall_enrichment_task: Prospect {prospect_id} not found.")
                return
            
            tenant_id = prospect.tenant_id
            account_id = settings.UNIPILE_ACCOUNT_ID or f"profile_{tenant_id}"
            
            # Tier 1: Unipile Native Check
            if prospect.provider_id and (not prospect.email or not prospect.phone_number):
                u_email, u_phone = await check_unipile_profile(prospect.provider_id, account_id)
                if u_email and not prospect.email:
                    prospect.email = u_email
                    logger.info(f"Enriched Prospect {prospect_id}: Email found via Unipile Native Profile")
                if u_phone and not prospect.phone_number:
                    prospect.phone_number = u_phone
                    logger.info(f"Enriched Prospect {prospect_id}: Phone found via Unipile Native Profile")

            # Tier 2: Email Waterfall
            if not prospect.email:
                new_email = await enrich_email_waterfall(
                    first_name=prospect.first_name,
                    last_name=prospect.last_name,
                    company_domain=prospect.company_domain or "",
                    linkedin_url=prospect.linkedin_url
                )
                if new_email:
                    prospect.email = new_email
                    logger.info(f"Enriched Prospect {prospect_id}: Email found via Email Waterfall")

            # Tier 3: Phone Waterfall
            if not prospect.phone_number:
                new_phone = await enrich_phone_waterfall(
                    linkedin_url=prospect.linkedin_url
                )
                if new_phone:
                    prospect.phone_number = new_phone
                    logger.info(f"Enriched Prospect {prospect_id}: Phone found via Phone Waterfall")

            logger.info(f"Finished waterfall enrichment for {prospect_id}.")
