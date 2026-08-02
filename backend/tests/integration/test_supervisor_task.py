"""Queue-integration coverage for autonomous_pipeline_supervisor_task: the
main autonomous heartbeat, now a pure executor of DecisionEngine decisions
rather than deciding anything itself. No test existed for this task before
Module 6 - this is new, load-bearing coverage, not just a Module 6 add-on."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.compliance.policy as compliance_policy
from app.models.schemas import DecisionLog, Prospect, ProspectState, SequenceRule, SequenceStep
from app.services.decision.engine import SEQUENCE_STEP_TASK_NAME, DecisionEngine
from app.workers.tasks import autonomous_pipeline_supervisor_task


@pytest.fixture(autouse=True)
def _business_hours_always_open(monkeypatch):
    """This file tests sequencing/decision behavior, not compliance - real
    business-hours enforcement (Sprint 2, item 4) would otherwise make
    these tests pass or fail depending on the wall-clock time they happen
    to run at. Business-hours enforcement itself is covered separately in
    tests/unit/test_compliance_timezone.py."""
    monkeypatch.setattr(compliance_policy, "is_within_business_hours", lambda *a, **kw: True)


async def _seed_sequence(db_session, tenant_id: str):
    rule = SequenceRule(id=str(uuid.uuid4()), tenant_id=tenant_id)
    db_session.add(rule)
    await db_session.flush()
    for step_number, channel in enumerate(
        ["LINKEDIN", "LINKEDIN_FOLLOWUP", "EMAIL_1", "EMAIL_2", "CALL", "VOICEMAIL", "BREAKUP_EMAIL"], start=1
    ):
        db_session.add(SequenceStep(
            id=str(uuid.uuid4()), sequence_rule_id=rule.id, channel=channel,
            step_number=step_number, title=channel, delay_minutes=60,
        ))
    await db_session.flush()


class _FakeRedis:
    def __init__(self):
        self.enqueued = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.enqueued.append((name, args, kwargs))


def _ctx(db_session):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return {"sessionmaker": session_factory, "redis": _FakeRedis(), "decision_engine": DecisionEngine()}


def _due_prospect(n, status, **overrides):
    defaults = dict(
        tenant_id="sup-tenant",
        first_name=f"Sup{n}",
        last_name="Test",
        linkedin_url=f"https://linkedin.com/in/sup{n}",
        status=status,
        next_action_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    defaults.update(overrides)
    return Prospect(**defaults)


async def test_supervisor_enqueues_start_outbound_sequence_with_tenant_id(db_session):
    await _seed_sequence(db_session, "sup-tenant")
    prospect = _due_prospect(1, ProspectState.IDLE)
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    # Sequence Engine: the supervisor now always enqueues the generic step
    # executor - which channel it actually runs comes from SequenceStep
    # order, not from the task name enqueued here.
    assert ctx["redis"].enqueued == [(SEQUENCE_STEP_TASK_NAME, (prospect.id,), {})]


async def test_supervisor_enqueues_plain_task_for_non_outbound_states(db_session):
    await _seed_sequence(db_session, "sup-tenant")
    prospect = _due_prospect(2, ProspectState.EMAIL_SENT, sequence_step_index=4)  # -> CALL
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    assert ctx["redis"].enqueued == [(SEQUENCE_STEP_TASK_NAME, (prospect.id,), {})]


async def test_supervisor_does_not_enqueue_for_a_wait_decision(db_session):
    # LI_ACCEPTED_NO_MSG less than 24h ago -> WAIT, nothing enqueued.
    prospect = _due_prospect(
        3, ProspectState.LI_ACCEPTED_NO_MSG,
        last_status_change_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    assert ctx["redis"].enqueued == []


async def test_supervisor_clears_next_action_at_for_every_due_prospect(db_session):
    prospect = _due_prospect(4, ProspectState.COMPLETED_DECLINED)  # terminal - END_SEQUENCE
    db_session.add(prospect)
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    await db_session.refresh(prospect)
    assert prospect.next_action_at is None
    assert ctx["redis"].enqueued == []  # terminal state, nothing to do


async def test_supervisor_logs_a_decision_for_every_due_prospect(db_session):
    prospects = [
        _due_prospect(5, ProspectState.IDLE),
        _due_prospect(6, ProspectState.EMAIL_SENT),
        _due_prospect(7, ProspectState.CALL_NO_ANSWER_1),
    ]
    db_session.add_all(prospects)
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    logs = (await db_session.execute(select(DecisionLog).where(DecisionLog.tenant_id == "sup-tenant"))).scalars().all()
    logged_prospect_ids = {log.prospect_id for log in logs}
    assert logged_prospect_ids == {p.id for p in prospects}


async def test_supervisor_ignores_prospects_not_yet_due(db_session):
    not_due = Prospect(
        tenant_id="sup-tenant", first_name="NotDue", last_name="Yet",
        linkedin_url="https://linkedin.com/in/not-due", status=ProspectState.IDLE,
        next_action_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(not_due)
    await db_session.flush()

    ctx = _ctx(db_session)
    await autonomous_pipeline_supervisor_task(ctx)

    assert ctx["redis"].enqueued == []
