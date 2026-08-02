import asyncio
import logging
import random
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.core.retry import evaluate_retry
from app.core.scheduling import get_next_action_time, get_next_business_time
from app.core.state_machine import transition_prospect
from app.models.schemas import (
    BuyingSignal,
    CalendarSyncLog,
    CalendarSyncStatus,
    DecisionType,
    Prospect,
    ProspectState,
    SequenceRule,
    SequenceStep,
    WorkspaceSetting,
)
from app.services.decision.engine import DecisionEngine
from app.services.email import send_native_email
from app.services.enrichment_waterfall import (
    check_unipile_profile,
    enrich_company_waterfall,
    enrich_email_waterfall,
    enrich_phone_waterfall,
)
from app.services.linkedin.base import LinkedInRateLimitError
from app.services.linkedin.service import resolve_account_id
from app.services.metrics.service import (
    calendar_sync_failures_total,
    crm_sync_failures_total,
    queue_processing_latency,
)
from app.services.personalization import PersonalizationService
from app.services.qualification.scoring import (
    delay_multiplier_for,
    estimate_deal_value,
    priority_rank_case,
)
from app.services.signals.engine import BuyingSignalEngine

logger = logging.getLogger(__name__)

async def apply_jitter(ctx, dev_mode=False):
    """
    Applies a dynamic random jitter delay to prevent anti-scraping triggers.
    In dev_mode, delays are truncated for performance.
    """
    delay = random.uniform(0.5, 1.5) if dev_mode else random.uniform(10.0, 30.0)
    logger.info(f"Compliance: Pausing sequence for {delay:.2f} seconds.")
    await asyncio.sleep(delay)

def _next_linkedin_queue_retry_time(account, reason: str, tz: str) -> datetime:
    """When the LinkedIn queue defers a send (daily cap reached or account
    paused), computes the next time it's worth retrying - still funneled
    through business-hours clamping like every other next_action_at in the
    pipeline (core/scheduling.py, reused not duplicated)."""
    now_utc = datetime.now(UTC)
    if reason == "daily_limit_reached":
        return get_next_business_time(now_utc + timedelta(days=1), tz)
    resume_at = account.paused_until or (now_utc + timedelta(hours=1))
    return get_next_business_time(resume_at, tz)

# Maps a prospect's current status to the task that manually advances it one
# step, for the "force advance" admin action. Value shape:
# (status to set before enqueueing, or None if the task's own precondition
# already matches; task name to enqueue; whether the task needs tenant_id).
FORCE_ADVANCE_PLAN = {
    ProspectState.NEW: (None, "run_waterfall_enrichment_task", False),
    ProspectState.IDLE: (None, "start_outbound_sequence", True),
    ProspectState.LI_REQ_SENT: (ProspectState.LI_ACCEPTED_NO_MSG, "send_linkedin_followup_task", False),
    ProspectState.LI_ACCEPTED_NO_MSG: (None, "send_linkedin_followup_task", False),
    ProspectState.LI_MSG_SENT: (None, "execute_email_dispatch_task", False),
    ProspectState.EMAIL_SENT: (None, "execute_call_task", False),
    ProspectState.CALL_QUEUED: (None, "execute_call_task", False),
    ProspectState.CALL_NO_ANSWER_1: (None, "execute_call_task", False),
    ProspectState.CALL_NO_ANSWER_2: (None, "execute_call_task", False),
}

def get_force_advance_plan(current_status: ProspectState):
    return FORCE_ADVANCE_PLAN.get(current_status, (None, None, False))

async def sync_crm_safely(crm_service, prospect, prospect_id: str, db=None):
    """CRM sync is a side effect - a HubSpot hiccup must never block or
    retry-loop the outbound pipeline itself, so failures are logged only.
    Passing `db` lets CRMService record the attempt (success/failure,
    provider response, timestamp) to CrmSyncLog; omit it only where no
    session is available (kept optional so existing callers/tests that
    don't pass one are unaffected)."""
    try:
        await crm_service.sync_status(prospect, db=db)
    except Exception as e:
        crm_sync_failures_total.labels(provider="hubspot").inc()
        logger.warning(f"CRM status sync failed for prospect {prospect_id}: {e}")

_REVENUE_OUTCOME_STATES = (ProspectState.CLOSED_WON, ProspectState.LOST)


async def sync_crm_deal_stage_task(ctx, prospect_id: str):
    """
    Sprint 6, item 1 (CRM Revenue Sync): once a prospect closes
    (CLOSED_WON or LOST/"closed lost"), syncs the corresponding HubSpot
    deal stage ("closedwon"/"closedlost" - see
    services/crm/service.py::DEAL_STAGE_BY_STATE) rather than letting the
    outcome sit unreflected in the CRM. Every attempt is recorded to
    CrmSyncLog (via CRMService's own logging, same as every other sync),
    and unlike sync_crm_safely's fire-and-forget "log and move on" (used
    for routine mid-pipeline status syncs), a closed-deal sync failure is
    retried through the same centralized retry engine
    (core/retry.py::evaluate_retry) book_calendar_meeting_task uses -
    reflecting revenue outcomes in the CRM is worth retrying, not just
    logging once and giving up.
    """
    sessionmaker = ctx['sessionmaker']
    crm_service = ctx['crm_service']
    redis = ctx['redis']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()

            if not prospect or prospect.status not in _REVENUE_OUTCOME_STATES:
                return

            try:
                await crm_service.sync_status(prospect, db=db)
                prospect.retry_count = 0
                logger.info(f"Prospect {prospect_id} deal stage synced to HubSpot for {prospect.status.value}.")
            except Exception as e:
                crm_sync_failures_total.labels(provider="hubspot").inc()
                logger.error(f"CRM deal stage sync failed for {prospect_id} ({prospect.status.value}): {e}")
                outcome = evaluate_retry(prospect)
                if outcome.should_retry:
                    prospect.retry_count += 1
                    defer_seconds = max(1, int((outcome.next_action_at - datetime.now(UTC)).total_seconds()))
                    await redis.enqueue_job('sync_crm_deal_stage_task', prospect_id, _defer_by=defer_seconds)
                else:
                    logger.error(f"CRM deal stage sync permanently failed for {prospect_id} after exhausting retries.")


