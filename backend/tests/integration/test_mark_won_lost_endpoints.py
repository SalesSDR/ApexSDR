"""Sprint 5, item 5: POST /prospects/{id}/mark-won and /mark-lost."""
from app.models.schemas import Prospect, ProspectState
from tests.conftest import bearer_for


async def test_mark_won_transitions_to_closed_won_and_sets_deal_value(client, db_session):
    prospect = Prospect(
        tenant_id="org_mark_won", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-won", status=ProspectState.MEETING_BOOKED,
    )
    db_session.add(prospect)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/prospects/{prospect.id}/mark-won",
        json={"deal_value": 25000.0},
        headers=bearer_for("org_mark_won"),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "CLOSED_WON"
    assert body["estimated_deal_value"] == 25000.0

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.CLOSED_WON
    assert prospect.estimated_deal_value == 25000.0


async def test_mark_won_without_a_body_keeps_the_existing_deal_value(client, db_session):
    prospect = Prospect(
        tenant_id="org_mark_won_2", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-won", status=ProspectState.MEETING_BOOKED,
        estimated_deal_value=5000.0,
    )
    db_session.add(prospect)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/prospects/{prospect.id}/mark-won", headers=bearer_for("org_mark_won_2")
    )

    assert response.status_code == 200
    assert response.json()["data"]["estimated_deal_value"] == 5000.0


async def test_mark_won_rejects_an_illegal_transition(client, db_session):
    prospect = Prospect(
        tenant_id="org_mark_won_3", first_name="No", last_name="Meeting",
        linkedin_url="https://linkedin.com/in/no-meeting", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/prospects/{prospect.id}/mark-won", headers=bearer_for("org_mark_won_3")
    )
    assert response.status_code == 409


async def test_mark_won_404s_for_an_unknown_prospect(client):
    response = await client.post(
        "/api/v1/prospects/does-not-exist/mark-won", headers=bearer_for("org_mark_won_404")
    )
    assert response.status_code == 404


async def test_mark_lost_transitions_to_lost(client, db_session):
    prospect = Prospect(
        tenant_id="org_mark_lost", first_name="Katherine", last_name="Johnson",
        linkedin_url="https://linkedin.com/in/katherine-lost", status=ProspectState.MEETING_BOOKED,
    )
    db_session.add(prospect)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/prospects/{prospect.id}/mark-lost", headers=bearer_for("org_mark_lost")
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "LOST"

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.LOST


async def test_mark_won_requires_authentication(client, db_session):
    prospect = Prospect(
        tenant_id="org_mark_won_auth", first_name="Auth", last_name="Test",
        linkedin_url="https://linkedin.com/in/auth-test", status=ProspectState.MEETING_BOOKED,
    )
    db_session.add(prospect)
    await db_session.flush()

    response = await client.post(f"/api/v1/prospects/{prospect.id}/mark-won")
    assert response.status_code in (401, 403)
