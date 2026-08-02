import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import UTC, datetime, timedelta

import httpx
import redis.asyncio as aioredis
from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator

from app.config import settings
from app.core.prompt_security import build_delimited_prompt, flag_suspicious
from app.core.scheduling import get_next_business_time
from app.core.state_machine import (
    TERMINAL_STATES,
    IllegalStateTransitionError,
    transition_prospect,
)
from app.database import get_arq_pool, get_db, get_redis
from app.models.schemas import Prospect, ProspectState, WorkspaceSetting
from app.services.crm.factory import get_crm_adapter
from app.services.crm.service import CRMService
from app.services.email_verification.service import suppress_bounced_email

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def verify_unipile_signature(request: Request) -> None:
    """Unipile signs every webhook delivery with a shared secret configured
    at webhook-creation time, sent back verbatim in the `Unipile-Auth`
    header (see developer.unipile.com/docs/webhooks-2). Rejects with 401 if
    the header is missing, wrong, or the secret isn't configured at all."""
    if not settings.UNIPILE_WEBHOOK_SECRET:
        logger.error("UNIPILE_WEBHOOK_SECRET is not configured; rejecting Unipile webhook.")
        raise HTTPException(status_code=401, detail="Unipile webhook verification is not configured")

    provided = request.headers.get("Unipile-Auth", "")
    if not provided or not hmac.compare_digest(provided, settings.UNIPILE_WEBHOOK_SECRET):
        logger.warning("Rejected Unipile webhook: missing or invalid Unipile-Auth header.")
        raise HTTPException(status_code=401, detail="Invalid Unipile webhook credential")


# Svix (and therefore Resend, which delivers webhooks through Svix) has no
# fixed tolerance in its own docs; 5 minutes is the conventional window used
# across Svix's own SDKs/guides to bound replay-attack exposure.
_RESEND_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300


def verify_resend_signature(request: Request, raw_body: bytes) -> None:
    """Verifies an inbound Resend webhook using Resend's actual signing
    scheme: delivery is via Svix, so the payload is signed HMAC-SHA256 over
    "{svix-id}.{svix-timestamp}.{raw_body}" using the base64-decoded portion
    of the `whsec_...` secret as the key (see
    resend.com/docs/webhooks/verify-webhooks-requests and
    docs.svix.com/receiving/verifying-payloads/how-manual). Rejects with 401
    if any header is missing, the timestamp is stale, or no signature in the
    (possibly multi-valued) svix-signature header matches."""
    if not settings.RESEND_WEBHOOK_SECRET:
        logger.error("RESEND_WEBHOOK_SECRET is not configured; rejecting email webhook.")
        raise HTTPException(status_code=401, detail="Email webhook verification is not configured")

    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")
    if not svix_id or not svix_timestamp or not svix_signature:
        logger.warning("Rejected email webhook: missing svix-id/svix-timestamp/svix-signature header.")
        raise HTTPException(status_code=401, detail="Missing email webhook signature headers")

    try:
        timestamp_age = abs(time.time() - int(svix_timestamp))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid email webhook timestamp")
    if timestamp_age > _RESEND_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
        logger.warning("Rejected email webhook: timestamp outside tolerance window.")
        raise HTTPException(status_code=401, detail="Email webhook timestamp outside tolerance")

    secret = settings.RESEND_WEBHOOK_SECRET
    secret = secret.removeprefix("whsec_")
    try:
        secret_bytes = base64.b64decode(secret)
    except Exception:
        logger.error("RESEND_WEBHOOK_SECRET is not valid base64; rejecting email webhook.")
        raise HTTPException(status_code=401, detail="Email webhook verification is not configured")

    signed_content = f"{svix_id}.{svix_timestamp}.".encode() + raw_body
    expected_signature = base64.b64encode(
        hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()
    ).decode("utf-8")

    # svix-signature can carry multiple space-delimited "v1,<base64sig>"
    # entries (e.g. during secret rotation) - any match is sufficient.
    for entry in svix_signature.split():
        _, _, provided_signature = entry.partition(",")
        if provided_signature and hmac.compare_digest(provided_signature, expected_signature):
            return

    logger.warning("Rejected email webhook: no svix-signature entry matched.")
    raise HTTPException(status_code=401, detail="Invalid email webhook signature")