async def run_decision_engine_task(ctx: dict, prospect_id: str):
    """ARQ task to run the AI Decision Engine for a prospect asynchronously."""
    start_time = time.perf_counter()
    logger.info(f"Worker starting DecisionEngine for prospect: {prospect_id}")
    
    sessionmaker = ctx['sessionmaker']
    async with sessionmaker() as db, db.begin():
        engine = DecisionEngine()
        prospect = await db.scalar(select(Prospect).where(Prospect.id == prospect_id))
        if prospect:
            await engine.decide_and_record(db, prospect)
    
    queue_processing_latency.labels(task_name="run_decision_engine_task").observe(time.perf_counter() - start_time)

async def sync_crm_contact_task(ctx, prospect_id: str):
    """Syncs a newly created prospect to the CRM as a contact."""
    sessionmaker = ctx['sessionmaker']
    crm_service = ctx['crm_service']

    async with sessionmaker() as db, db.begin():
        query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
        p_res = await db.execute(query)
        prospect = p_res.scalar_one_or_none()
        if not prospect:
            return
        try:
            await crm_service.sync_contact(prospect, db=db)
        except Exception as e:
            logger.warning(f"CRM contact sync failed for prospect {prospect_id}: {e}")

async def start_outbound_sequence(ctx, prospect_id: str, tenant_id: str):
    """
    Task to explicitly kick off a prospect from IDLE.
    """
    sessionmaker = ctx['sessionmaker']
    linkedin_queue = ctx['linkedin_queue']
    crm_service = ctx['crm_service']

    async with sessionmaker() as db:
        async with db.begin():
            # SELECT ... FOR UPDATE
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()

            if not prospect or prospect.status != ProspectState.IDLE:
                return

            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False
            tz = getattr(settings_obj, "timezone", None) or "America/New_York"

            rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
            rule_obj = rule_res.scalar_one_or_none()

            account = await linkedin_queue.get_or_create_account(
                db, tenant_id, resolve_account_id(tenant_id), settings.MAX_LINKEDIN_INVITES_PER_DAY
            )
            allowed, reason = linkedin_queue.can_send(account)
            if not allowed:
                prospect.next_action_at = _next_linkedin_queue_retry_time(account, reason, tz)
                logger.info(f"LinkedIn queue unavailable for prospect {prospect_id} ({reason}). Deferring to {prospect.next_action_at}.")
                return

            await apply_jitter(ctx, dev_mode)

            # Sprint 5, item 1: rich, personalized connection note (company
            # enrichment, qualification, buying signals, memory, etc.) via
            # PersonalizationService - no more minimal static text.
            ai_message = await PersonalizationService.generate_message(db, prospect, prompt_type="linkedin_request")

            # Request invitation transmission
            try:
                await linkedin_queue.send_connection_request(
                    account,
                    prospect.linkedin_url,
                    message=ai_message
                )
            except LinkedInRateLimitError as e:
                logger.warning(f"LinkedIn rate limit hit sending LI req to {prospect_id}: {e}")
                prospect.next_action_at = _next_linkedin_queue_retry_time(account, "account_paused", tz)
                return
            except Exception as e:
                logger.error(f"Failed to send LI req to {prospect_id}: {e}")
                if dev_mode:
                    logger.info("Dev mode active: Bypassing Unipile exception to continue sequence...")
                else:
                    outcome = evaluate_retry(prospect)
                    if outcome.should_retry:
                        prospect.retry_count += 1
                        prospect.next_action_at = outcome.next_action_at
                    else:
                        transition_prospect(prospect, outcome.new_status)
                        prospect.next_action_at = None
                    return

            prospect.retry_count = 0
            transition_prospect(prospect, ProspectState.LI_REQ_SENT)

            interval_days = rule_obj.linkedin_interval_minutes // 1440 if rule_obj else 2
            prospect.next_action_at = get_next_action_time(settings_obj, rule_obj, dev_mode, interval_days)

            await sync_crm_safely(crm_service, prospect, prospect_id, db=db)
            logger.info(f"Prospect {prospect_id} moved to LI_REQ_SENT. Next action at {prospect.next_action_at}")

