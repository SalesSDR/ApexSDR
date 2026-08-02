"""End-to-end + mock-mode coverage: drives a prospect through the real
pipeline (API creation -> enrichment -> supervisor-driven outreach), with
every external integration running in Mock mode, and confirms the
DecisionEngine's own audit trail (queryable via the /decisions API) matches
what actually happened - the guarantee that decision logging isn't a
parallel, potentially-inaccurate narrative of the pipeline."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.ai as ai_module
import app.services.compliance.policy as compliance_policy
import app.workers.tasks as tasks
from app.models.schemas import DecisionType, Prospect, ProspectState, SequenceRule, SequenceStep
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.decision.engine import SEQUENCE_STEP_TASK_NAME, DecisionEngine
from app.services.linkedin.mock import MockLinkedInAdapter
from app.services.linkedin.service import LinkedInQueueService
from app.workers.tasks import autonomous_pipeline_supervisor_task, run_waterfall_enrichment_task
from tests.conftest import bearer_for


@pytest.fixture(autouse=True)
def _business_hours_always_open(monkeypatch):
    """This test exercises the qualification->sequencing hand-off, not
    compliance - see the same fixture in test_supervisor_task.py for why."""
    monkeypatch.setattr(compliance_policy, "is_within_business_hours", lambda *a, **kw: True)


class _FakeRedis:
    """Records enqueue_job calls instead of dispatching to a live worker -
    lets the test assert exactly what the pipeline decided to do next
    without needing a running ARQ worker process."""
    def __init__(self):
        self.enqueued = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.enqueued.append((name, args, kwargs))


async def _ret(value):
    return value


async def test_mock_mode_pipeline_matches_its_own_decision_log(client, db_session, monkeypatch):
    monkeypatch.setattr(tasks, "enrich_email_waterfall", lambda **kw: _ret("mockmode@example.com"))
    monkeypatch.setattr(tasks, "enrich_phone_waterfall", lambda **kw: _ret(None))
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    monkeypatch.setattr(ai_module, "generate_outreach_message", lambda *a, **kw: _ret("Looking forward to connecting!"))

    create_resp = await client.post(
        "/api/v1/prospects",
        json={
            "first_name": "Mock",
            "last_name": "Mode",
            "email": "mockmode@example.com",
            "linkedin_url": "https://linkedin.com/in/mock-mode-e2e",
        },
        headers=bearer_for("org_mock_mode"),
    )
    assert create_resp.status_code == 201
    prospect_id = create_resp.json()["data"]["id"]

    # Sequence Engine: decide_for_prospect() reads the tenant's SequenceStep
    # order from the DB - without seeding one, the supervisor would just
    # see "no further sequence step configured" and enqueue nothing.
    rule = SequenceRule(id=str(uuid.uuid4()), tenant_id="org_mock_mode")
    db_session.add(rule)
    await db_session.flush()
    db_session.add(SequenceStep(
        id=str(uuid.uuid4()), sequence_rule_id=rule.id, channel="LINKEDIN",
        step_number=1, title="LinkedIn Connection Request", delay_minutes=60,
    ))
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    crm_service = CRMService(MockHubSpotAdapter())  # explicitly Mock, never touches real HubSpot
    decision_engine = DecisionEngine()

    # Step 1: qualification (Module 3 task, now decision-engine-driven).
    await run_waterfall_enrichment_task(
        {
            "sessionmaker": session_factory, "crm_service": crm_service,
            "redis": _FakeRedis(), "decision_engine": decision_engine,
        },
        prospect_id,
    )

    async with session_factory() as db:
        prospect = await db.get(Prospect, prospect_id)
        assert prospect.status == ProspectState.IDLE
        prospect.next_action_at = datetime.now(UTC) - timedelta(minutes=1)  # make it due
        await db.commit()

    # Step 2: the autonomous supervisor picks it up and asks the engine what
    # to do - entirely Mock-mode, no live worker process involved.
    supervisor_ctx = {"sessionmaker": session_factory, "redis": _FakeRedis(), "decision_engine": decision_engine}
    await autonomous_pipeline_supervisor_task(supervisor_ctx)

    assert supervisor_ctx["redis"].enqueued == [
        (SEQUENCE_STEP_TASK_NAME, (prospect_id,), {})
    ]

    # Step 3: actually run what got enqueued, with the Mock LinkedIn adapter.
    await tasks.execute_sequence_step_task(
        {
            "sessionmaker": session_factory,
            "linkedin_queue": LinkedInQueueService(MockLinkedInAdapter()),
            "crm_service": crm_service,
        },
        prospect_id,
    )

    async with session_factory() as db:
        prospect = await db.get(Prospect, prospect_id)
        assert prospect.status == ProspectState.LI_REQ_SENT

    # Step 4: the /decisions API's audit trail must reflect the same
    # sequence of decisions that actually drove the pipeline above.
    history_resp = await client.get(
        f"/api/v1/decisions/{prospect_id}", headers=bearer_for("org_mock_mode")
    )
    assert history_resp.status_code == 200
    decisions = [d["decision_type"] for d in history_resp.json()["data"]]
    # Most-recent-first: SEND_LINKEDIN (supervisor) logged after
    # MARK_QUALIFIED (enrichment task).
    assert decisions == [DecisionType.SEND_LINKEDIN.value, DecisionType.MARK_QUALIFIED.value]
