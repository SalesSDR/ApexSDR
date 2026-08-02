import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.database import get_db
from app.models.schemas import LinkedInAccount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


@router.get("/queue-status", status_code=status.HTTP_200_OK)
async def get_linkedin_queue_status(
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Backend data source for the dashboard's LinkedIn Queue Status view:
    per-account daily send count/limit and pause state. Read-only - doesn't
    mutate account state, just reports whether a stored pause has already
    lapsed (the queue service itself lifts it lazily on the next real send)."""
    query = select(LinkedInAccount).where(LinkedInAccount.tenant_id == tenant_id)
    accounts = (await db.execute(query)).scalars().all()

    now_utc = datetime.now(UTC)
    return {
        "status": "success",
        "data": {
            "accounts": [
                {
                    "account_id": a.account_id,
                    "daily_send_count": a.daily_send_count,
                    "daily_limit": a.daily_limit,
                    "remaining_today": max(0, a.daily_limit - a.daily_send_count),
                    "is_paused": bool(a.is_paused and (not a.paused_until or a.paused_until > now_utc)),
                    "paused_reason": a.paused_reason,
                    "paused_until": a.paused_until.isoformat() if a.paused_until else None,
                }
                for a in accounts
            ]
        },
    }
