import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import redis.asyncio as aioredis

from app.database import get_db, get_redis
from app.models.schemas import Prospect, FollowUp, ActivityTimeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

@router.post("/webhooks/unipile", status_code=status.HTTP_200_OK)
async def handle_unipile_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Listens for inbound message events from Unipile. 
    If a prospect replies, instantly kill their sequence to prevent automated spamming.
    """
    payload = await request.json()
    logger.info(f"Received Unipile webhook: {payload.get('event')}")
    
    event_type = payload.get("event")
    if event_type == "message:received":
        data = payload.get("data", {})
        sender_linkedin_id = data.get("sender_id")
        text = data.get("text", "")
        
        if not sender_linkedin_id:
            return {"status": "ignored", "reason": "no sender_id"}

        # Look up the prospect by their provider tracking ID
        result = await db.execute(select(Prospect).where(Prospect.provider_id == sender_linkedin_id))
        prospect = result.scalar_one_or_none()
        
        if prospect and prospect.current_state != "CONVERSATION_ACTIVE":
            # 1. Update State
            prospect.current_state = "CONVERSATION_ACTIVE"
            
            # 2. Kill all pending scheduled follow-ups instantly
            await db.execute(
                update(FollowUp)
                .where(FollowUp.prospect_id == prospect.id, FollowUp.status == "PENDING")
                .values(status="CANCELED")
            )
            
            # 3. Log to activity timeline
            activity = ActivityTimeline(
                prospect_id=prospect.id,
                tenant_id=prospect.tenant_id,
                channel="LINKEDIN",
                event_type="REPLY",
                description=f"Received message: {text}"
            )
            db.add(activity)
            
            await db.commit()
            
            # Push real-time event updates
            event_payload = {
                "event_type": "PROSPECT_REPLIED",
                "prospect_id": prospect.id,
                "tenant_id": prospect.tenant_id,
                "state": "CONVERSATION_ACTIVE",
                "timestamp": datetime.utcnow().isoformat()
            }
            await redis.publish(f"tenant_updates:{prospect.tenant_id}", json.dumps(event_payload))
            
    return {"status": "received"}
