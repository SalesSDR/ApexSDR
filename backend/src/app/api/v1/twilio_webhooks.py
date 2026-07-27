from fastapi import APIRouter, Request, BackgroundTasks, Form
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.schemas import Prospect
from app.core.state_machine import StateMachine
from app.core.sequence_engine import SequenceEngine
from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings
from app.database import get_redis
import logging
import json

router = APIRouter(prefix="/twilio", tags=["twilio-webhooks"])
logger = logging.getLogger(__name__)

@router.post("/status")
async def receive_twilio_status(
    background_tasks: BackgroundTasks,
    CallSid: str = Form(...),
    CallStatus: str = Form(...)
):
    """
    Receives CallStatus updates from Twilio.
    When a call completes, we update the state and schedule the next step.
    """
    logger.info(f"Received Twilio CallStatus webhook: CallSid={CallSid}, Status={CallStatus}")

    async def process_call_status():
        if CallStatus in ["completed", "no-answer", "busy", "failed"]:
            async with AsyncSessionLocal() as db:
                try:
                    # Look up prospect by twilio_call_sid in their workflow state
                    from app.models.schemas import WorkflowState
                    
                    # Note: Since the sid is in a JSONB payload, we need to query appropriately
                    # For simplicity, we can do a full scan or if we stored it properly.
                    # As a quick workaround, we can find it via the payload object
                    # Since sqlalchemy JSONB allows `payload->>'twilio_call_sid'`
                    
                    w_res = await db.execute(
                        select(WorkflowState)
                        .where(WorkflowState.payload['twilio_call_sid'].astext == CallSid)
                    )
                    wf_state = w_res.scalar_one_or_none()
                    
                    if not wf_state:
                        logger.warning(f"Could not find WorkflowState with twilio_call_sid {CallSid}")
                        return

                    prospect_id = wf_state.prospect_id
                    
                    p_res = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
                    prospect = p_res.scalar_one_or_none()
                    
                    if not prospect:
                        return

                    from app.database import redis_client
                    redis = redis_client
                    
                    # Update State
                    await StateMachine.transition(
                        db=db,
                        redis=redis,
                        prospect_id=prospect.id,
                        new_state="CALL_COMPLETED",
                        event_trigger=f"Twilio Webhook: {CallStatus}"
                    )
                    
                    # Immediately schedule Step 4 (Follow-up Email)
                    # We get the next scheduled action from SequenceEngine
                    # Wait, in the manual requirement: "Immediately schedule Step 4 (Follow-up Email) in SequenceEngine."
                    # We can use the sequence engine to get the next step, assuming current_channel was CALL
                    
                    # Let's see what SequenceEngine says for current_channel="CALL"
                    action_meta = await SequenceEngine.get_next_scheduled_action(
                        db=db,
                        tenant_id=prospect.tenant_id,
                        current_step=1, # Twilio call might be an escalation, SequenceEngine figures it out based on limits
                        current_channel="CALL"
                    )
                    
                    # Wait, the instruction says "Immediately schedule Step 4 (Follow-up Email)"
                    # I will trigger execute_follow_up_task directly or let SequenceEngine handle it.
                    next_channel = action_meta["next_channel"]
                    next_seq = action_meta["next_step"]
                    
                    if next_channel == "EMAIL":
                        # We just enqueue the email task directly via ARQ
                        arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
                        try:
                            # Usually there's a delay, but we'll enqueue it immediately or with minor defer
                            await arq_pool.enqueue_job(
                                'execute_follow_up_task',
                                prospect.id,
                                sequence_number=next_seq,
                                tenant_id=prospect.tenant_id,
                                _defer_by=10
                            )
                        finally:
                            await arq_pool.close()
                    
                    await db.commit()

                except Exception as e:
                    logger.error(f"Failed to process Twilio status for CallSid {CallSid}: {e}")

    background_tasks.add_task(process_call_status)
    return {"status": "accepted"}
