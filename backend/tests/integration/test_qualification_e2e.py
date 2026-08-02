import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.ai as ai_module
import app.workers.tasks as tasks
from app.models.schemas import Prospect, ProspectState, SequenceRule, SequenceStep
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.decision.engine import SEQUENCE_STEP_TASK_NAME, DecisionEngine
from app.services.linkedin.mock import MockLinkedInAdapter
from app.services.linkedin.service import LinkedInQueueService
from app.workers.tasks import execute_sequence_step_task, run_waterfall_enrichment_task


class _FakeRedis:
    def __init__(self):
        self.enqueued = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.enqueued.append((name, args, kwargs))


async def test_new_prospect_reaches_li_req_sent_through_the_full_pipeline(db_session, monkeypatch):
    """End-to-end: NEW -> ENRICHING -> QUALIFIED -> IDLE (qualification task,
    Module 3's new phase) -> LI_REQ_SENT (existing outbound sequence task),
    driven by directly chaining the two real ARQ task functions the way the
    live worker would, with only the external network calls (enrichment
    providers, Unipile, jitter sleep) replaced by fakes."""
    monkeypatch.setattr(tasks, "enrich_email_waterfall", lambda **kw: _ret("ada@example.com"))
    monkeypatch.setattr(tasks, "enrich_phone_waterfall", lambda **kw: _ret(None))
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    monkeypatch.setattr(ai_module, "generate_outreach_message", lambda *a, **kw: _ret("Looking forward to connecting!"))

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Ada",
        last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-e2e",
        status=ProspectState.NEW,
    )
    db_session.add(prospect)
    # Sequence Engine: the qualification hand-off enqueues the generic step
    # executor, which reads the tenant's SequenceStep order from the DB.
    rule = SequenceRule(id=str(uuid.uuid4()), tenant_id="test-tenant")
    db_session.add(rule)
    await db_session.flush()
    db_session.add(SequenceStep(
        id=str(uuid.uuid4()), sequence_rule_id=rule.id, channel="LINKEDIN",
        step_number=1, title="LinkedIn Connection Request", delay_minutes=60,
    ))
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    crm_service = CRMService(MockHubSpotAdapter())
    fake_redis = _FakeRedis()

    # Hop 1: qualification phase (the new Module 3 functionality).
    await run_waterfall_enrichment_task(
        {"sessionmaker": session_factory, "crm_service": crm_service, "redis": fake_redis, "decision_engine": DecisionEngine()},
        prospect.id,
    )
    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.IDLE

    name, args, kwargs = fake_redis.enqueued[0]
    assert name == SEQUENCE_STEP_TASK_NAME

    # Hop 2: exactly what the enqueued job would invoke - proves the handoff
    # between the two tasks (and their statuses) is wired correctly end-to-end.
    await execute_sequence_step_task(
        {
            "sessionmaker": session_factory,
            "linkedin_queue": LinkedInQueueService(MockLinkedInAdapter()),
            "crm_service": crm_service,
        },
        *args,
        **kwargs,
    )
    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.LI_REQ_SENT
    assert prospect.next_action_at is not None


async def test_new_prospect_with_no_contact_info_never_reaches_outreach(db_session, monkeypatch):
    monkeypatch.setattr(tasks, "enrich_email_waterfall", lambda **kw: _ret(None))
    monkeypatch.setattr(tasks, "enrich_phone_waterfall", lambda **kw: _ret(None))

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="No",
        last_name="Contact",
        linkedin_url="https://linkedin.com/in/no-contact-e2e",
        status=ProspectState.NEW,
    )
    db_session.add(prospect)
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    fake_redis = _FakeRedis()

    await run_waterfall_enrichment_task(
        {
            "sessionmaker": session_factory, "crm_service": CRMService(MockHubSpotAdapter()),
            "redis": fake_redis, "decision_engine": DecisionEngine(),
        },
        prospect.id,
    )

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.DISQUALIFIED
    assert fake_redis.enqueued == []  # outbound sequence never starts


async def _ret(value):
    return value