async def verify_twilio_signature(request: Request) -> None:
    """Verifies the `X-Twilio-Signature` header against the full set of
    posted form parameters, per Twilio's request-signing scheme. Rejects
    with 401 if the signature is missing, invalid, or TWILIO_AUTH_TOKEN
    isn't configured at all.

    Twilio computes its signature over the EXACT URL it requested,
    including the query string (e.g. `?prospect_id=...`) - Twilio's own
    RequestValidator.validate() takes that full URL as a single opaque
    string and does not separate query params from the rest of the URL.
    Dropping the query string here would make every signature check fail
    for any webhook URL that carries one (the /voice/webhook/* routes do)."""
    if not settings.TWILIO_AUTH_TOKEN:
        logger.error("TWILIO_AUTH_TOKEN is not configured; rejecting Twilio webhook.")
        raise HTTPException(status_code=401, detail="Twilio webhook verification is not configured")

    signature = request.headers.get("X-Twilio-Signature", "")
    form_params = dict(await request.form())
    url = f"{settings.PUBLIC_BASE_URL}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    if not signature or not validator.validate(url, form_params, signature):
        logger.warning("Rejected Twilio webhook: invalid X-Twilio-Signature.")
        raise HTTPException(status_code=401, detail="Invalid Twilio webhook signature")

async def sync_crm_after_reply(prospect: Prospect, db: AsyncSession = None, log_meeting: bool = False) -> bool:
    """CRM sync is a side effect - a HubSpot hiccup must never block these
    webhook handlers, so failures are logged only. Uses a short-lived HTTP
    client since webhook handlers have no shared ctx like the ARQ worker.
    Returns whether the sync succeeded, since calendar booking should only
    proceed after CRM sync completes successfully. Passing `db` lets
    CRMService record each sync attempt to CrmSyncLog."""
    try:
        async with httpx.AsyncClient() as http_client:
            crm_service = CRMService(get_crm_adapter(http_client))
            await crm_service.sync_status(prospect, db=db)
            if log_meeting:
                await crm_service.log_meeting_booked(prospect, db=db)
        return True
    except Exception as e:
        logger.warning(f"CRM sync failed for prospect {prospect.id}: {e}")
        return False

async def enqueue_task(arq_pool: ArqRedis, task_name: str, *args) -> None:
    """Enqueues via the single shared app-wide ARQ pool (app.state.arq_redis,
    injected by the caller) instead of opening a new connection pool per
    call."""
    try:
        await arq_pool.enqueue_job(task_name, *args)
    except Exception as e:
        logger.error(f"Failed to enqueue {task_name}({args}): {e}")

async def queue_calendar_booking(arq_pool: ArqRedis, prospect: Prospect) -> None:
    """Never call Google APIs directly inside a request handler - queue the
    booking through the same ARQ queue the rest of the pipeline uses. Resets
    retry_count first since calendar retries must start fresh, independent of
    whatever the outreach pipeline's retry_count held before MEETING_BOOKED."""
    prospect.retry_count = 0
    try:
        await arq_pool.enqueue_job('book_calendar_meeting_task', prospect.id)
    except Exception as e:
        logger.error(f"Failed to enqueue calendar booking for prospect {prospect.id}: {e}")

_MOCK_POSITIVE_KEYWORDS = ("interested", "sounds great", "let's talk", "love to", "yes", "schedule", "book a", "demo")
_MOCK_NEGATIVE_KEYWORDS = ("not interested", "no thanks", "remove me", "stop", "unsubscribe", "don't")


def _mock_classify_intent(text: str) -> str:
    """Keyword-based stand-in for the real Gemini classification - avoids
    calling a paid API when USE_MOCK_CLIENTS=true, matching every other
    provider integration in this codebase (see services/*/factory.py)."""
    lowered = text.lower()
    if any(kw in lowered for kw in _MOCK_NEGATIVE_KEYWORDS):
        return "NEGATIVE"
    if any(kw in lowered for kw in _MOCK_POSITIVE_KEYWORDS):
        return "POSITIVE"
    return "NEUTRAL"


async def classify_intent_service(text: str) -> str:
    """
    Analyzes inbound reply text (an email or LinkedIn reply - untrusted,
    prospect-authored) using Gemini 2.0 Flash to classify intent. Enforces
    strict JSON output {"intent": "POSITIVE" | "NEGATIVE" | "NEUTRAL"}.
    The reply text is isolated in its own delimited, escaped tag (Sprint 4,
    item 4) rather than interpolated inline, so a reply crafted to look
    like an instruction ("ignore previous instructions...") can't break out
    of the data section.
    """
    if not text:
        return "NEUTRAL"
    if flag_suspicious(text):
        logger.warning("classify_intent_service: reply text matches a known prompt-injection pattern.")
    if settings.USE_MOCK_CLIENTS:
        return _mock_classify_intent(text)
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash')

        prompt = build_delimited_prompt(
            "Analyze the reply inside <reply_text>, from a sales prospect. Classify their intent as POSITIVE, NEGATIVE, or NEUTRAL.",
            {"reply_text": text},
            max_chars_per_section=2000,
        )

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "enum": ["Positive", "Negative", "Neutral"]}
                    },
                    "required": ["intent"]
                }
            )
        )
        result = json.loads(response.text.strip())
        intent = result.get("intent", "Neutral").upper()
        return intent
    except Exception as e:
        logger.warning(f"Gemini reply intent analysis error: {e}. Defaulting to NEUTRAL.")
        return "NEUTRAL"