async def send_linkedin_followup_task(ctx, prospect_id: str):
    """
    Task triggered by Unipile webhook when prospect accepts but doesn't message.
    """
    sessionmaker = ctx['sessionmaker']
    linkedin_queue = ctx['linkedin_queue']
    crm_service = ctx['crm_service']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()

            if not prospect or prospect.status != ProspectState.LI_ACCEPTED_NO_MSG:
                return

            tenant_id = prospect.tenant_id
            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False
            tz = getattr(settings_obj, "timezone", None) or "America/New_York"

            rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
            rule_obj = rule_res.scalar_one_or_none()

            account = await linkedin_queue.get_or_create_account(
                db, tenant_id, resolve_account_id(tenant_id), settings.MAX_LINKEDIN_INVITES_PER_DAY
            )
            allowed, reason = linkedin_queue.can_send(account)
            if not allowed:
                prospect.next_action_at = _next_linkedin_queue_retry_time(account, reason, tz)
                logger.info(f"LinkedIn queue unavailable for prospect {prospect_id} ({reason}). Deferring to {prospect.next_action_at}.")
                return

            await apply_jitter(ctx, dev_mode)

            # Sprint 5, item 1: rich, personalized follow-up via PersonalizationService.
            ai_message = await PersonalizationService.generate_message(db, prospect, prompt_type="linkedin_followup")

            import re
            match = re.search(r"in/([^/?]+)", prospect.linkedin_url or "")
            li_identifier = match.group(1) if match else prospect_id

            try:
                await linkedin_queue.send_message(
                    account,
                    provider_id=li_identifier,
                    text=ai_message
                )
            except LinkedInRateLimitError as e:
                logger.warning(f"LinkedIn rate limit hit sending LI followup to {prospect_id}: {e}")
                prospect.next_action_at = _next_linkedin_queue_retry_time(account, "account_paused", tz)
                return
            except Exception as e:
                logger.error(f"Failed to send LI followup to {prospect_id}: {e}")
                if dev_mode:
                    logger.info("Dev mode active: Bypassing Unipile followup exception to continue sequence...")
                else:
                    outcome = evaluate_retry(prospect)
                    if outcome.should_retry:
                        prospect.retry_count += 1
                        prospect.next_action_at = outcome.next_action_at
                    else:
                        transition_prospect(prospect, outcome.new_status)
                        prospect.next_action_at = None
                    return

            prospect.retry_count = 0
            transition_prospect(prospect, ProspectState.LI_MSG_SENT)
            interval_days = rule_obj.email_interval_minutes // 1440 if rule_obj else 2
            prospect.next_action_at = get_next_action_time(settings_obj, rule_obj, dev_mode, interval_days)
            await sync_crm_safely(crm_service, prospect, prospect_id, db=db)
            logger.info(f"Prospect {prospect_id} moved to LI_MSG_SENT. Next action at {prospect.next_action_at}")


async def execute_email_dispatch_task(ctx, prospect_id: str):
    """
    Task triggered if no reply to LI_REQ_SENT or LI_MSG_SENT.
    """
    sessionmaker = ctx['sessionmaker']
    crm_service = ctx['crm_service']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()

            if not prospect or prospect.status not in (ProspectState.LI_REQ_SENT, ProspectState.LI_MSG_SENT):
                return

            tenant_id = prospect.tenant_id
            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False

            rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
            rule_obj = rule_res.scalar_one_or_none()

            await apply_jitter(ctx, dev_mode)

            # Sprint 5, item 1: rich, personalized email via PersonalizationService.
            ai_message = await PersonalizationService.generate_message(db, prospect, prompt_type="email_1")
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
                    outcome = evaluate_retry(prospect)
                    if outcome.should_retry:
                        prospect.retry_count += 1
                        prospect.next_action_at = outcome.next_action_at
                    else:
                        transition_prospect(prospect, outcome.new_status)
                        prospect.next_action_at = None
                    return

            prospect.retry_count = 0
            transition_prospect(prospect, ProspectState.EMAIL_SENT)
            interval_days = rule_obj.call_interval_minutes // 1440 if rule_obj else 3
            prospect.next_action_at = get_next_action_time(settings_obj, rule_obj, dev_mode, interval_days)
            await sync_crm_safely(crm_service, prospect, prospect_id, db=db)
            logger.info(f"Prospect {prospect_id} moved to EMAIL_SENT. Next action at {prospect.next_action_at}")

async def send_email_nudge_task(ctx, prospect_id: str):
    """
    Triggered by the email webhook on a NEGATIVE-intent reply: sends a brief
    re-engagement nudge. Doesn't change status - the prospect stays
    PAUSED_NUDGED either way, waiting for a genuine reply (which re-enters
    the pipeline via the webhook's own EMAIL_REPLIED handling). A failure
    here is logged, not retried via the escalation retry engine - a missed
    nudge is not a broken pipeline hop, just a lost soft-touch.
    """
    sessionmaker = ctx['sessionmaker']
    crm_service = ctx['crm_service']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()

            if not prospect or prospect.status != ProspectState.PAUSED_NUDGED or not prospect.email:
                return

            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == prospect.tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False

            await apply_jitter(ctx, dev_mode)

            # Sprint 5, item 1: rich, personalized nudge via PersonalizationService.
            ai_message = await PersonalizationService.generate_message(db, prospect, prompt_type="email_nudge")

            try:
                await send_native_email(
                    recipient=prospect.email,
                    subject="Following up",
                    text=ai_message
                )
            except Exception as e:
                logger.error(f"Failed to send nudge email to {prospect_id}: {e}")
                return

            await sync_crm_safely(crm_service, prospect, prospect_id, db=db)
            logger.info(f"Sent re-engagement nudge email to prospect {prospect_id}.")

