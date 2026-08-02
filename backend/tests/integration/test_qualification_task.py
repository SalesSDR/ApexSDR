from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.workers.tasks as tasks
from app.models.schemas import Prospect, ProspectState
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.decision.engine import SEQUENCE_STEP_TASK_NAME, DecisionEngine
from app.workers.tasks import run_waterfall_enrichment_task


class _FakeRedis:
    def __init__(self):
        self.enqueued = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.enqueued.append((name, args, kwargs))


def _ctx(db_session):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return {
        "sessionmaker": session_factory,
        "crm_service": CRMService(MockHubSpotAdapter()),
        "redis": _FakeRedis(),
        "decision_engine": DecisionEngine(),
    }


async def test_qualifies_prospect_and_enqueues_outbound_sequence(db_session, monkeypatch):
    monkeypatch.setattr(tasks, "enrich_email_waterfall", lambda **kw: _async_return("found@example.com"))
    monkeypatch.setattr(tasks, "enrich_phone_waterfall", lambda **kw: _async_return(None))

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Ada",
        last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-qual",
        status=ProspectState.NEW,
    )
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session)
    await run_waterfall_enrichment_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.IDLE
    assert prospect.email == "found@example.com"
    assert prospect.next_action_at is not None

    assert len(ctx["redis"].enqueued) == 1
    name, args, kwargs = ctx["redis"].enqueued[0]
    assert name == SEQUENCE_STEP_TASK_NAME
    assert args == (prospect.id,)
    assert kwargs == {}


async def test_disqualifies_prospect_with_no_email_or_phone_found(db_session, monkeypatch):
    monkeypatch.setattr(tasks, "enrich_email_waterfall", lambda **kw: _async_return(None))
    monkeypatch.setattr(tasks, "enrich_phone_waterfall", lambda **kw: _async_return(None))

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Grace",
        last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-qual",
        status=ProspectState.NEW,
    )
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session)
    await run_waterfall_enrichment_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.DISQUALIFIED
    # A disqualified prospect never starts outreach.
    assert ctx["redis"].enqueued == []


async def test_skips_prospects_already_past_qualification(db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(tasks, "enrich_email_waterfall", lambda **kw: calls.append(1) or _async_return(None))

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Katherine",
        last_name="Johnson",
        linkedin_url="https://linkedin.com/in/katherine-qual",
        status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session)
    await run_waterfall_enrichment_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.IDLE  # untouched
    assert calls == []  # enrichment never even attempted
    assert ctx["redis"].enqueued == []


async def _async_return(value):
    return value
