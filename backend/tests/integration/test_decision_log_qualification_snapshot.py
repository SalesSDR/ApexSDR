"""Sprint 6, item 4 (Historical Analytics): DecisionLog captures the
prospect's qualification_level/score AT THE TIME of each decision, and
priority-based analytics read that snapshot rather than joining to
Prospect's current (possibly since-changed) value."""
from sqlalchemy import select

from app.models.schemas import DecisionLog, DecisionType, Prospect, ProspectState, QualificationLevel, SequenceStep
from app.services.analytics.service import AnalyticsService
from app.services.decision.engine import DecisionEngine

ENGINE = DecisionEngine()


async def test_record_decision_snapshots_the_prospects_qualification_level(db_session):
    prospect = Prospect(
        tenant_id="snap-tenant", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-snap", status=ProspectState.IDLE,
        qualification_level=QualificationLevel.HOT, qualification_score=88.0,
    )
    db_session.add(prospect)
    await db_session.flush()

    decision = ENGINE.decide(prospect, sequence_steps=[
        SequenceStep(channel="LINKEDIN", step_number=1, title="LinkedIn", delay_minutes=60),
    ])
    await ENGINE.record_decision(db_session, prospect, decision)

    log = (await db_session.execute(
        select(DecisionLog).where(DecisionLog.prospect_id == prospect.id)
    )).scalar_one()
    assert log.qualification_level_at_decision == QualificationLevel.HOT
    assert log.qualification_score_at_decision == 88.0


async def test_snapshot_is_preserved_even_after_the_prospect_is_rescored(db_session):
    """The whole point of a snapshot: once logged, it must not silently
    change just because Prospect.qualification_level later does."""
    prospect = Prospect(
        tenant_id="snap-tenant-2", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-snap", status=ProspectState.IDLE,
        qualification_level=QualificationLevel.LOW, qualification_score=20.0,
    )
    db_session.add(prospect)
    await db_session.flush()

    decision = ENGINE.decide(prospect, sequence_steps=[
        SequenceStep(channel="LINKEDIN", step_number=1, title="LinkedIn", delay_minutes=60),
    ])
    await ENGINE.record_decision(db_session, prospect, decision)

    # Prospect gets rescored higher later - the already-logged row must not change.
    prospect.qualification_level = QualificationLevel.HOT
    prospect.qualification_score = 95.0
    await db_session.flush()

    log = (await db_session.execute(select(DecisionLog).where(DecisionLog.prospect_id == prospect.id))).scalar_one()
    assert log.qualification_level_at_decision == QualificationLevel.LOW
    assert log.qualification_score_at_decision == 20.0


def _decision_log(prospect, decision_type, level, score):
    return DecisionLog(
        tenant_id=prospect.tenant_id, prospect_id=prospect.id, decision_type=decision_type,
        reason="test", confidence=0.9, prospect_status_at_decision=prospect.status.value,
        qualification_level_at_decision=level, qualification_score_at_decision=score,
    )


async def test_messages_by_priority_uses_the_decision_log_snapshot_not_current_prospect_value(db_session):
    """A prospect logged as HOT at decision time, but since demoted to LOW
    on the Prospect row itself, must still count under HOT here."""
    prospect = Prospect(
        tenant_id="snap-tenant-3", first_name="Kay", last_name="Test",
        linkedin_url="https://linkedin.com/in/kay-snap", status=ProspectState.LI_REQ_SENT,
        qualification_level=QualificationLevel.LOW, qualification_score=10.0,  # current value: LOW
    )
    db_session.add(prospect)
    await db_session.flush()

    db_session.add(_decision_log(prospect, DecisionType.SEND_LINKEDIN, QualificationLevel.HOT, 90.0))
    await db_session.flush()

    data = await AnalyticsService(db_session, "snap-tenant-3").messages_by_priority()

    assert data["messages_sent_by_priority"]["HOT"] == 1
    assert data["messages_sent_by_priority"]["LOW"] == 0


async def test_conversion_by_priority_uses_the_prospects_latest_logged_level(db_session):
    prospect = Prospect(
        tenant_id="snap-tenant-4", first_name="Latest", last_name="Level",
        linkedin_url="https://linkedin.com/in/latest-level", status=ProspectState.MEETING_BOOKED,
        qualification_level=QualificationLevel.MEDIUM, qualification_score=45.0,
    )
    db_session.add(prospect)
    await db_session.flush()

    # Earlier decision logged as MEDIUM, later (more recent) one as HOT -
    # the latest one should win for grouping purposes.
    db_session.add(_decision_log(prospect, DecisionType.WAIT, QualificationLevel.MEDIUM, 45.0))
    await db_session.flush()
    db_session.add(_decision_log(prospect, DecisionType.SEND_LINKEDIN, QualificationLevel.HOT, 85.0))
    await db_session.flush()

    data = await AnalyticsService(db_session, "snap-tenant-4").conversion_by_priority()

    assert data["conversion_by_priority"]["HOT"]["total"] == 1
    assert data["conversion_by_priority"]["HOT"]["meetings_booked"] == 1
    assert "MEDIUM" not in data["conversion_by_priority"]
