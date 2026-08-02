import uuid
from datetime import date

from sqlalchemy import select

from app.config import settings
from app.models.schemas import (
    DecisionLog,
    DecisionType,
    LinkedInAccount,
    Prospect,
    ProspectState,
    SequenceRule,
    SequenceStep,
)
from app.services.decision.engine import DecisionEngine


async def _seed_sequence(db_session, tenant_id: str):
    """Minimal SequenceRule + the default 7-step SequenceStep chain, so
    decide_for_prospect() (which reads these from the DB) has something to
    advance through - without this, every mid-sequence status just gets
    "no further sequence step configured"."""
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
    return rule


async def test_decide_for_prospect_resolves_the_matching_linkedin_account(db_session, monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)  # deterministic profile_<tenant> fallback
    await _seed_sequence(db_session, "db-tenant")

    db_session.add(LinkedInAccount(
        tenant_id="db-tenant", account_id="profile_db-tenant",
        daily_send_count=20, daily_limit=20, daily_count_date=date.today(),
    ))
    prospect = Prospect(
        tenant_id="db-tenant", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-db", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    engine = DecisionEngine()
    decision = await engine.decide_for_prospect(db_session, prospect)

    assert decision.decision_type == DecisionType.WAIT  # blocked by the seeded at-limit account
    assert "daily send limit" in decision.reason


async def test_decide_for_prospect_ignores_linkedin_account_for_non_linkedin_states(db_session, monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)
    await _seed_sequence(db_session, "db-tenant-2")
    prospect = Prospect(
        tenant_id="db-tenant-2", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-db", status=ProspectState.EMAIL_SENT,
        sequence_step_index=4,  # -> CALL
    )
    db_session.add(prospect)
    await db_session.flush()

    engine = DecisionEngine()
    decision = await engine.decide_for_prospect(db_session, prospect)

    assert decision.decision_type == DecisionType.SCHEDULE_CALL


async def test_record_decision_persists_a_decision_log_row(db_session):
    # current_state is a separate, legacy column from `status` (never kept
    # in sync by transition_prospect()) - set explicitly here since this
    # test is about what record_decision() persists, not about that
    # pre-existing desync between the two fields.
    prospect = Prospect(
        tenant_id="log-tenant", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-log", status=ProspectState.IDLE,
        current_state="IDLE",
    )
    db_session.add(prospect)
    await db_session.flush()

    engine = DecisionEngine()
    sequence_steps = [SequenceStep(channel="LINKEDIN", step_number=1, title="LinkedIn", delay_minutes=60)]
    decision = engine.decide(prospect, sequence_steps=sequence_steps)
    await engine.record_decision(db_session, prospect, decision)

    rows = (await db_session.execute(
        select(DecisionLog).where(DecisionLog.prospect_id == prospect.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].decision_type == DecisionType.SEND_LINKEDIN
    assert rows[0].prospect_status_at_decision == "IDLE"
    assert rows[0].tenant_id == "log-tenant"
    assert rows[0].confidence == decision.confidence


async def test_decide_and_record_logs_exactly_once_per_call(db_session, monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)
    prospect = Prospect(
        tenant_id="log-tenant-2", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-log2", status=ProspectState.LI_REQ_SENT,
    )
    db_session.add(prospect)
    await db_session.flush()

    engine = DecisionEngine()
    await engine.decide_and_record(db_session, prospect)
    await engine.decide_and_record(db_session, prospect)

    rows = (await db_session.execute(
        select(DecisionLog).where(DecisionLog.prospect_id == prospect.id)
    )).scalars().all()
    assert len(rows) == 2
