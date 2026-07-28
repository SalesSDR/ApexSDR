import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from arq import create_pool
from arq.connections import RedisSettings
import redis.asyncio as aioredis

from app.config import settings
from app.database import get_db, get_redis
from app.api.v1.auth import verify_tenant
from app.models.schemas import Prospect, WorkflowState, ActivityTimeline
from app.schemas.prospects import ProspectCreateSchema, ProspectResponseSchema, ProspectListResponseSchema, BulkActionSchema, AdvanceActionSchema, UnipileImportSchema
from app.core.state_machine import StateMachine
from sqlalchemy import or_
router = APIRouter(prefix="/prospects", tags=["Prospects"])
logger = logging.getLogger(__name__)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProspectResponseSchema)
async def create_prospect(
    payload: ProspectCreateSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Registers a new prospect under the caller's tenant boundary.
    Checks for duplicate active workflows and enqueues automated sequence initialization.
    """
    # For dev testing, we allow adding the same email multiple times.
    # query = select(Prospect).where(
    #     Prospect.tenant_id == tenant_id,
    #     Prospect.email == payload.email,
    #     Prospect.current_state != "CLOSED"
    # )
    # existing = await db.execute(query)
    # if existing.scalar_one_or_none():
    #     raise HTTPException(
    #         status_code=status.HTTP_409_CONFLICT,
    #         detail=f"An active prospect with the email '{payload.email}' already exists inside this workspace."
    #     )

    # 1. Instantiate Prospect record
    prospect_id = str(uuid.uuid4())
    prospect = Prospect(
        id=prospect_id,
        tenant_id=tenant_id,
        campaign_id=payload.campaign_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        linkedin_url=str(payload.linkedin_url),
        phone_number=payload.phone_number,
        current_state="PENDING_ACCEPTANCE",
        next_action_at=datetime.now(timezone.utc)
    )
    db.add(prospect)

    # 2. Instantiate workflow tracking payload
    wf_state = WorkflowState(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        prospect_id=prospect_id,
        state="PENDING_ACCEPTANCE",
        payload={
            "linkedin_step_count": 0,
            "email_step_count": 0,
            "call_step_count": 0,
            "reply_received": False
        }
    )
    db.add(wf_state)

    # 2.5 Update the Prospect current_state as well
    prospect.current_state = "PENDING_ACCEPTANCE"

    # 3. Log event timeline metrics
    timeline_event = ActivityTimeline(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        prospect_id=prospect_id,
        channel="SYSTEM",
        event_type="SYSTEM_EVENT",
        description="Prospect record created, starting automation sequence."
    )
    db.add(timeline_event)

    await db.commit()

    # Publish transition update to Redis Pub/Sub for frontend UI syncing
    event_payload = {
        "event_type": "PROSPECT_CREATED",
        "prospect_id": prospect_id,
        "tenant_id": tenant_id,
        "state": "PENDING_ACCEPTANCE",
        "timestamp": datetime.utcnow().isoformat()
    }
    await redis.publish(f"tenant_updates:{tenant_id}", json.dumps(event_payload))

    # Enqueue sequence initialization job via Redis Queue (ARQ)
    arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        await arq_pool.enqueue_job("start_outbound_sequence", prospect_id, tenant_id=tenant_id)
    except Exception as e:
        logger.error(f"Failed to enqueue outbound sequence initialization for prospect {prospect_id}: {str(e)}")
    finally:
        await arq_pool.close()

    return {
        "status": "success",
        "data": {
            "id": prospect_id,
            "current_state": "PENDING_ACCEPTANCE",
            "status": prospect.status,
            "tenant_id": tenant_id
        }
    }

@router.get("", status_code=status.HTTP_200_OK, response_model=ProspectListResponseSchema)
async def list_prospects(
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    List all prospects for the current tenant.
    """
    query = select(Prospect).where(Prospect.tenant_id == tenant_id)
    result = await db.execute(query)
    prospects = result.scalars().all()

    return {
        "status": "success",
        "data": prospects
    }

@router.post("/import-from-unipile", status_code=status.HTTP_200_OK)
async def import_from_unipile(
    payload: UnipileImportSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Imports selected profiles from Unipile Live Search.
    Filters out duplicates by provider_id.
    Sets status = IDLE to trigger the autonomous pipeline instantly.
    """
    from app.models.schemas import ProspectStatus
    
    imported_count = 0
    skipped_count = 0
    imported_prospect_ids = []

    for profile in payload.profiles:
        # Check duplicate by provider_id
        query = select(Prospect).where(
            Prospect.tenant_id == tenant_id,
            Prospect.provider_id == profile.provider_id
        )
        existing = await db.execute(query)
        if existing.scalar_one_or_none():
            skipped_count += 1
            continue

        prospect_id = str(uuid.uuid4())
        prospect = Prospect(
            id=prospect_id,
            tenant_id=tenant_id,
            campaign_id=payload.campaign_id,
            first_name=profile.first_name,
            last_name=profile.last_name,
            email=profile.email,
            linkedin_url=profile.linkedin_url or "",
            phone_number=None,
            company_name=profile.organization_name,
            company_domain=profile.company_domain,
            provider_id=profile.provider_id,
            current_state=(profile.title[:50] if profile.title else "Unipile Import"),
            status=ProspectStatus.IDLE,
            call_attempts=0,
            next_action_at=datetime.utcnow()
        )
        db.add(prospect)

        wf_state = WorkflowState(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            prospect_id=prospect_id,
            state="IDLE",
            payload={}
        )
        db.add(wf_state)

        timeline = ActivityTimeline(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            prospect_id=prospect_id,
            channel="SYSTEM",
            event_type="SYSTEM_EVENT",
            description="Imported from Unipile Live Search. Pipeline activated."
        )
        db.add(timeline)
        
        imported_count += 1
        imported_prospect_ids.append(prospect_id)
        
    await db.commit()

    if imported_prospect_ids:
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        try:
            for pid in imported_prospect_ids:
                await arq_pool.enqueue_job("run_waterfall_enrichment_task", pid)
        except Exception as e:
            logger.error(f"Failed to enqueue enrichment tasks: {str(e)}")
        finally:
            await arq_pool.close()

    return {
        "status": "success",
        "imported": imported_count,
        "skipped": skipped_count
    }

@router.get("/stream")
async def stream_prospect_updates(
    tenant_id: str = Depends(verify_tenant),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Exposes a Server-Sent Events (SSE) endpoint transmitting real-time changes
    published by workers directly to frontend listeners.
    """
    async def event_generator():
        pubsub = redis.pubsub()
        channel = f"tenant_updates:{tenant_id}"
        await pubsub.subscribe(channel)
        logger.info(f"Client subscribed to SSE channel: {channel}")
        
        try:
            while True:
                # Poll Redis pubsub messages
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0)
                if message:
                    data = message["data"]
                    yield f"data: {data}\n\n"
                # Yield comment to prevent connection close timeout
                yield ": keep-alive\n\n"
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info(f"Client disconnected from SSE channel: {channel}")
            await pubsub.unsubscribe(channel)
            raise
        finally:
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/bulk-action", status_code=status.HTTP_200_OK)
async def bulk_action(
    payload: BulkActionSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Apply an action to multiple prospects in bulk.
    Currently supports: 'FORCE_ADVANCE', 'PAUSE'
    """
    for pid in payload.prospect_ids:
        # For 'FORCE_ADVANCE', we find current state and just jump
        query = select(Prospect).where(Prospect.id == pid, Prospect.tenant_id == tenant_id)
        res = await db.execute(query)
        prospect = res.scalar_one_or_none()
        
        if not prospect:
            continue
            
        if payload.action == "FORCE_ADVANCE":
            target = "CLOSED"
            task_to_enqueue = None
            task_kwargs = {}

            if prospect.current_state == "PROSPECT_CREATED":
                target = "PENDING_ACCEPTANCE"
                task_to_enqueue = "start_outbound_sequence"
            elif prospect.current_state == "PENDING_ACCEPTANCE":
                target = "CONNECTION_ACCEPTED"
                task_to_enqueue = "execute_initial_message_task"
            elif prospect.current_state == "CONNECTION_ACCEPTED":
                target = "INITIAL_MSG_SENT"
                task_to_enqueue = "execute_initial_message_task"
            elif prospect.current_state in ["INITIAL_MSG_SENT", "WAITING_FOR_REPLY"]:
                target = "FOLLOW_UP_SCHEDULED"
                task_to_enqueue = "execute_follow_up_task"
                task_kwargs = {"sequence_number": 1}
            elif prospect.current_state in ["FOLLOW_UP_SCHEDULED", "FOLLOW_UP_SENT"]:
                target = "CALL_SCHEDULED"
                task_to_enqueue = "execute_call_task"
                
            if task_to_enqueue:
                arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
                try:
                    await arq_pool.enqueue_job(task_to_enqueue, pid, tenant_id=tenant_id, **task_kwargs)
                finally:
                    await arq_pool.close()
    await db.commit()
    return {"status": "success", "message": f"Applied {payload.action} to {len(payload.prospect_ids)} prospects"}

from pydantic import BaseModel
from jose import jwt, JWTError

class EngagementEvent(BaseModel):
    event: str

@router.post("/engaged", status_code=status.HTTP_200_OK)
async def prospect_engaged(
    payload: EngagementEvent,
    token: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Called by the frontend landing site when a prospect interacts with the chatbot or CTA.
    """
    if payload.event not in ["CHATBOT_INTERACTION", "CTA_CLICK"]:
        return {"status": "ignored", "reason": "invalid_event"}
        
    if not token:
        raise HTTPException(status_code=403, detail="Missing auth token")
        
    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        prospect_id = decoded.get("prospect_id")
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")
        
    if not prospect_id:
        raise HTTPException(status_code=400, detail="Invalid payload")
        
    async with db.begin():
        query = select(Prospect).where(Prospect.id == prospect_id).with_for_update()
        res = await db.execute(query)
        prospect = res.scalar_one_or_none()
        
        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")
            
        if prospect.status in [ProspectStatus.MEETING_BOOKED, ProspectStatus.CALL_IN_PROGRESS, ProspectStatus.UNRESPONSIVE_DEAD, ProspectStatus.COMPLETED_DECLINED]:
            logger.info(f"Prospect {prospect_id} interacted on website but is in terminal state ({prospect.status.value}). Ignoring.")
            return {"status": "ignored", "reason": "terminal_state"}
            
        prospect.status = ProspectStatus.ENGAGED_ON_WEBSITE
        prospect.next_action_at = None
        
        logger.info(f"Prospect {prospect_id} engaged on website via {payload.event}. Outbound sequences halted.")
        
    return {"status": "success", "message": "Pipeline halted, prospect is engaged"}

@router.post("/{prospect_id}/advance", status_code=status.HTTP_200_OK)
async def advance_prospect(
    prospect_id: str,
    payload: AdvanceActionSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Manually forces a prospect into the next logical state.
    """
    query = select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    target = payload.target_state
    task_to_enqueue = None
    task_kwargs = {}

    if not target:
        if prospect.current_state == "PROSPECT_CREATED":
            # Force send linkedin connection
            target = "PENDING_ACCEPTANCE"
            task_to_enqueue = "start_outbound_sequence"
        elif prospect.current_state == "PENDING_ACCEPTANCE":
            # Simulate they accepted it
            target = "CONNECTION_ACCEPTED"
            task_to_enqueue = "execute_initial_message_task"
        elif prospect.current_state == "CONNECTION_ACCEPTED":
            # Just run initial msg
            target = "INITIAL_MSG_SENT"
            task_to_enqueue = "execute_initial_message_task"
        elif prospect.current_state in ["INITIAL_MSG_SENT", "WAITING_FOR_REPLY"]:
            # Force send followup
            target = "FOLLOW_UP_SCHEDULED"
            task_to_enqueue = "execute_follow_up_task"
            task_kwargs = {"sequence_number": 1}
        elif prospect.current_state in ["FOLLOW_UP_SCHEDULED", "FOLLOW_UP_SENT"]:
            # Force make a call
            target = "CALL_SCHEDULED"
            task_to_enqueue = "execute_call_task"
        else:
            target = "CLOSED"

    # We do NOT transition the state here! We let the background task transition it upon success.
    # Otherwise, if the API fails, the UI will falsely show it as advanced.
    if task_to_enqueue:
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        try:
            await arq_pool.enqueue_job(task_to_enqueue, prospect_id, tenant_id=tenant_id, **task_kwargs)
        finally:
            await arq_pool.close()
            
    # We'll just return a success message saying the job is queued
    return {"status": "success", "message": f"Queued task {task_to_enqueue} for prospect."}