async def execute_call_task(ctx, prospect_id: str):
    """
    Triggered when no response to Email. Escalate to Twilio Voice.
    """
    sessionmaker = ctx['sessionmaker']
    voice_adapter = ctx['voice_adapter']
    crm_service = ctx['crm_service']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()

            if not prospect or prospect.status not in (
                ProspectState.EMAIL_SENT,
                ProspectState.CALL_QUEUED,
                ProspectState.CALL_NO_ANSWER_1,
                ProspectState.CALL_NO_ANSWER_2,
            ):
                return

            if not prospect.phone_number:
                logger.info(f"No phone number on record for prospect {prospect_id}. Transitioning to DEAD.")
                transition_prospect(prospect, ProspectState.UNRESPONSIVE_DEAD)
                prospect.next_action_at = None
                await sync_crm_safely(crm_service, prospect, prospect_id, db=db)
                return

            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == prospect.tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False

            try:
                await voice_adapter.initiate_call(
                    to_number=prospect.phone_number,
                    twimlet_url=f"{settings.PUBLIC_BASE_URL}/api/v1/voice/webhook/incoming?prospect_id={prospect_id}"
                )
            except Exception as e:
                logger.error(f"Failed to initiate call for {prospect_id}: {e}")
                if dev_mode:
                    logger.info("Dev mode active: Bypassing Twilio call exception to continue sequence...")
                else:
                    outcome = evaluate_retry(prospect)
                    if outcome.should_retry:
                        prospect.retry_count += 1
                        prospect.next_action_at = outcome.next_action_at
                    else:
                        transition_prospect(prospect, outcome.new_status)
                        prospect.next_action_at = None
                    return

            prospect.retry_count = 0
            prospect.call_attempts += 1
            prospect.last_call_attempt_at = datetime.now(UTC)
            transition_prospect(prospect, ProspectState.CALL_IN_PROGRESS)
            prospect.next_action_at = None # Await webhook for result
            await sync_crm_safely(crm_service, prospect, prospect_id, db=db)
            logger.info(f"Prospect {prospect_id} moved to CALL_IN_PROGRESS. Call attempts: {prospect.call_attempts}")

# --- Sequence Engine ---
#
# Everything below replaces the old hardcoded per-channel chaining
# (IDLE -> start_outbound_sequence -> LI_REQ_SENT -> ... -> execute_call_task)
# for the AUTONOMOUS pipeline. execute_sequence_step_task is the ONLY task
# the DecisionEngine enqueues for a prospect mid-sequence (see
# services/decision/engine.py's _next_sequence_step_decision) - which
# channel runs next comes entirely from the tenant's SequenceStep rows
# (step_number order, configured via /api/v1/sequences/steps), never from
# Python control flow here. The four legacy task functions above
# (start_outbound_sequence, send_linkedin_followup_task,
# execute_email_dispatch_task, execute_call_task) are kept only as
# manual/admin entry points for the "force advance" action
# (FORCE_ADVANCE_PLAN above) - the autonomous pipeline no longer calls them.

# Maps a SequenceStep.channel value to the ProspectState reached once that
# step's action has been placed/sent successfully.
_CHANNEL_COMPLETION_STATE = {
    "LINKEDIN": ProspectState.LI_REQ_SENT,
    "LINKEDIN_FOLLOWUP": ProspectState.LI_MSG_SENT,
    "EMAIL_1": ProspectState.EMAIL_SENT,
    "EMAIL_2": ProspectState.EMAIL_2_SENT,
    "VOICEMAIL": ProspectState.VOICEMAIL_LEFT,
    "BREAKUP_EMAIL": ProspectState.BREAKUP_EMAIL_SENT,
    # CALL is deliberately absent: it manages its own transition (to
    # CALL_IN_PROGRESS, awaiting the Twilio webhook's outcome) rather than
    # the generic post-step bookkeeping below - see _run_call_channel_step.
}


async def _get_ordered_sequence_steps(db, tenant_id: str) -> list:
    """The tenant's SequenceStep rows, ordered by step_number - the sole
    source of truth for what channel comes after which."""
    rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == tenant_id))
    rule_obj = rule_res.scalar_one_or_none()
    if not rule_obj:
        return []
    steps_res = await db.execute(
        select(SequenceStep).where(SequenceStep.sequence_rule_id == rule_obj.id).order_by(SequenceStep.step_number)
    )
    return steps_res.scalars().all()


async def _apply_outbound_failure(prospect: Prospect, dev_mode: bool, channel_label: str) -> bool:
    """Shared failure handling for every outbound channel: dev_mode bypasses
    the exception entirely (treated as success, matching the legacy tasks'
    behavior); otherwise defers to the centralized retry engine
    (core/retry.py), applying a backoff or escalating to a terminal state
    once retries are exhausted. Returns whether the step should be treated
    as completed (True) or not (False)."""
    if dev_mode:
        logger.info(f"Dev mode active: bypassing {channel_label} exception to continue sequence...")
        return True
    outcome = evaluate_retry(prospect)
    if outcome.should_retry:
        prospect.retry_count += 1
        prospect.next_action_at = outcome.next_action_at
    else:
        transition_prospect(prospect, outcome.new_status)
        prospect.next_action_at = None
    return False


