"""Sprint 5, item 4: messages sent by priority, conversion by priority,
qualification accuracy, and channel performance."""
from app.models.schemas import DecisionLog, DecisionType, Prospect, ProspectState, QualificationLevel
from app.services.analytics.service import AnalyticsService

TENANT = "priority-analytics-tenant"


def _prospect(n, status, level=None, score=None, **overrides):
    defaults = dict(
        tenant_id=TENANT, first_name=f"P{n}", last_name="Test",
        linkedin_url=f"https://linkedin.com/in/pa{n}", status=status,
        qualification_level=level, qualification_score=score,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


def _decision_log(prospect, decision_type, level=None, score=None):
    """Sprint 6, item 4: priority-based analytics now group by each
    DecisionLog row's own qualification_level_at_decision/score snapshot,
    not Prospect's current value - defaults to the prospect's current
    level/score for tests that don't care about snapshot-vs-current
    divergence specifically (see test_decision_log_qualification_snapshot.py
    for tests that do)."""
    return DecisionLog(
        tenant_id=TENANT, prospect_id=prospect.id, decision_type=decision_type,
        reason="test", confidence=0.9, prospect_status_at_decision=prospect.status.value,
        qualification_level_at_decision=level if level is not None else prospect.qualification_level,
        qualification_score_at_decision=score if score is not None else prospect.qualification_score,
    )


async def test_messages_by_priority_counts_send_decisions_per_tier(db_session):
    hot = _prospect(1, ProspectState.LI_REQ_SENT, QualificationLevel.HOT, 90.0)
    medium = _prospect(2, ProspectState.EMAIL_SENT, QualificationLevel.MEDIUM, 45.0)
    db_session.add_all([hot, medium])
    await db_session.flush()

    db_session.add_all([
        _decision_log(hot, DecisionType.SEND_LINKEDIN),
        _decision_log(hot, DecisionType.SEND_LINKEDIN),  # two sends for the same HOT prospect
        _decision_log(medium, DecisionType.SEND_EMAIL),
        _decision_log(medium, DecisionType.WAIT),  # not a send - must not be counted
    ])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).messages_by_priority()

    assert data["messages_sent_by_priority"]["HOT"] == 2
    assert data["messages_sent_by_priority"]["MEDIUM"] == 1
    assert data["messages_sent_by_priority"]["LOW"] == 0


async def test_conversion_by_priority_reports_meeting_and_reply_rates(db_session):
    hot_booked = _prospect(1, ProspectState.MEETING_BOOKED, QualificationLevel.HOT, 90.0)
    hot_pending = _prospect(2, ProspectState.LI_REQ_SENT, QualificationLevel.HOT, 88.0)
    low_pending = _prospect(3, ProspectState.EMAIL_SENT, QualificationLevel.LOW, 20.0)
    db_session.add_all([hot_booked, hot_pending, low_pending])
    await db_session.flush()

    # conversion_by_priority groups by each prospect's most recently logged
    # DecisionLog snapshot (Sprint 6, item 4) - every prospect needs at
    # least one logged decision to be included at all.
    db_session.add_all([
        _decision_log(hot_booked, DecisionType.WAIT),
        _decision_log(hot_pending, DecisionType.SEND_LINKEDIN),
        _decision_log(low_pending, DecisionType.SEND_EMAIL),
    ])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).conversion_by_priority()

    hot_stats = data["conversion_by_priority"]["HOT"]
    assert hot_stats["total"] == 2
    assert hot_stats["meetings_booked"] == 1
    assert hot_stats["meeting_rate_pct"] == 50.0

    low_stats = data["conversion_by_priority"]["LOW"]
    assert low_stats["total"] == 1
    assert low_stats["meetings_booked"] == 0


async def test_qualification_accuracy_flags_when_priority_order_matches_outcomes(db_session):
    # HOT converts well, LOW doesn't - the scoring model "got it right".
    prospects = [
        _prospect(1, ProspectState.MEETING_BOOKED, QualificationLevel.HOT, 90.0),
        _prospect(2, ProspectState.CLOSED_WON, QualificationLevel.HOT, 92.0),
        _prospect(3, ProspectState.LOST, QualificationLevel.LOW, 15.0),
        _prospect(4, ProspectState.UNRESPONSIVE_DEAD, QualificationLevel.LOW, 10.0),
    ]
    db_session.add_all(prospects)
    await db_session.flush()

    # qualification_accuracy groups by each prospect's most recently logged
    # DecisionLog snapshot (Sprint 6, item 4).
    db_session.add_all([_decision_log(p, DecisionType.WAIT) for p in prospects])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).qualification_accuracy()

    assert data["qualification_accuracy_by_level"]["HOT"]["positive_rate_pct"] == 100.0
    assert data["qualification_accuracy_by_level"]["LOW"]["positive_rate_pct"] == 0.0
    assert data["priority_order_matches_outcomes"] is True


async def test_channel_performance_reports_reply_rates_per_channel(db_session):
    db_session.add_all([
        _prospect(1, ProspectState.LI_REQ_SENT),
        _prospect(2, ProspectState.LINKEDIN_REPLIED),
        _prospect(3, ProspectState.EMAIL_SENT),
        _prospect(4, ProspectState.EMAIL_REPLIED),
        _prospect(5, ProspectState.EMAIL_REPLIED),
        _prospect(6, ProspectState.CALL_CONNECTED),
        _prospect(7, ProspectState.CALL_NO_ANSWER_1),
    ])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).channel_performance()

    assert data["linkedin"]["total"] == 2
    assert data["linkedin"]["replied"] == 1
    assert data["email"]["total"] == 3
    assert data["email"]["replied"] == 2
    assert data["call"]["total"] == 2
    assert data["call"]["connected"] == 1
