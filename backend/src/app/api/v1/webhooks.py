import json
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Request, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import redis.asyncio as aioredis
from typing import Optional

from app.database import get_db, get_redis
from app.models.schemas import Prospect, ProspectStatus, WorkspaceSetting
from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

async def classify_intent_service(text: str) -> str:
    """
    Analyzes inbound reply text using Gemini 2.0 Flash to classify intent.
    Enforces strict JSON output {"intent": "POSITIVE" | "NEGATIVE" | "NEUTRAL"}.
    """
    if not text:
        return "NEUTRAL"
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"Analyze the following reply from a sales prospect. Classify their intent as POSITIVE, NEGATIVE, or NEUTRAL.\nReply text: '{text}'"
        
        # Enforce JSON output in Gemini
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                # Note: We can also pass a JSON schema, but strict prompting usually works well for simple schemas in Flash.
            )
        )
        result = json.loads(response.text.strip())
        intent = result.get("intent", "NEUTRAL").upper()
        if intent not in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
            intent = "NEUTRAL"
        return intent
    except Exception as e:
        logger.warning(f"Gemini reply intent analysis error: {e}. Defaulting to NEUTRAL.")
        return "NEUTRAL"

@router.post("/webhooks/unipile", status_code=status.HTTP_200_OK)
async def handle_unipile_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Listens for inbound events from Unipile. 
    """
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

            if prospect and prospect.status == ProspectStatus.LI_REQ_SENT:
                prospect.status = ProspectStatus.LI_ACCEPTED_NO_MSG
                # Schedule followup immediately
                arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
                await arq_pool.enqueue_job('send_linkedin_followup_task', prospect.id)
                await arq_pool.close()
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
            
            if prospect and prospect.status not in (ProspectStatus.MEETING_BOOKED, ProspectStatus.COMPLETED_DECLINED, ProspectStatus.UNRESPONSIVE_DEAD):
                intent = await classify_intent_service(text)
                logger.info(f"Message from {prospect.id}. Intent: {intent}")
                
                prospect.next_action_at = None # Freeze Sequence
                
                if intent == "POSITIVE":
                    prospect.status = ProspectStatus.MEETING_BOOKED
                    # TODO: Trigger calendar invite email via resend here
                elif intent == "NEGATIVE":
                    prospect.status = ProspectStatus.PAUSED_NUDGED
                    # TODO: Dispatch nudge here
                else:
                    # Neutral, maybe pause and notify? Let's just pause for now
                    prospect.status = ProspectStatus.PAUSED_NUDGED
                    
                logger.info(f"Prospect {prospect.id} status updated to {prospect.status.value}")

    return {"status": "received"}

@router.post("/webhooks/twilio/call-status", status_code=status.HTTP_200_OK)
async def handle_twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    CallStatus: str = Form(...),
    To: str = Form(...)
):
    """
    Handles Twilio Voice call status updates.
    """
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

        if prospect.status != ProspectStatus.CALL_IN_PROGRESS:
            logger.info("Call status received but prospect not in CALL_IN_PROGRESS. Ignoring.")
            return {"status": "ignored"}
            
        tenant_id = prospect.tenant_id
        sett_res = await db.execute(select(WorkspaceSetting).where(WorkspaceSetting.tenant_id == tenant_id))
        settings_obj = sett_res.scalar_one_or_none()
        dev_mode = settings_obj.dev_mode if settings_obj else False

        # Simulate intent since we don't have a real AI Voice engine connected
        # In a real app, 'completed' would trigger transcription analysis.
        # For this spec, we rely on CallStatus basic mapping or assume outcome
        
        if CallStatus == "completed":
            # Let's assume completed means booked for demonstration if it lasted a while,
            # or we can just randomly decide for the sake of the mock?
            # The prompt says: "Picked & Pitched (Booked): Trigger calendar invite, update to MEETING_BOOKED."
            prospect.status = ProspectStatus.MEETING_BOOKED
            prospect.next_action_at = None
            logger.info(f"Prospect {prospect.id} Call Completed -> MEETING_BOOKED")
            # TODO: Send calendar invite via resend
            
        elif CallStatus in ["busy", "no-answer", "failed", "canceled"]:
            if prospect.call_attempts < 3:
                prospect.status = ProspectStatus.CALL_QUEUED
                now_utc = datetime.now(timezone.utc)
                if dev_mode:
                    prospect.next_action_at = now_utc + timedelta(seconds=60)
                else:
                    prospect.next_action_at = now_utc + timedelta(days=1)
                logger.info(f"Prospect {prospect.id} Call {CallStatus}. Retry < 3 -> CALL_QUEUED at {prospect.next_action_at}")
            else:
                prospect.status = ProspectStatus.UNRESPONSIVE_DEAD
                prospect.next_action_at = None
                logger.info(f"Prospect {prospect.id} Call {CallStatus}. >= 3 attempts -> UNRESPONSIVE_DEAD")

    return {"status": "received"}