async def _run_linkedin_channel_step(ctx, db, prospect: Prospect, tz: str, dev_mode: bool, is_followup: bool) -> bool:
    """Shared LinkedIn send logic for both the LINKEDIN and LINKEDIN_FOLLOWUP
    channels - queue availability check, jitter, send, and the same
    retry/dev_mode failure handling every outbound channel uses."""
    linkedin_queue = ctx['linkedin_queue']
    tenant_id = prospect.tenant_id
    account = await linkedin_queue.get_or_create_account(
        db, tenant_id, resolve_account_id(tenant_id), settings.MAX_LINKEDIN_INVITES_PER_DAY
    )
    allowed, reason = linkedin_queue.can_send(account)
    if not allowed:
        prospect.next_action_at = _next_linkedin_queue_retry_time(account, reason, tz)
        logger.info(f"LinkedIn queue unavailable for prospect {prospect.id} ({reason}). Deferring to {prospect.next_action_at}.")
        return False

    await apply_jitter(ctx, dev_mode)

    try:
        if is_followup:
            # Sprint 5, item 1: rich, personalized follow-up via PersonalizationService.
            ai_message = await PersonalizationService.generate_message(db, prospect, prompt_type="linkedin_followup")
            import re
            match = re.search(r"in/([^/?]+)", prospect.linkedin_url or "")
            li_identifier = match.group(1) if match else prospect.id
            await linkedin_queue.send_message(account, provider_id=li_identifier, text=ai_message)
        else:
            # Sprint 5, item 1: rich, personalized connection note - no more
            # minimal static text.
            ai_message = await PersonalizationService.generate_message(db, prospect, prompt_type="linkedin_request")
            await linkedin_queue.send_connection_request(
                account, prospect.linkedin_url, message=ai_message
            )
    except LinkedInRateLimitError as e:
        logger.warning(f"LinkedIn rate limit hit for prospect {prospect.id}: {e}")
        prospect.next_action_at = _next_linkedin_queue_retry_time(account, "account_paused", tz)
        return False
    except Exception as e:
        logger.error(f"Failed LinkedIn sequence step for {prospect.id}: {e}")
        return await _apply_outbound_failure(prospect, dev_mode, "Unipile")
    return True


async def _run_email_channel_step(ctx, db, prospect: Prospect, dev_mode: bool, prompt_type: str, subject: str) -> bool:
    """Shared email-send logic for the EMAIL_1, EMAIL_2, and BREAKUP_EMAIL
    channels - only the prompt/subject framing differs between them."""
    await apply_jitter(ctx, dev_mode)
    # Sprint 5, item 1: rich, personalized email via PersonalizationService.
    ai_message = await PersonalizationService.generate_message(db, prospect, prompt_type=prompt_type)
    if "ApexSDR" not in ai_message:
        ai_message += "\n\nSent via ApexSDR"

    try:
        await send_native_email(recipient=prospect.email, subject=subject, text=ai_message)
    except Exception as e:
        logger.error(f"Failed to send '{subject}' email to {prospect.id}: {e}")
        return await _apply_outbound_failure(prospect, dev_mode, "Resend")
    return True


async def _run_call_channel_step(ctx, db, prospect: Prospect, dev_mode: bool) -> bool:
    """The CALL channel: places the call and immediately hands off to the
    Twilio call-status webhook for the actual answer outcome, exactly like
    the legacy execute_call_task - so it manages its own state transition
    (to CALL_IN_PROGRESS, next_action_at=None) and always returns False, to
    skip execute_sequence_step_task's generic post-step bookkeeping (which
    would otherwise prematurely schedule the next step before the call's
    outcome is known)."""
    voice_adapter = ctx['voice_adapter']

    if not prospect.phone_number:
        logger.info(f"No phone number on record for prospect {prospect.id}. Transitioning to DEAD.")
        transition_prospect(prospect, ProspectState.UNRESPONSIVE_DEAD)
        prospect.next_action_at = None
        return False

    try:
        await voice_adapter.initiate_call(
            to_number=prospect.phone_number,
            twimlet_url=f"{settings.PUBLIC_BASE_URL}/api/v1/voice/webhook/incoming?prospect_id={prospect.id}"
        )
    except Exception as e:
        logger.error(f"Failed to initiate call for {prospect.id}: {e}")
        await _apply_outbound_failure(prospect, dev_mode, "Twilio")
        return False

    prospect.retry_count = 0
    prospect.sequence_step_index = (prospect.sequence_step_index or 0) + 1
    prospect.call_attempts += 1
    prospect.last_call_attempt_at = datetime.now(UTC)
    transition_prospect(prospect, ProspectState.CALL_IN_PROGRESS)
    prospect.next_action_at = None  # await the Twilio webhook, not a timer
    return False


async def _run_voicemail_channel_step(ctx, db, prospect: Prospect, dev_mode: bool) -> bool:
    """The VOICEMAIL channel: this MVP's telephony integration (services/voice/)
    doesn't distinguish a live answer from voicemail pickup, so leaving a
    message is modeled as attempting the call and advancing the sequence
    regardless of pickup outcome, rather than depending on Voice module
    internals this sprint must not touch."""
    if not prospect.phone_number:
        logger.info(f"No phone number on record for prospect {prospect.id}; skipping voicemail step.")
        return True

    voice_adapter = ctx['voice_adapter']
    try:
        await voice_adapter.initiate_call(
            to_number=prospect.phone_number,
            twimlet_url="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical"
        )
    except Exception as e:
        logger.warning(f"Voicemail call attempt failed for {prospect.id}: {e} (advancing sequence anyway).")
    return True


_SEQUENCE_STEP_HANDLERS = {
    "LINKEDIN": lambda ctx, db, prospect, tz, dev_mode: _run_linkedin_channel_step(ctx, db, prospect, tz, dev_mode, is_followup=False),
    "LINKEDIN_FOLLOWUP": lambda ctx, db, prospect, tz, dev_mode: _run_linkedin_channel_step(ctx, db, prospect, tz, dev_mode, is_followup=True),
    "EMAIL_1": lambda ctx, db, prospect, tz, dev_mode: _run_email_channel_step(ctx, db, prospect, dev_mode, prompt_type="email_1", subject="ApexSDR Outreach"),
    "EMAIL_2": lambda ctx, db, prospect, tz, dev_mode: _run_email_channel_step(ctx, db, prospect, dev_mode, prompt_type="email_2", subject="Following up"),
    "CALL": lambda ctx, db, prospect, tz, dev_mode: _run_call_channel_step(ctx, db, prospect, dev_mode),
    "VOICEMAIL": lambda ctx, db, prospect, tz, dev_mode: _run_voicemail_channel_step(ctx, db, prospect, dev_mode),
    "BREAKUP_EMAIL": lambda ctx, db, prospect, tz, dev_mode: _run_email_channel_step(ctx, db, prospect, dev_mode, prompt_type="breakup_email", subject="Checking in one last time"),
}


