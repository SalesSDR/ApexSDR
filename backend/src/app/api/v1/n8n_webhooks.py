from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.services.agent import agent_orchestrator
from app.models.schemas import Prospect, SequenceRule, FollowUp
from app.core.state_machine import StateMachine
import logging
import json

router = APIRouter(prefix="/n8n", tags=["n8n-webhooks"])
logger = logging.getLogger(__name__)

# --- Pydantic Schemas for Strict Typing ---

class ProspectEnrichedPayload(BaseModel):
    prospect_id: str
    email: Optional[EmailStr] = None
    linkedin_url: Optional[str] = None
    company: str
    enriched_context: str

class IncomingReplyPayload(BaseModel):
    prospect_id: str
    channel: str # 'email' or 'linkedin'
    message: str

class WebhookResponse(BaseModel):
    status: str
    message: str

# --- Endpoints ---

@router.post("/trigger-outreach", response_model=WebhookResponse)
async def trigger_n8n_outreach(payload: ProspectEnrichedPayload, background_tasks: BackgroundTasks):
    """
    Receives enriched lead data from n8n and initializes the prospect state machine.
    """
    logger.info(f"Received n8n outreach trigger for prospect {payload.prospect_id}")
    
    # Ideally, we would update DB state here and queue an ARQ job.
    # For now, we simulate starting the Gemini agent drafting process in the background.
    async def process_outreach():
        try:
            # We use our newly built orchestrator to draft an initial message
            draft = await agent_orchestrator.draft_channel_outreach(
                channel="email" if payload.email else "linkedin",
                tone="professional yet approachable",
                context=payload.enriched_context
            )
            logger.info(f"Agent successfully drafted outreach for {payload.prospect_id}: {draft[:50]}...")
            # Here we would send it back to n8n or unipile to actually dispatch.
        except Exception as e:
            logger.error(f"Failed to process outreach for {payload.prospect_id}: {e}")

    background_tasks.add_task(process_outreach)
    
    return WebhookResponse(status="success", message="Outreach trigger accepted and queued.")


@router.post("/reply-received", response_model=WebhookResponse)
async def receive_n8n_reply(payload: IncomingReplyPayload, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Receives incoming replies categorized/processed through n8n.
    """
    logger.info(f"Received n8n reply webhook for prospect {payload.prospect_id} via {payload.channel}")

    async def process_reply():
        try:
            # Utilize Gemini Agent Tool Calling to classify intent strictly
            classification = await agent_orchestrator.classify_intent(payload.message)
            intent = classification.get("intent", "UNKNOWN")
            logger.info(f"Agent classified reply from {payload.prospect_id} as: {intent}")
            
            # Here we would update prospect state (e.g. pause sequence if intent is MEETING_REQUESTED)
            if intent in ["MEETING_REQUESTED", "REFUSAL", "QUESTION"]:
                logger.info(f"Checking sequence rules for {payload.prospect_id} due to intent: {intent}")
                
                # Fetch prospect and tenant
                p_res = await db.execute(select(Prospect).where(Prospect.id == payload.prospect_id))
                prospect = p_res.scalar_one_or_none()
                if not prospect:
                    return

                # Fetch sequence rule
                rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == prospect.tenant_id))
                rule = rule_res.scalar_one_or_none()
                
                action = rule.response_handling_action if rule else "PAUSE_AND_NOTIFY"
                
                if action == "PAUSE_AND_NOTIFY":
                    logger.info("Sequence Rule is PAUSE_AND_NOTIFY. Transitioning to CONVERSATION_ACTIVE.")
                    
                    # Update prospect status
                    prospect.current_state = "CONVERSATION_ACTIVE"
                    
                    # Cancel any pending follow ups
                    f_res = await db.execute(select(FollowUp).where(
                        FollowUp.prospect_id == prospect.id,
                        FollowUp.status == "PENDING"
                    ))
                    for f in f_res.scalars():
                        f.status = "CANCELED"
                        
                    await db.commit()
                    
                    # In a real app we'd dispatch an SSE event and notify assigned_lead_owner_id
                else:
                    logger.info("Sequence Rule is CONTINUE. Automated follow ups remain active.")
                    
        except Exception as e:
            logger.error(f"Failed to process reply for {payload.prospect_id}: {e}")

    background_tasks.add_task(process_reply)
    
    return WebhookResponse(status="success", message="Reply accepted and queued for classification.")