@router.post("/webhooks/unipile", status_code=status.HTTP_200_OK)
async def handle_unipile_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Listens for inbound events from Unipile.
    """
    verify_unipile_signature(request)
    payload = await request.json()
    logger.info(f"Received Unipile webhook: {payload.get('event')}")
    
    event_type = payload.get("event")
    
    if event_type == "new_relation" or event_type == "invitation:accepted":
        # Connection Accepted without message
        data = payload.get("data", {})
        sender_id = data.get("sender_id") or data.get("provider_id")
        
        if not sender_id:
            return {"status": "ignored", "reason": "no sender_id"}

        async with db.begin():
            # Find and lock prospect
            query = select(Prospect).where(Prospect.provider_id == sender_id).with_for_update()
            res = await db.execute(query)
            prospect = res.scalar_one_or_none()
            
            if not prospect:
                # Try fallback matching
                query2 = select(Prospect).where(Prospect.linkedin_url.ilike(f"%{sender_id}%")).with_for_update()
                res = await db.execute(query2)
                prospect = res.scalar_one_or_none()
                
            if prospect and prospect.status in [ProspectState.PAUSED_NUDGED, ProspectState.MEETING_BOOKED, ProspectState.CALL_IN_PROGRESS, ProspectState.ENGAGED_ON_WEBSITE, ProspectState.ERROR_NEEDS_HUMAN]:
                logger.info(f"Prospect {prospect.id} already engaged ({prospect.status.value}). Aborting Unipile logic.")
                return {"status": "ignored", "reason": "global_circuit_breaker"}

            if prospect and prospect.status == ProspectState.LI_REQ_SENT:
                transition_prospect(prospect, ProspectState.LI_ACCEPTED_NO_MSG)
                # Schedule the next sequence step immediately (Sequence
                # Engine: whatever the tenant configured after LinkedIn -
                # not hardcoded to the follow-up specifically).
                await enqueue_task(arq_pool, 'execute_sequence_step_task', prospect.id)
                await sync_crm_after_reply(prospect, db=db)
                logger.info(f"Prospect {prospect.id} accepted invite. Status -> LI_ACCEPTED_NO_MSG")

    elif event_type == "message.created" or event_type == "message:received":
        data = payload.get("data", {})
        sender_id = data.get("sender_id")
        text = data.get("text", "")
        
        if not sender_id:
            return {"status": "ignored"}

        async with db.begin():
            query = select(Prospect).where(Prospect.provider_id == sender_id).with_for_update()
            res = await db.execute(query)
            prospect = res.scalar_one_or_none()
            
            if not prospect:
                query2 = select(Prospect).where(Prospect.linkedin_url.ilike(f"%{sender_id}%")).with_for_update()
                res = await db.execute(query2)
                prospect = res.scalar_one_or_none()
            
            if prospect and prospect.status in [ProspectState.PAUSED_NUDGED, ProspectState.MEETING_BOOKED, ProspectState.CALL_IN_PROGRESS, ProspectState.ENGAGED_ON_WEBSITE, ProspectState.ERROR_NEEDS_HUMAN]:
                logger.info(f"Prospect {prospect.id} already engaged ({prospect.status.value}). Aborting Unipile logic.")
                return {"status": "ignored", "reason": "global_circuit_breaker"}
            
            if prospect and prospect.status not in TERMINAL_STATES:
                intent = await classify_intent_service(text)
                logger.info(f"Message from {prospect.id}. Intent: {intent}")

                prospect.next_action_at = None # Freeze Sequence

                try:
                    transition_prospect(prospect, ProspectState.LINKEDIN_REPLIED)
                    if intent == "POSITIVE":
                        transition_prospect(prospect, ProspectState.MEETING_BOOKED)
                        # TODO: Trigger calendar invite email via resend here
                    else:
                        # NEGATIVE or NEUTRAL both pause and notify for now
                        transition_prospect(prospect, ProspectState.PAUSED_NUDGED)
                        # TODO: Dispatch nudge here on NEGATIVE
                except IllegalStateTransitionError as e:
                    logger.warning(f"Ignoring LinkedIn reply for prospect {prospect.id}: {e}")
                    return {"status": "ignored", "reason": "illegal_transition"}

                crm_synced = await sync_crm_after_reply(prospect, db=db, log_meeting=(intent == "POSITIVE"))
                if intent == "POSITIVE" and crm_synced:
                    await queue_calendar_booking(arq_pool, prospect)
                logger.info(f"Prospect {prospect.id} status updated to {prospect.status.value}")

    return {"status": "received"}

@router.post("/webhooks/email/inbound", status_code=status.HTTP_200_OK)
async def handle_email_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Listens for inbound email replies.
    """
    raw_body = await request.body()
    verify_resend_signature(request, raw_body)
    payload = json.loads(raw_body)

    sender_email = payload.get("from_email")
    text = payload.get("text", "")
    
    if not sender_email:
        return {"status": "ignored"}
        
    async with db.begin():
        query = select(Prospect).where(Prospect.email == sender_email).with_for_update()
        res = await db.execute(query)
        prospect = res.scalar_one_or_none()
        
        if not prospect:
            return {"status": "ignored", "reason": "Prospect not found"}
            
        if prospect.status in [ProspectState.PAUSED_NUDGED, ProspectState.MEETING_BOOKED, ProspectState.CALL_IN_PROGRESS, ProspectState.ENGAGED_ON_WEBSITE, ProspectState.ERROR_NEEDS_HUMAN]:
            logger.info(f"Prospect {prospect.id} already engaged ({prospect.status.value}). Aborting Email logic.")
            return {"status": "ignored", "reason": "global_circuit_breaker"}
            
        intent = await classify_intent_service(text)
        logger.info(f"Email from {prospect.id}. Intent: {intent}")
        prospect.next_action_at = None

        try:
            transition_prospect(prospect, ProspectState.EMAIL_REPLIED)
            if intent == "POSITIVE":
                transition_prospect(prospect, ProspectState.MEETING_BOOKED)
            else:
                transition_prospect(prospect, ProspectState.PAUSED_NUDGED)
                if intent == "NEGATIVE":
                    await enqueue_task(arq_pool, 'send_email_nudge_task', prospect.id)
        except IllegalStateTransitionError as e:
            logger.warning(f"Ignoring email reply for prospect {prospect.id}: {e}")
            return {"status": "ignored", "reason": "illegal_transition"}

        crm_synced = await sync_crm_after_reply(prospect, db=db, log_meeting=(intent == "POSITIVE"))
        if intent == "POSITIVE" and crm_synced:
            await queue_calendar_booking(arq_pool, prospect)

    return {"status": "received"}

