"""Sprint 6, item 1 (CRM Revenue Sync): CLOSED_WON/LOST deal-stage sync to
HubSpot, recorded to CrmSyncLog, retried through the centralized retry
engine on failure."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.schemas import CrmSyncLog, CrmSyncStatus, Prospect, ProspectState
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import DEAL_STAGE_BY_STATE, CRMService
from app.workers.tasks import sync_crm_deal_stage_task


class _RaisingAdapter(MockHubSpotAdapter):
    async def upsert_deal(self, contact_id, deal_id, deal_name, stage):
        raise RuntimeError("simulated HubSpot outage")


class _FakeRedis:
    def __init__(self):
        self.enqueued = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.enqueued.append((name, args, kwargs))


def _ctx(db_session, crm_service, redis=None):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return {"sessionmaker": session_factory, "crm_service": crm_service, "redis": redis or _FakeRedis()}


def test_deal_stage_mapping_covers_won_and_lost():
    assert DEAL_STAGE_BY_STATE[ProspectState.CLOSED_WON] == "closedwon"
    assert DEAL_STAGE_BY_STATE[ProspectState.LOST] == "closedlost"


async def test_closed_won_prospect_syncs_deal_stage_and_logs_success(db_session):
    prospect = Prospect(
        tenant_id="crm-rev-tenant", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-crm-rev", status=ProspectState.CLOSED_WON,
        company_name="Acme Inc",
    )
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session, CRMService(MockHubSpotAdapter()))
    await sync_crm_deal_stage_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.hubspot_deal_id is not None
    assert prospect.retry_count == 0

    logs = (await db_session.execute(
        select(CrmSyncLog).where(CrmSyncLog.prospect_id == prospect.id, CrmSyncLog.sync_type == "DEAL")
    )).scalars().all()
    assert any(log.status == CrmSyncStatus.SUCCESS for log in logs)


async def test_lost_prospect_syncs_deal_stage(db_session):
    prospect = Prospect(
        tenant_id="crm-rev-tenant", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-crm-rev", status=ProspectState.LOST,
        company_name="Acme Inc",
    )
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session, CRMService(MockHubSpotAdapter()))
    await sync_crm_deal_stage_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.hubspot_deal_id is not None


async def test_ignores_prospects_not_in_a_closed_outcome_state(db_session):
    prospect = Prospect(
        tenant_id="crm-rev-tenant", first_name="Not", last_name="Closed",
        linkedin_url="https://linkedin.com/in/not-closed", status=ProspectState.MEETING_BOOKED,
    )
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session, CRMService(MockHubSpotAdapter()))
    await sync_crm_deal_stage_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.hubspot_deal_id is None


async def test_failure_is_logged_and_retried_via_the_retry_engine(db_session):
    prospect = Prospect(
        tenant_id="crm-rev-tenant", first_name="Failing", last_name="Sync",
        linkedin_url="https://linkedin.com/in/failing-sync", status=ProspectState.CLOSED_WON,
        company_name="Acme Inc", retry_count=0,
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_redis = _FakeRedis()
    ctx = _ctx(db_session, CRMService(_RaisingAdapter()), redis=fake_redis)
    await sync_crm_deal_stage_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.retry_count == 1
    assert len(fake_redis.enqueued) == 1
    name, args, kwargs = fake_redis.enqueued[0]
    assert name == "sync_crm_deal_stage_task"
    assert args == (prospect.id,)
    assert "_defer_by" in kwargs

    logs = (await db_session.execute(
        select(CrmSyncLog).where(CrmSyncLog.prospect_id == prospect.id, CrmSyncLog.sync_type == "DEAL")
    )).scalars().all()
    assert any(log.status == CrmSyncStatus.FAILURE for log in logs)


async def test_gives_up_after_retries_exhausted_without_re_enqueueing(db_session):
    prospect = Prospect(
        tenant_id="crm-rev-tenant", first_name="Exhausted", last_name="Retries",
        linkedin_url="https://linkedin.com/in/exhausted-retries", status=ProspectState.CLOSED_WON,
        company_name="Acme Inc", retry_count=5,
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_redis = _FakeRedis()
    ctx = _ctx(db_session, CRMService(_RaisingAdapter()), redis=fake_redis)
    await sync_crm_deal_stage_task(ctx, prospect.id)

    assert fake_redis.enqueued == []