async def execute_sequence_step_task(ctx: dict, prospect_id: str):
    """
    Generic sequence executor (Sequence Engine): runs whichever SequenceStep
    sits at the prospect's current sequence_step_index for their tenant's
    configured sequence - LinkedIn, LinkedIn Follow-up, Email 1, Email 2,
    Call, Voicemail, or Breakup Email, in whatever order the tenant
    configured via /api/v1/sequences/steps. This is the only task the
    autonomous DecisionEngine enqueues for a prospect mid-sequence; the
    order prospects move through channels comes entirely from
    SequenceStep.step_number in the database, never a fixed call chain.
    """
    sessionmaker = ctx['sessionmaker']
    crm_service = ctx['crm_service']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()
            if not prospect:
                return

            steps = await _get_ordered_sequence_steps(db, prospect.tenant_id)
            index = prospect.sequence_step_index or 0
            if index >= len(steps):
                logger.info(f"Prospect {prospect_id}: no further sequence steps configured (index {index}/{len(steps)}).")
                return
            step = steps[index]

            handler = _SEQUENCE_STEP_HANDLERS.get(step.channel)
            if handler is None:
                logger.error(f"Unknown sequence step channel '{step.channel}' for prospect {prospect_id}; skipping.")
                return

            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == prospect.tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            dev_mode = settings_obj.dev_mode if settings_obj else False
            tz = getattr(settings_obj, "timezone", None) or "America/New_York"

            completed = await handler(ctx, db, prospect, tz, dev_mode)
            if not completed:
                return  # handler already applied its own retry/failure/transition bookkeeping

            prospect.retry_count = 0
            prospect.sequence_step_index = index + 1
            transition_prospect(prospect, _CHANNEL_COMPLETION_STATE[step.channel])
            # Sprint 5, item 2: HOT/HIGH priority prospects move through the
            # sequence faster than MEDIUM/LOW - the configured step delay is
            # a base value, scaled by qualification tier.
            base_delay_days = max(0, (step.delay_minutes or 0) // 1440)
            delay_days = max(0, round(base_delay_days * delay_multiplier_for(prospect.qualification_level)))
            prospect.next_action_at = get_next_action_time(settings_obj, None, dev_mode, delay_days)
            await sync_crm_safely(crm_service, prospect, prospect_id, db=db)
            logger.info(
                f"Prospect {prospect_id} completed sequence step '{step.title}' ({step.channel}); "
                f"next_action_at={prospect.next_action_at}"
            )


async def autonomous_pipeline_supervisor_task(ctx):
    """
    The main heartbeat of the AI SDR. It autonomously evaluates prospects
    where now() >= next_action_at, asks the DecisionEngine (Module 6) what
    to do next for each one, and enqueues whatever task the decision names -
    this task no longer decides anything itself, only executes the
    decision (see services/decision/engine.py's docstring for why decision
    logic lives there and nowhere else).

    Sprint 5, item 2 (Priority Queue): due prospects are processed
    HOT -> HIGH -> MEDIUM -> LOW -> not-yet-scored, oldest-created-first
    within each tier - never in arbitrary/insertion order.

    Runs every 5 minutes (or whatever cron schedules).
    """
    sessionmaker = ctx['sessionmaker']
    redis = ctx['redis']
    decision_engine = ctx['decision_engine']

    async with sessionmaker() as db:
        now_utc = datetime.now(UTC)

        # Select all prospects that are due for action, HOT-first and
        # oldest-first within a tier. with_for_update() locks these rows for
        # the duration of the session's transaction, so a concurrent
        # supervisor tick can't double-enqueue the same prospect.
        due_query = (
            select(Prospect)
            .where(Prospect.next_action_at <= now_utc)
            .order_by(priority_rank_case(), Prospect.created_at.asc())
            .with_for_update()
        )
        result = await db.execute(due_query)
        due_prospects = result.scalars().all()

        for prospect in due_prospects:
            logger.info(f"Supervisor: Prospect {prospect.id} in state {prospect.status.value} is due.")

            decision = await decision_engine.decide_and_record(db, prospect)

            if decision.decision_type == DecisionType.HUMAN_REVIEW:
                # Surfaces through the same ERROR_NEEDS_HUMAN bucket ops
                # already monitors (AnalyticsService.failed_jobs()), rather
                # than a parallel "needs review" concept.
                transition_prospect(prospect, ProspectState.ERROR_NEEDS_HUMAN)
            elif decision.task_to_enqueue == 'start_outbound_sequence':
                await redis.enqueue_job('start_outbound_sequence', prospect.id, tenant_id=prospect.tenant_id)
            elif decision.task_to_enqueue:
                await redis.enqueue_job(decision.task_to_enqueue, prospect.id)
            # A decision with no task_to_enqueue (WAIT with nothing due yet,
            # PAUSE, or END_SEQUENCE for a terminal/retry-exhausted
            # prospect) is simply not acted on this tick - already logged
            # above. PAUSE deliberately leaves prospect.status untouched
            # (unlike HUMAN_REVIEW) - it isn't a failure, just parked.

            # Clear next_action_at so this prospect isn't picked up again next
            # tick; the object is already attached to this session (it came
            # from the query above), so no re-query/nested transaction needed.
            prospect.next_action_at = None

        await db.commit()

async def run_waterfall_enrichment_task(ctx, prospect_id: str):
    """
    Cascades through free enrichment providers to fetch missing emails,
    phone numbers, and company data, then qualifies the prospect for
    outreach using the configurable weighted scoring engine (Module 13):
    MEDIUM/HIGH/HOT proceed to IDLE and kick off the outbound sequence; LOW
    is disqualified.
    """
    sessionmaker = ctx['sessionmaker']
    crm_service = ctx['crm_service']
    redis = ctx['redis']
    decision_engine = ctx['decision_engine']

    qualified = False
    tenant_id = None

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            res = await db.execute(query)
            prospect = res.scalar_one_or_none()

            if not prospect:
                logger.warning(f"run_waterfall_enrichment_task: Prospect {prospect_id} not found.")
                return

            if prospect.status not in (ProspectState.NEW, ProspectState.ENRICHING):
                logger.info(f"Prospect {prospect_id} already past qualification ({prospect.status.value}). Skipping.")
                return

            if prospect.status == ProspectState.NEW:
                transition_prospect(prospect, ProspectState.ENRICHING)

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

            # Tier 4 (Module 13): Company Enrichment - only fills fields
            # still unset, so a re-run doesn't overwrite anything a human
            # may have corrected in the meantime.
            if prospect.company_domain and not prospect.industry:
                company_data = await enrich_company_waterfall(prospect.company_domain)
                for field, value in company_data.items():
                    if value not in (None, "", []) and not getattr(prospect, field, None):
                        setattr(prospect, field, value)
                if company_data:
                    logger.info(f"Enriched Prospect {prospect_id}: company data via Apollo organization enrich")

            # Sprint 5, item 5 (Revenue Attribution): seed a starting deal
            # value estimate from company size if nothing's been set yet
            # (by a human or CRM) - always overridable, never recomputed
            # once set.
            if prospect.estimated_deal_value is None:
                prospect.estimated_deal_value = estimate_deal_value(prospect)

            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
            workspace_setting = sett_res.scalar_one_or_none()

            signals_res = await db.execute(
                select(BuyingSignal).where(
                    BuyingSignal.tenant_id == tenant_id,
                    BuyingSignal.prospect_id == prospect_id,
                    BuyingSignal.is_active == True,
                )
            )
            active_signals = signals_res.scalars().all()

            decision = decision_engine.decide_qualification(prospect, workspace_setting, active_signals)
            prospect.qualification_score = decision.qualification_score
            prospect.qualification_reason = decision.qualification_reason
            prospect.qualification_level = decision.qualification_level
            await decision_engine.record_decision(db, prospect, decision)

            if decision.decision_type == DecisionType.MARK_QUALIFIED:
                transition_prospect(prospect, ProspectState.QUALIFIED)
                transition_prospect(prospect, ProspectState.IDLE)
                prospect.next_action_at = datetime.now(UTC)
                qualified = True
                logger.info(f"Prospect {prospect_id} qualified ({decision.qualification_level.value}, score {decision.qualification_score}) and moved to IDLE, ready for outreach.")
            else:
                transition_prospect(prospect, ProspectState.DISQUALIFIED)
                logger.info(f"Prospect {prospect_id} disqualified: qualification score {decision.qualification_score} below threshold.")

            await sync_crm_safely(crm_service, prospect, prospect_id, db=db)

    # Enqueued only after the transaction above commits, so the task that
    # picks this up reads the prospect's new IDLE status, not a stale one.
    # Sequence Engine: dispatches through the generic step executor, not a
    # hardcoded task name - which channel runs first comes from the
    # tenant's SequenceStep order, not from this call site.
    if qualified:
        await redis.enqueue_job('execute_sequence_step_task', prospect_id)

def log_calendar_sync(db, prospect: Prospect, event_type: str, status: CalendarSyncStatus, google_event_id=None, error_message=None):
    """Structured log for the dashboard's Calendar Sync Status / Failed Syncs
    / Last Calendar Sync views - distinct from ActivityTimeline's free text."""
    db.add(CalendarSyncLog(
        id=str(uuid.uuid4()),
        tenant_id=prospect.tenant_id,
        prospect_id=prospect.id,
        event_type=event_type,
        status=status,
        google_event_id=google_event_id,
        error_message=error_message,
    ))

async def book_calendar_meeting_task(ctx, prospect_id: str):
    """Books (or updates, to avoid duplicates) the meeting calendar event once
    a prospect reaches MEETING_BOOKED. Reuses the same centralized retry
    engine as the rest of the pipeline (core/retry.py) - a calendar sync
    failure never changes the prospect's own status, since the real outreach
    outcome (a booked meeting) already succeeded independently of the sync.
    """
    sessionmaker = ctx['sessionmaker']
    calendar_service = ctx['calendar_service']
    redis = ctx['redis']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()

            if not prospect or prospect.status != ProspectState.MEETING_BOOKED:
                return

            sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == prospect.tenant_id))
            settings_obj = sett_res.scalar_one_or_none()
            prospect_timezone = settings_obj.timezone if settings_obj else "America/New_York"

            was_already_booked = bool(prospect.google_calendar_event_id)
            try:
                event_id = await calendar_service.schedule_default_meeting(prospect, prospect_timezone)
                event_type = "EVENT_UPDATED" if was_already_booked else "EVENT_CREATED"
                log_calendar_sync(db, prospect, event_type, CalendarSyncStatus.SUCCESS, google_event_id=event_id)
                prospect.retry_count = 0
                logger.info(f"Prospect {prospect_id} calendar meeting synced: {event_id}")
            except Exception as e:
                logger.error(f"Calendar booking failed for {prospect_id}: {e}")
                log_calendar_sync(db, prospect, "API_FAILURE", CalendarSyncStatus.FAILED, error_message=str(e))
                outcome = evaluate_retry(prospect)
                if outcome.should_retry:
                    prospect.retry_count += 1
                    defer_seconds = max(1, int((outcome.next_action_at - datetime.now(UTC)).total_seconds()))
                    log_calendar_sync(db, prospect, "RETRY_ATTEMPT", CalendarSyncStatus.PENDING)
                    await redis.enqueue_job('book_calendar_meeting_task', prospect_id, _defer_by=defer_seconds)
                else:
                    logger.error(f"Calendar booking permanently failed for {prospect_id} after exhausting retries.")

