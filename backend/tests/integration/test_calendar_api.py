import pytest

from app.config import settings
from tests.conftest import bearer_for


@pytest.fixture(autouse=True)
def _use_mock_calendar_adapter(monkeypatch):
    # Sprint 7.1: get_calendar_adapter() now switches purely on
    # USE_MOCK_CLIENTS (see services/calendar/factory.py) - without this,
    # these tests would hit the real Google OAuth token endpoint.
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)


async def test_calendar_availability_endpoint_returns_free_when_no_events(client):
    response = await client.get(
        "/api/v1/calendar/availability",
        params={
            "start": "2026-08-03T14:00:00+00:00",
            "end": "2026-08-03T15:00:00+00:00",
            "timezone": "America/New_York",
        },
        headers=bearer_for("org_test"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["is_free"] is True
    assert body["data"]["busy_slots"] == []


async def test_calendar_availability_endpoint_rejects_invalid_range(client):
    response = await client.get(
        "/api/v1/calendar/availability",
        params={
            "start": "2026-08-03T15:00:00+00:00",
            "end": "2026-08-03T14:00:00+00:00",  # end before start
            "timezone": "UTC",
        },
        headers=bearer_for("org_test"),
    )

    assert response.status_code == 400


async def test_calendar_sync_status_endpoint_returns_empty_state_cleanly(client):
    response = await client.get(
        "/api/v1/calendar/sync-status",
        headers=bearer_for("org_test"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["last_calendar_sync"] is None
    assert body["data"]["upcoming_meetings"] == []
    assert body["data"]["failed_syncs"] == []
