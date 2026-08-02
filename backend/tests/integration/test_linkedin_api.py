from datetime import UTC, date, datetime, timedelta

from app.models.schemas import LinkedInAccount
from tests.conftest import bearer_for


async def test_queue_status_endpoint_returns_empty_when_no_account_exists(client):
    response = await client.get(
        "/api/v1/linkedin/queue-status",
        headers=bearer_for("org_test"),
    )

    assert response.status_code == 200
    assert response.json()["data"]["accounts"] == []


async def test_queue_status_endpoint_reports_account_state(client, db_session):
    db_session.add(LinkedInAccount(
        tenant_id="org_test",
        account_id="acc_1",
        daily_send_count=5,
        daily_limit=20,
        daily_count_date=date.today(),
        is_paused=True,
        paused_reason="rate_limited",
        paused_until=datetime.now(UTC) + timedelta(hours=1),
    ))
    await db_session.flush()

    response = await client.get(
        "/api/v1/linkedin/queue-status",
        headers=bearer_for("org_test"),
    )

    assert response.status_code == 200
    accounts = response.json()["data"]["accounts"]
    assert len(accounts) == 1
    account = accounts[0]
    assert account["account_id"] == "acc_1"
    assert account["daily_send_count"] == 5
    assert account["remaining_today"] == 15
    assert account["is_paused"] is True
    assert account["paused_reason"] == "rate_limited"
