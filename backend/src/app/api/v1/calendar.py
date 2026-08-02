import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.database import get_db
from app.models.schemas import CalendarSyncLog, CalendarSyncStatus, Prospect, ProspectState
from app.services.calendar.factory import get_calendar_adapter
from app.services.calendar.service import CalendarService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])

# Availability is a read-only lookup with no state to mutate, retry, or
# de-duplicate - unlike booking/updating/cancelling events, it's answered
# directly rather than queued through ARQ, since there's nothing here that
# benefits from the queue's retry/duplicate-avoidance semantics.
@router.get("/availability", status_code=status.HTTP_200_OK)
async def get_availability(
    start: datetime = Query(...),
    end: datetime = Query(...),
    timezone_name: str = Query("America/New_York", alias="timezone"),
    tenant_id: str = Depends(verify_tenant),
):
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start")

    async with httpx.AsyncClient() as http_client:
        calendar_service = CalendarService(get_calendar_adapter(http_client))
        try:
            busy_slots = await calendar_service.get_busy_slots(start, end, timezone_name)
        except Exception as e:
            logger.error(f"Calendar availability lookup failed: {e}")
            raise HTTPException(status_code=502, detail="Calendar availability lookup failed")

    return {
        "status": "success",
        "data": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": timezone_name,
            "busy_slots": [{"start": s.start.isoformat(), "end": s.end.isoformat()} for s in busy_slots],
            "is_free": len(busy_slots) == 0,
        },
    }


@router.get("/sync-status", status_code=status.HTTP_200_OK)
async def get_calendar_sync_status(
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Backend data source for the dashboard's Calendar Sync Status /
    Upcoming Meetings / Failed Syncs / Last Calendar Sync views (Module 4
    wires this into the actual dashboard UI)."""
    upcoming_query = (
        select(Prospect)
        .where(
            Prospect.tenant_id == tenant_id,
            Prospect.status == ProspectState.MEETING_BOOKED,
            Prospect.google_calendar_event_id.isnot(None),
        )
        .order_by(Prospect.last_status_change_at.desc())
        .limit(50)
    )
    upcoming = (await db.execute(upcoming_query)).scalars().all()

    failed_query = (
        select(CalendarSyncLog)
        .where(CalendarSyncLog.tenant_id == tenant_id, CalendarSyncLog.status == CalendarSyncStatus.FAILED)
        .order_by(CalendarSyncLog.created_at.desc())
        .limit(50)
    )
    failed_syncs = (await db.execute(failed_query)).scalars().all()

    last_sync_query = select(func.max(CalendarSyncLog.created_at)).where(CalendarSyncLog.tenant_id == tenant_id)
    last_sync_at = (await db.execute(last_sync_query)).scalar_one_or_none()

    return {
        "status": "success",
        "data": {
            "last_calendar_sync": last_sync_at.isoformat() if last_sync_at else None,
            "failed_sync_count": len(failed_syncs),
            "upcoming_meeting_count": len(upcoming),
            "upcoming_meetings": [
                {
                    "prospect_id": p.id,
                    "name": f"{p.first_name} {p.last_name}",
                    "google_calendar_event_id": p.google_calendar_event_id,
                    "booked_at": p.last_status_change_at.isoformat() if p.last_status_change_at else None,
                }
                for p in upcoming
            ],
            "failed_syncs": [
                {
                    "prospect_id": f.prospect_id,
                    "event_type": f.event_type,
                    "error_message": f.error_message,
                    "created_at": f.created_at.isoformat(),
                }
                for f in failed_syncs
            ],
        },
    }
