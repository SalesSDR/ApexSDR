import uuid

from app.models.schemas import DecisionLog, DecisionType, Prospect, ProspectState, SequenceRule, SequenceStep
from app.services.decision.engine import SEQUENCE_STEP_TASK_NAME
from tests.conftest import bearer_for


async def test_preview_returns_a_decision_without_persisting_it(client, db_session):
    prospect = Prospect(
        tenant_id="org_dec_test", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-preview", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    rule = SequenceRule(id=str(uuid.uuid4()), tenant_id="org_dec_test")
    db_session.add(rule)
    await db_session.flush()
    db_session.add(SequenceStep(
        id=str(uuid.uuid4()), sequence_rule_id=rule.id, channel="LINKEDIN",
        step_number=1, title="LinkedIn Connection Request", delay_minutes=60,
    ))
    await db_session.flush()

    response = await client.get(
        f"/api/v1/decisions/{prospect.id}/preview", headers=bearer_for("org_dec_test")
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["decision_type"] == "SEND_LINKEDIN"
    assert data["task_to_enqueue"] == SEQUENCE_STEP_TASK_NAME
    assert 0.0 <= data["confidence"] <= 1.0

    from sqlalchemy import select
    rows = (await db_session.execute(select(DecisionLog).where(DecisionLog.prospect_id == prospect.id))).scalars().all()
    assert rows == []  # preview never writes a log row


async def test_preview_404s_for_unknown_prospect(client):
    response = await client.get(
        "/api/v1/decisions/does-not-exist/preview", headers=bearer_for("org_dec_test")
    )
    assert response.status_code == 404


async def test_history_returns_logged_decisions_most_recent_first(client, db_session):
    prospect = Prospect(
        tenant_id="org_dec_hist", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-hist", status=ProspectState.EMAIL_SENT,
    )
    db_session.add(prospect)
    await db_session.flush()

    db_session.add(DecisionLog(
        tenant_id="org_dec_hist", prospect_id=prospect.id, decision_type=DecisionType.SEND_EMAIL,
        reason="first", confidence=0.8, prospect_status_at_decision="LI_MSG_SENT",
    ))
    db_session.add(DecisionLog(
        tenant_id="org_dec_hist", prospect_id=prospect.id, decision_type=DecisionType.SCHEDULE_CALL,
        reason="second", confidence=0.75, prospect_status_at_decision="EMAIL_SENT",
    ))
    await db_session.flush()

    response = await client.get(
        f"/api/v1/decisions/{prospect.id}", headers=bearer_for("org_dec_hist")
    )

    assert response.status_code == 200
    entries = response.json()["data"]
    assert len(entries) == 2
    assert entries[0]["reason"] == "second"  # most recent first
    assert entries[1]["reason"] == "first"


async def test_history_and_preview_are_scoped_per_tenant(client, db_session):
    prospect = Prospect(
        tenant_id="org_dec_owner", first_name="Owner", last_name="Only",
        linkedin_url="https://linkedin.com/in/owner-only", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    other_tenant_resp = await client.get(
        f"/api/v1/decisions/{prospect.id}/preview", headers=bearer_for("org_dec_intruder")
    )
    assert other_tenant_resp.status_code == 404
