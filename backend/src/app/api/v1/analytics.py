from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.database import get_arq_pool, get_db
from app.models.schemas import ActivityTimeline, Prospect
from app.services.analytics.service import AnalyticsService

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


# --- Module 5: dashboard analytics ---
# Every endpoint below is a thin wrapper around AnalyticsService - routes
# never build aggregation queries themselves (see AnalyticsService's
# docstring for why).

@router.get("/metrics/funnel", status_code=status.HTTP_200_OK)
async def get_pipeline_funnel(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).pipeline_funnel()
    return {"status": "success", "data": data}


@router.get("/metrics/prospects-by-state", status_code=status.HTTP_200_OK)
async def get_prospects_by_state(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).prospects_by_state()
    return {"status": "success", "data": data}


@router.get("/metrics/outreach", status_code=status.HTTP_200_OK)
async def get_outreach_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).outreach_metrics()
    return {"status": "success", "data": data}


@router.get("/metrics/linkedin", status_code=status.HTTP_200_OK)
async def get_linkedin_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).linkedin_metrics()
    return {"status": "success", "data": data}


@router.get("/metrics/email", status_code=status.HTTP_200_OK)
async def get_email_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).email_metrics()
    return {"status": "success", "data": data}


@router.get("/metrics/calls", status_code=status.HTTP_200_OK)
async def get_call_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).call_metrics()
    return {"status": "success", "data": data}


@router.get("/metrics/crm-sync", status_code=status.HTTP_200_OK)
async def get_crm_sync_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).crm_sync_metrics()
    return {"status": "success", "data": data}


@router.get("/metrics/calendar", status_code=status.HTTP_200_OK)
async def get_calendar_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).calendar_metrics()
    return {"status": "success", "data": data}


@router.get("/metrics/queue", status_code=status.HTTP_200_OK)
async def get_queue_metrics(
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    data = await AnalyticsService(db, tenant_id, arq_pool=arq_pool).queue_metrics()
    return {"status": "success", "data": data}


@router.get("/metrics/retry", status_code=status.HTTP_200_OK)
async def get_retry_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).retry_metrics()
    return {"status": "success", "data": data}


@router.get("/metrics/activity", status_code=status.HTTP_200_OK)
async def get_daily_weekly_activity(
    period: str = Query("daily", pattern="^(daily|weekly)$"),
    days: int = Query(30, ge=1, le=365),
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await AnalyticsService(db, tenant_id).daily_weekly_activity(period=period, days=days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "data": data}


@router.get("/metrics/failed-jobs", status_code=status.HTTP_200_OK)
async def get_failed_jobs(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).failed_jobs()
    return {"status": "success", "data": data}


@router.get("/metrics/conversion", status_code=status.HTTP_200_OK)
async def get_conversion_rates(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).conversion_rates()
    return {"status": "success", "data": data}


@router.get("/metrics/response-times", status_code=status.HTTP_200_OK)
async def get_response_times(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    data = await AnalyticsService(db, tenant_id).response_times()
    return {"status": "success", "data": data}


@router.get("/metrics/signals", status_code=status.HTTP_200_OK)
async def get_signals_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Module 8: Returns active vs expired signal counts and aggregations."""
    metrics = await AnalyticsService(db, tenant_id).signal_metrics()
    return {"status": "success", "data": metrics}

@router.get("/metrics/compliance")
async def get_compliance_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Module 9: Returns compliance engine metrics."""
    metrics = await AnalyticsService.compliance_metrics(db, tenant_id)
    return {"status": "success", "data": metrics}

@router.get("/metrics/voice")
async def get_voice_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Module 10: Returns voice engine metrics."""
    metrics = await AnalyticsService.voice_metrics(db, tenant_id)
    return {"status": "success", "data": metrics}


@router.get("/metrics/qualification")
async def get_qualification_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Module 13: qualification/priority distribution, average score, and
    top ICP matches."""
    metrics = await AnalyticsService(db, tenant_id).qualification_metrics()
    return {"status": "success", "data": metrics}


@router.get("/metrics/messages-by-priority")
async def get_messages_by_priority(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Sprint 5, item 4: outbound send-decisions grouped by priority tier."""
    metrics = await AnalyticsService(db, tenant_id).messages_by_priority()
    return {"status": "success", "data": metrics}


@router.get("/metrics/conversion-by-priority")
async def get_conversion_by_priority(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Sprint 5, item 4: meeting/reply/won rates per priority tier."""
    metrics = await AnalyticsService(db, tenant_id).conversion_by_priority()
    return {"status": "success", "data": metrics}


@router.get("/metrics/qualification-accuracy")
async def get_qualification_accuracy(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Sprint 5, item 4: does the qualification tier ordering actually
    match real pipeline outcomes."""
    metrics = await AnalyticsService(db, tenant_id).qualification_accuracy()
    return {"status": "success", "data": metrics}


@router.get("/metrics/channel-performance")
async def get_channel_performance(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Sprint 5, item 4: reply/connect rate per outbound channel."""
    metrics = await AnalyticsService(db, tenant_id).channel_performance()
    return {"status": "success", "data": metrics}


@router.get("/metrics/revenue")
async def get_revenue_metrics(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Sprint 5, item 5: estimated_pipeline_value, meeting_value, won_value,
    and lost_value."""
    metrics = await AnalyticsService(db, tenant_id).revenue_metrics()
    return {"status": "success", "data": metrics}