async def cancel_calendar_meeting_task(ctx, prospect_id: str):
    """Cancels a prospect's booked calendar event, if one exists."""
    sessionmaker = ctx['sessionmaker']
    calendar_service = ctx['calendar_service']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()
            if not prospect:
                return
            try:
                await calendar_service.cancel_meeting(prospect)
                log_calendar_sync(db, prospect, "EVENT_DELETED", CalendarSyncStatus.SUCCESS)
                logger.info(f"Prospect {prospect_id} calendar meeting cancelled.")
            except Exception as e:
                logger.error(f"Calendar cancellation failed for {prospect_id}: {e}")
                log_calendar_sync(db, prospect, "API_FAILURE", CalendarSyncStatus.FAILED, error_message=str(e))

async def reschedule_calendar_meeting_task(ctx, prospect_id: str, new_start: datetime, new_end: datetime, prospect_timezone: str = "America/New_York"):
    """Reschedules (updates in place, never duplicates) a prospect's meeting."""
    sessionmaker = ctx['sessionmaker']
    calendar_service = ctx['calendar_service']

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
            p_res = await db.execute(query)
            prospect = p_res.scalar_one_or_none()
            if not prospect:
                return
            try:
                description = f"Rescheduled meeting with {prospect.first_name} {prospect.last_name}."
                event_id = await calendar_service.book_or_update_meeting(prospect, new_start, new_end, prospect_timezone, description)
                log_calendar_sync(db, prospect, "EVENT_UPDATED", CalendarSyncStatus.SUCCESS, google_event_id=event_id)
                logger.info(f"Prospect {prospect_id} calendar meeting rescheduled: {event_id}")
            except Exception as e:
                logger.error(f"Calendar reschedule failed for {prospect_id}: {e}")
                calendar_sync_failures_total.inc()
                log_calendar_sync(db, prospect, "API_FAILURE", CalendarSyncStatus.FAILED, error_message=str(e))


