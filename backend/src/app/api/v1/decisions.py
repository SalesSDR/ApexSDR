import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.database import get_db
from app.models.schemas import DecisionLog, Prospect
from app.services.decision.engine import DecisionEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decisions", tags=["decisions"])


async def _get_owned_prospect(db: AsyncSession, prospect_id: str, tenant_id: str) -> Prospect:
    query = select(Prospect).where(Prospect.id == prospect_id, Prospect.tenant_id == tenant_id)
    prospect = (await db.execute(query)).scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect


@router.get("/{prospect_id}", status_code=status.HTTP_200_OK)
async def get_decision_history(
    prospect_id: str,
    limit: int = Query(50, ge=1, le=200),
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
):
    """The audit trail: every decision the DecisionEngine has actually made
    and logged for this prospect, most recent first."""
    await _get_owned_prospect(db, prospect_id, tenant_id)

    query = (
        select(DecisionLog)
        .where(DecisionLog.prospect_id == prospect_id, DecisionLog.tenant_id == tenant_id)
        # sequence_number (a real Postgres IDENTITY column) rather than
        # created_at: two decisions logged in the same transaction can share
        # an identical created_at (Postgres now() is transaction-start
        # time), which would make "most recent first" ambiguous.
        .order_by(DecisionLog.sequence_number.desc())
        .limit(limit)
    )
    logs = (await db.execute(query)).scalars().all()

    return {
        "status": "success",
        "data": [
            {
                "id": log.id,
                "decision_type": log.decision_type.value,
                "reason": log.reason,
                "confidence": log.confidence,
                "prospect_status_at_decision": log.prospect_status_at_decision,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


@router.get("/{prospect_id}/preview", status_code=status.HTTP_200_OK)
async def preview_next_decision(
    prospect_id: str,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Read-only: what the DecisionEngine would decide for this prospect
    right now, without logging it - for debugging/admin inspection, not a
    substitute for the real decision the pipeline makes when the prospect
    is actually due."""
    prospect = await _get_owned_prospect(db, prospect_id, tenant_id)

    engine = DecisionEngine()
    decision = await engine.decide_for_prospect(db, prospect)

    return {
        "status": "success",
        "data": {
            "decision_type": decision.decision_type.value,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "task_to_enqueue": decision.task_to_enqueue,
        },
    }
