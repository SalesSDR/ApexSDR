from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.api.v1.auth import verify_tenant
from app.models.schemas import ActivityTimeline, Prospect

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/intents", status_code=status.HTTP_200_OK)
async def get_intent_logs(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """
    Returns AI intent analysis from prospect replies.
    For demonstration, queries ActivityTimeline for REPLY events.
    """
    query = (
        select(ActivityTimeline, Prospect)
        .join(Prospect, ActivityTimeline.prospect_id == Prospect.id)
        .where(
            ActivityTimeline.tenant_id == tenant_id,
            ActivityTimeline.event_type == "REPLY"
        )
        .order_by(ActivityTimeline.created_at.desc())
        .limit(100)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for timeline, prospect in rows:
        # Assuming the description holds the intent or message text
        response.append({
            "prospect_name": f"{prospect.first_name} {prospect.last_name}",
            "prospect_company": prospect.company_name or "",
            "intent": "POSITIVE" if "POSITIVE" in timeline.description else "NEGATIVE" if "NEGATIVE" in timeline.description else "NEUTRAL",
            "message": timeline.description,
            "timestamp": timeline.created_at.isoformat()
        })
    return {"status": "success", "data": response}


@router.get("/calls", status_code=status.HTTP_200_OK)
async def get_call_logs(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """
    Returns call logs and outcomes.
    """
    query = (
        select(ActivityTimeline, Prospect)
        .join(Prospect, ActivityTimeline.prospect_id == Prospect.id)
        .where(
            ActivityTimeline.tenant_id == tenant_id,
            ActivityTimeline.channel == "CALL"
        )
        .order_by(ActivityTimeline.created_at.desc())
        .limit(100)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for timeline, prospect in rows:
        response.append({
            "prospect_name": f"{prospect.first_name} {prospect.last_name}",
            "phone_number": prospect.phone_number or "",
            "outcome": timeline.event_type,
            "details": timeline.description,
            "timestamp": timeline.created_at.isoformat()
        })
    return {"status": "success", "data": response}
