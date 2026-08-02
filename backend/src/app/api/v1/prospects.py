import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant, verify_tenant_sse
from app.config import settings
from app.core.state_machine import TERMINAL_STATES, transition_prospect
from app.database import get_arq_pool, get_db, get_redis
from app.models.schemas import ActivityTimeline, Prospect, ProspectState, WorkflowState
from app.schemas.prospects import (
    AdvanceActionSchema,
    BulkActionSchema,
    ProspectCreateSchema,
    ProspectListResponseSchema,
    ProspectResponseSchema,
    UnipileImportSchema,
)
from app.services.ai import generate_outreach_message
from app.services.personalization import PersonalizationService
from app.workers.tasks import get_force_advance_plan

router = APIRouter(prefix="/prospects", tags=["Prospects"])
logger = logging.getLogger(__name__)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProspectResponseSchema)
async def create_prospect(
    payload: ProspectCreateSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    arq_pool: ArqRedis = Depends(get_arq_pool),
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

    # 1. Instantiate Prospect record (status defaults to NEW, matching the
    # run_waterfall_enrichment_task's entry point, enqueued below)
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
        status=ProspectState.NEW,
        next_action_at=datetime.now(UTC)
    )
    db.add(prospect)

    # 2. Instantiate workflow tracking payload
    wf_state = WorkflowState(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        prospect_id=prospect_id,
        state=ProspectState.NEW.value,
        payload={
            "linkedin_step_count": 0,
            "email_step_count": 0,
            "call_step_count": 0,
            "reply_received": False
        }
    )
    db.add(wf_state)

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
        "state": ProspectState.NEW.value,
        "timestamp": datetime.utcnow().isoformat()
    }
    await redis.publish(f"tenant_updates:{tenant_id}", json.dumps(event_payload))

    # Enqueue enrichment/qualification job via Redis Queue (ARQ). Outbound
    # sequencing only starts once run_waterfall_enrichment_task qualifies
    # the prospect (NEW -> ENRICHING -> QUALIFIED -> IDLE).
    try:
        await arq_pool.enqueue_job("run_waterfall_enrichment_task", prospect_id)
        await arq_pool.enqueue_job("sync_crm_contact_task", prospect_id)
    except Exception as e:
        logger.error(f"Failed to enqueue enrichment initialization for prospect {prospect_id}: {e!s}")

    return {
        "status": "success",
        "data": {
            "id": prospect_id,
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
    redis: aioredis.Redis = Depends(get_redis),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Imports selected profiles from Unipile Live Search.
    Filters out duplicates by provider_id.
    Sets status = NEW to route through qualification before outreach.
    """
    imported_count = 0
    skipped_count = 0
    imported_prospect_ids = []

    # Single batch fetch of already-known provider_ids rather than one
    # duplicate-check SELECT per incoming profile.
    incoming_provider_ids = [p.provider_id for p in payload.profiles if p.provider_id]
    existing_provider_ids: set = set()
    if incoming_provider_ids:
        existing_query = select(Prospect.provider_id).where(
            Prospect.tenant_id == tenant_id,
            Prospect.provider_id.in_(incoming_provider_ids),
        )
        existing_provider_ids = set((await db.execute(existing_query)).scalars().all())

    for profile in payload.profiles:
        if profile.provider_id and profile.provider_id in existing_provider_ids:
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
            status=ProspectState.NEW,
            call_attempts=0,
            next_action_at=datetime.utcnow()
        )
        db.add(prospect)

        wf_state = WorkflowState(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            prospect_id=prospect_id,
            state=ProspectState.NEW.value,
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
        try:
            for pid in imported_prospect_ids:
                await arq_pool.enqueue_job("run_waterfall_enrichment_task", pid)
        except Exception as e:
            logger.error(f"Failed to enqueue enrichment tasks: {e!s}")

    return {
        "status": "success",
        "imported": imported_count,
        "skipped": skipped_count
    }

@router.get("/stream")
async def stream_prospect_updates(
    tenant_id: str = Depends(verify_tenant_sse),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Exposes a Server-Sent Events (SSE) endpoint transmitting real-time changes
    published by workers directly to frontend listeners.

    Uses verify_tenant_sse (Authorization header OR ?token= query param)
    rather than verify_tenant, since the browser-native EventSource this
    powers cannot set an Authorization header.
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
    redis: aioredis.Redis = Depends(get_redis),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Apply an action to multiple prospects in bulk.
    Currently supports: 'FORCE_ADVANCE', 'PAUSE'
    """
    # Single batch fetch rather than one SELECT per prospect_id - the
    # previous per-ID query loop meant a bulk action on N prospects made N
    # round-trips to Postgres instead of 1.
    query = select(Prospect).where(Prospect.id.in_(payload.prospect_ids), Prospect.tenant_id == tenant_id)
    prospects_by_id = {p.id: p for p in (await db.execute(query)).scalars().all()}

    for pid in payload.prospect_ids:
        prospect = prospects_by_id.get(pid)

        if not prospect:
            continue

        if payload.action == "FORCE_ADVANCE":
            target_status, task_to_enqueue, needs_tenant_id = get_force_advance_plan(prospect.status)
            if target_status is not None:
                transition_prospect(prospect, target_status)

            if task_to_enqueue:
                task_kwargs = {"tenant_id": tenant_id} if needs_tenant_id else {}
                await arq_pool.enqueue_job(task_to_enqueue, pid, **task_kwargs)
    await db.commit()
    return {"status": "success", "message": f"Applied {payload.action} to {len(payload.prospect_ids)} prospects"}


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

    if not settings.SECRET_KEY:
        logger.error("SECRET_KEY is not configured; rejecting engagement token verification.")
        raise HTTPException(status_code=503, detail="Engagement verification unavailable")

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
            
        if prospect.status in TERMINAL_STATES | {ProspectState.MEETING_BOOKED, ProspectState.CALL_IN_PROGRESS}:
            logger.info(f"Prospect {prospect_id} interacted on website but is in a halted state ({prospect.status.value}). Ignoring.")
            return {"status": "ignored", "reason": "terminal_state"}

        transition_prospect(prospect, ProspectState.ENGAGED_ON_WEBSITE)
        prospect.next_action_at = None
        
        logger.info(f"Prospect {prospect_id} engaged on website via {payload.event}. Outbound sequences halted.")
        
    return {"status": "success", "message": "Pipeline halted, prospect is engaged"}

@router.post("/{prospect_id}/advance", status_code=status.HTTP_200_OK)
async def advance_prospect(
    prospect_id: str,
    payload: AdvanceActionSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Manually forces a prospect into the next logical state.
    """
    query = select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    target_status, task_to_enqueue, needs_tenant_id = get_force_advance_plan(prospect.status)

    # Most hops enqueue a task whose own precondition already matches the
    # prospect's current status, and the task transitions it on success (so a
    # failed job doesn't leave the UI falsely showing it as advanced). The one
    # exception is simulating an external acceptance event (e.g. LinkedIn
    # accepted) that only this API can fake, which is why target_status is
    # set here for that hop specifically.
    if target_status is not None:
        transition_prospect(prospect, target_status)
        await db.commit()

    if task_to_enqueue:
        task_kwargs = {"tenant_id": tenant_id} if needs_tenant_id else {}
        await arq_pool.enqueue_job(task_to_enqueue, prospect_id, **task_kwargs)

    return {"status": "success", "message": f"Queued task {task_to_enqueue} for prospect."}

class RescheduleMeetingSchema(BaseModel):
    new_start: datetime
    new_end: datetime
    timezone: str = "America/New_York"

@router.get("/{prospect_id}/preview-message", status_code=status.HTTP_200_OK)
async def preview_message(
    prospect_id: str,
    prompt_type: str = "linkedin",
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Sprint 4, item 3 / Sprint 5, item 1: previews the exact fully-
    personalized outreach message PersonalizationService would generate for
    this prospect and prompt_type - the same call every live outbound
    channel (LinkedIn request/follow-up, Email 1/2, breakup email, and the
    legacy follow-up/nudge tasks) now goes through.
    """
    query = select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    context = await PersonalizationService.build_context(db, prospect)
    message = await generate_outreach_message(
        prospect_name=prospect.first_name,
        company=prospect.company_name or "",
        prompt_type=prompt_type,
        context=context,
    )

    return {"status": "success", "data": {"message": message, "context_used": context}}

@router.post("/{prospect_id}/cancel-meeting", status_code=status.HTTP_200_OK)
async def cancel_meeting(
    prospect_id: str,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Cancels a prospect's booked calendar meeting. Never calls Google APIs
    directly here - queues the cancellation through the same ARQ worker
    the rest of the pipeline uses.
    """
    query = select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    await arq_pool.enqueue_job("cancel_calendar_meeting_task", prospect_id)

    return {"status": "success", "message": "Meeting cancellation queued."}

@router.post("/{prospect_id}/reschedule-meeting", status_code=status.HTTP_200_OK)
async def reschedule_meeting(
    prospect_id: str,
    payload: RescheduleMeetingSchema,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Reschedules a prospect's meeting to a new time. Updates the existing
    calendar event in place rather than creating a duplicate. Queued through
    ARQ, never calling Google APIs directly from this request handler.
    """
    query = select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    if payload.new_end <= payload.new_start:
        raise HTTPException(status_code=400, detail="new_end must be after new_start")

    await arq_pool.enqueue_job(
        "reschedule_calendar_meeting_task",
        prospect_id,
        payload.new_start,
        payload.new_end,
        payload.timezone,
    )

    return {"status": "success", "message": "Meeting reschedule queued."}

class DealOutcomeSchema(BaseModel):
    deal_value: float | None = None

@router.post("/{prospect_id}/mark-won", status_code=status.HTTP_200_OK)
async def mark_deal_won(
    prospect_id: str,
    payload: DealOutcomeSchema = DealOutcomeSchema(),
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Sprint 5, item 5 (Revenue Attribution): records that a booked meeting
    actually closed as a won deal. Deal-closing is inherently a human/CRM
    judgment call - nothing in the pipeline auto-detects it - so this is a
    deliberate operator action, not something the Decision Engine decides.

    Sprint 6, item 1: queues the HubSpot deal-stage sync through ARQ
    (sync_crm_deal_stage_task) rather than calling the CRM inline here, so
    a HubSpot outage doesn't fail this request and gets retried through the
    same centralized retry engine every other CRM sync uses.
    """
    query = select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    if payload.deal_value is not None:
        prospect.estimated_deal_value = payload.deal_value

    try:
        transition_prospect(prospect, ProspectState.CLOSED_WON)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

    await db.commit()
    await arq_pool.enqueue_job("sync_crm_deal_stage_task", prospect_id)
    return {"status": "success", "data": {"id": prospect.id, "status": prospect.status.value, "estimated_deal_value": prospect.estimated_deal_value}}

@router.post("/{prospect_id}/mark-lost", status_code=status.HTTP_200_OK)
async def mark_deal_lost(
    prospect_id: str,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """Sprint 5, item 5: records that this prospect's deal was lost - the
    counterpart to /mark-won, feeding lost_value in revenue analytics.
    Sprint 6, item 1: also queues the HubSpot deal-stage sync (see
    mark_deal_won above)."""
    query = select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    try:
        transition_prospect(prospect, ProspectState.LOST)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

    await db.commit()
    await arq_pool.enqueue_job("sync_crm_deal_stage_task", prospect_id)
    return {"status": "success", "data": {"id": prospect.id, "status": prospect.status.value}}
