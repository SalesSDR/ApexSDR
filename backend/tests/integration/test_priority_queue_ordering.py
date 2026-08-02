"""Sprint 5, item 2 (Priority Queue): the Sequence Engine's supervisor must
process due prospects HOT -> HIGH -> MEDIUM -> LOW -> not-yet-scored, and
oldest-created-first within the same tier - never insertion/arbitrary
order. Seeds prospects in an order that would produce a DIFFERENT result if
priority weren't actually driving the query, which is the strongest proof
the ordering is real."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.compliance.policy as compliance_policy
from app.models.schemas import Prospect, ProspectState, QualificationLevel, SequenceRule, SequenceStep
from app.services.decision.engine import DecisionEngine
from app.workers.tasks import autonomous_pipeline_supervisor_task


@pytest.fixture(autouse=True)
def _business_hours_always_open(monkeypatch):
    monkeypatch.setattr(compliance_policy, "is_within_business_hours", lambda *a, **kw: True)


class _FakeRedis:
    def __init__(self):
        self.enqueued = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.enqueued.append(args[0])  # just the prospect_id, for order assertions


def _ctx(db_session):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return {"sessionmaker": session_factory, "redis": _FakeRedis(), "decision_engine": DecisionEngine()}


async def _seed_sequence(db_session, tenant_id: str):
    rule = SequenceRule(id=str(uuid.uuid4()), tenant_id=tenant_id)
    db_session.add(rule)
    await db_session.flush()
    db_session.add(SequenceStep(
        id=str(uuid.uuid4()), sequence_rule_id=rule.id, channel="LINKEDIN",
        step_number=1, title="LinkedIn", delay_minutes=60,
    ))
    await db_session.flush()


def _prospect(n, level, created_at, tenant_id="priority-tenant"):
    return Prospect(
        tenant_id=tenant_id, first_name=f"P{n}", last_name="Test",
        linkedin_url=f"https://linkedin.com/in/priority-{n}",
        status=ProspectState.IDLE,
        qualification_level=level,
        qualification_score={QualificationLevel.HOT: 90.0, QualificationLevel.HIGH: 65.0,
                              QualificationLevel.MEDIUM: 45.0, QualificationLevel.LOW: 10.0, None: None}[level],
        next_action_at=datetime.now(UTC) - timedelta(minutes=1),
        created_at=created_at,
    )


async def test_hot_is_processed_before_high_before_medium(db_session):
    """LOW is deliberately excluded here: a LOW-tier prospect's would-be
    send gets overridden to HUMAN_REVIEW by the qualification policy (item
    3) rather than enqueued at all - see test_decision_engine.py's
    coverage of that. This test isolates pure priority ordering among tiers
    that all still result in a real send."""
    await _seed_sequence(db_session, "priority-tenant")
    now = datetime.now(UTC)

    # Deliberately seeded worst-priority-first, so only real priority-aware
    # ordering (not insertion order) could produce HOT-first output.
    medium = _prospect(1, QualificationLevel.MEDIUM, now)
    high = _prospect(2, QualificationLevel.HIGH, now)
    hot = _prospect(3, QualificationLevel.HOT, now)
    db_session.add_all([medium, high, hot])
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    assert ctx["redis"].enqueued == [hot.id, high.id, medium.id]


async def test_oldest_first_within_the_same_priority_tier(db_session):
    await _seed_sequence(db_session, "priority-tenant")
    now = datetime.now(UTC)

    # All HOT, but seeded newest-first - oldest-first must still win within
    # the tier.
    newest = _prospect(1, QualificationLevel.HOT, now)
    oldest = _prospect(2, QualificationLevel.HOT, now - timedelta(days=2))
    middle = _prospect(3, QualificationLevel.HOT, now - timedelta(days=1))
    db_session.add_all([newest, oldest, middle])
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    assert ctx["redis"].enqueued == [oldest.id, middle.id, newest.id]


async def test_not_yet_scored_prospects_are_processed_last(db_session):
    await _seed_sequence(db_session, "priority-tenant")
    now = datetime.now(UTC)

    unscored = _prospect(1, None, now - timedelta(days=5))  # oldest of all, but unscored
    medium = _prospect(2, QualificationLevel.MEDIUM, now)
    db_session.add_all([unscored, medium])
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    assert ctx["redis"].enqueued == [medium.id, unscored.id]


async def test_low_priority_is_escalated_to_human_review_instead_of_sent(db_session):
    """Sprint 5, item 3: a LOW-tier prospect's would-be send is overridden
    to HUMAN_REVIEW by the qualification policy - nothing is enqueued for
    it, and it's moved to ERROR_NEEDS_HUMAN so ops can see it."""
    await _seed_sequence(db_session, "priority-tenant")
    low = _prospect(1, QualificationLevel.LOW, datetime.now(UTC))
    db_session.add(low)
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    assert ctx["redis"].enqueued == []
    await db_session.refresh(low)
    assert low.status == ProspectState.ERROR_NEEDS_HUMAN