async def collect_buying_signals_task(ctx, prospect_id: str):
    """
    Collects and processes buying signals for a specific prospect.
    Triggered periodically or on demand.
    """
    sessionmaker = ctx['sessionmaker']
    engine = BuyingSignalEngine()
    
    async with sessionmaker() as db, db.begin():
        query = select(Prospect).where(Prospect.id == prospect_id)
        prospect = (await db.execute(query)).scalar_one_or_none()
        if not prospect:
            return
            
        await engine.collect_and_process_signals(db, prospect)
            # Memory entries will be saved.

async def expire_buying_signals_task(ctx):
    """
    Cron task that expires old signals across all tenants.
    """
    sessionmaker = ctx['sessionmaker']
    engine = BuyingSignalEngine()
    
    async with sessionmaker() as db, db.begin():
        expired_count = await engine.expire_old_signals(db)
        if expired_count > 0:
            logger.info(f"Expired {expired_count} old buying signals.")

async def start_voice_conversation_task(ctx, prospect_id: str):
    """
    Initiates an outbound voice call via Twilio and sets up the initial DB state.
    """
    sessionmaker = ctx['sessionmaker']
    voice_adapter = ctx.get('voice_adapter')
    
    if not voice_adapter:
        logger.error("Voice adapter not configured for start_voice_conversation_task")
        return

    async with sessionmaker() as db:
        async with db.begin():
            query = select(Prospect).where(Prospect.id == prospect_id)
            prospect = (await db.execute(query)).scalar_one_or_none()
            if not prospect or not prospect.phone_number:
                logger.error(f"Cannot start voice call for {prospect_id}: missing phone")
                return
            
            twimlet_url = f"{settings.PUBLIC_BASE_URL}/api/v1/voice/webhook/incoming?prospect_id={prospect_id}"
            
            try:
                result = await voice_adapter.initiate_call(prospect.phone_number, twimlet_url)
                logger.info(f"Initiated call {result.sid} to {prospect.phone_number}")
                
                # Update Prospect State via transition_prospect
                from app.core.state_machine import transition_prospect
                transition_prospect(prospect, ProspectState.CALL_IN_PROGRESS)
            except Exception as e:
                logger.error(f"Failed to initiate call for {prospect_id}: {e}")
                
async def summarize_voice_conversation_task(ctx, call_sid: str):
    """
    Post-call async task to generate the final summary of the conversation.
    """
    sessionmaker = ctx['sessionmaker']
    
    async with sessionmaker() as db, db.begin():
        from app.models.schemas import CallTranscript
        query = select(CallTranscript).where(CallTranscript.call_sid == call_sid)
        transcript = (await db.execute(query)).scalar_one_or_none()
        
        if not transcript:
            return
            
        # For MVP, just use the incremental summary as final
        transcript.summary = transcript.incremental_summary
        transcript.status = "COMPLETED"
        
        logger.info(f"Summarized call {call_sid}")