# Resend delivery-event types that mean "never send to this address again".
_RESEND_BOUNCE_EVENT_TYPES = {"email.bounced", "email.complained"}

@router.post("/webhooks/email/events", status_code=status.HTTP_200_OK)
async def handle_email_delivery_event(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Listens for Resend's native delivery-status webhook (bounce/complaint
    events) and adds the recipient to the permanent bounce-suppression list
    (Sprint 3, item 1) - checked by send_native_email() ahead of every send.
    """
    raw_body = await request.body()
    verify_resend_signature(request, raw_body)
    payload = json.loads(raw_body)

    event_type = payload.get("type")
    if event_type not in _RESEND_BOUNCE_EVENT_TYPES:
        return {"status": "ignored", "reason": "not_a_bounce_event"}

    recipient = (payload.get("data") or {}).get("to")
    if isinstance(recipient, list):
        recipient = recipient[0] if recipient else None
    if not recipient:
        return {"status": "ignored", "reason": "no_recipient"}

    await suppress_bounced_email(db, recipient, reason=event_type)
    logger.warning(f"Suppressed {recipient} for future sends: {event_type}")
    return {"status": "received"}

@router.post("/webhooks/twilio/call-status", status_code=status.HTTP_200_OK)
async def handle_twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    CallStatus: str = Form(...),
    To: str = Form(...),
    CallSid: str = Form(None),
):
    """
    Handles Twilio Voice call status updates.
    """
    await verify_twilio_signature(request)
    logger.info(f"Twilio Call Status Webhook: {To} -> {CallStatus}")

    # Clean the 'To' number to match our DB
    cleaned_number = To.replace("+", "").strip()
    
    async with db.begin():
        # Find prospect by phone number, locking row
        query = select(Prospect).where(Prospect.phone_number.ilike(f"%{cleaned_number}%")).with_for_update()
        res = await db.execute(query)
        prospect = res.scalar_one_or_none()
        
        if not prospect:
            return {"status": "ignored", "reason": "Prospect not found"}

        if prospect.status in [ProspectState.PAUSED_NUDGED, ProspectState.MEETING_BOOKED, ProspectState.ENGAGED_ON_WEBSITE, ProspectState.ERROR_NEEDS_HUMAN]:
            logger.info(f"Prospect {prospect.id} already engaged ({prospect.status.value}). Aborting Twilio logic.")
            return {"status": "ignored", "reason": "global_circuit_breaker"}

        if prospect.status not in [
            ProspectState.CALL_IN_PROGRESS, ProspectState.CALL_CONNECTED,
            ProspectState.CALL_QUEUED, ProspectState.CALL_NO_ANSWER_1,
        ]:
            logger.info("Call status received but prospect not in a valid CALL state. Ignoring.")
            return {"status": "ignored"}

        tenant_id = prospect.tenant_id
        sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
        settings_obj = sett_res.scalar_one_or_none()
        dev_mode = settings_obj.dev_mode if settings_obj else False

        try:
            if CallStatus == "answered":
                # The call was picked up; the eventual "completed" event
                # resolves the actual outcome once the call ends.
                transition_prospect(prospect, ProspectState.CALL_CONNECTED)
                logger.info(f"Prospect {prospect.id} Call answered -> CALL_CONNECTED")

            elif CallStatus == "completed":
                # Sprint 7: the actual outcome (MEETING_BOOKED,
                # COMPLETED_DECLINED, ERROR_NEEDS_HUMAN, ...) is decided
                # turn-by-turn by the live conversation itself - see
                # services/voice_ai/orchestrator.py's _apply_decision, the
                # only place Voice AI's Decision Engine output changes
                # Prospect state. This webhook only knows the call ended;
                # it never assumes what happened during it.
                if CallSid:
                    await enqueue_task(arq_pool, 'summarize_voice_conversation_task', CallSid)

                if prospect.status == ProspectState.CALL_CONNECTED:
                    # The call ended without the conversation reaching any
                    # decisive turn-level outcome (e.g. dropped before the
                    # first recorded reply) - falls back to the same
                    # "talked, no meeting" bucket a live conversation would
                    # reach via next_action=CLOSE.
                    transition_prospect(prospect, ProspectState.COMPLETED_DECLINED)
                    prospect.next_action_at = None
                    await sync_crm_after_reply(prospect, db=db)
                logger.info(f"Prospect {prospect.id} Call Completed. Final status: {prospect.status.value}")

            elif CallStatus in ["busy", "no-answer", "failed", "canceled", "voicemail"]:
                if getattr(prospect, "call_attempts", 0) == 0:
                    prospect.call_attempts = 1
                    transition_prospect(prospect, ProspectState.CALL_NO_ANSWER_1)
                    now_utc = datetime.now(UTC)
                    if dev_mode:
                        prospect.next_action_at = now_utc + timedelta(seconds=60)
                    else:
                        prospect.next_action_at = get_next_business_time(now_utc + timedelta(days=1), getattr(settings_obj, 'timezone', 'America/New_York'))
                    logger.info(f"Prospect {prospect.id} Call {CallStatus}. call_attempts=1, State -> CALL_NO_ANSWER_1")
                elif prospect.call_attempts == 1:
                    prospect.call_attempts = 2
                    transition_prospect(prospect, ProspectState.CALL_NO_ANSWER_2)
                    now_utc = datetime.now(UTC)
                    if dev_mode:
                        prospect.next_action_at = now_utc + timedelta(seconds=60)
                    else:
                        prospect.next_action_at = get_next_business_time(now_utc + timedelta(days=1), getattr(settings_obj, 'timezone', 'America/New_York'))
                    logger.info(f"Prospect {prospect.id} Call {CallStatus}. call_attempts=2, State -> CALL_NO_ANSWER_2")
                else:
                    transition_prospect(prospect, ProspectState.UNRESPONSIVE_DEAD)
                    prospect.next_action_at = None
                    await sync_crm_after_reply(prospect, db=db)
                    logger.info(f"Prospect {prospect.id} Call {CallStatus}. Exhausted retries -> UNRESPONSIVE_DEAD")
        except IllegalStateTransitionError as e:
            logger.warning(f"Ignoring Twilio call status for prospect {prospect.id}: {e}")
            return {"status": "ignored", "reason": "illegal_transition"}

    return {"status": "received"}
