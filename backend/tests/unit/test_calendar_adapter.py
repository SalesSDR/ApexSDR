from datetime import UTC, datetime, timedelta

from app.config import settings
from app.services.calendar.base import EventDetails
from app.services.calendar.factory import get_calendar_adapter
from app.services.calendar.mock import MockGoogleCalendarAdapter
from app.services.calendar.production import GoogleCalendarAdapter


def _set_google_credentials(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "fake-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setattr(settings, "GOOGLE_REFRESH_TOKEN", "fake-refresh-token")


async def test_factory_returns_mock_when_use_mock_clients(monkeypatch):
    # Sprint 7.1: USE_MOCK_CLIENTS is the ONE switch - even with real-looking
    # credentials configured, USE_MOCK_CLIENTS=true must guarantee no live
    # Google Calendar call.
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    _set_google_credentials(monkeypatch)

    adapter = get_calendar_adapter(http_client=None)

    assert isinstance(adapter, MockGoogleCalendarAdapter)


async def test_factory_returns_production_when_not_mock(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", False)
    _set_google_credentials(monkeypatch)

    adapter = get_calendar_adapter(http_client=None)

    assert isinstance(adapter, GoogleCalendarAdapter)


async def test_mock_adapter_reports_no_busy_slots():
    adapter = MockGoogleCalendarAdapter()
    start = datetime.now(UTC)
    end = start + timedelta(hours=1)

    busy_slots = await adapter.get_busy_slots(start, end, "America/New_York")

    assert busy_slots == []


async def test_mock_adapter_create_and_update_event_return_ids():
    adapter = MockGoogleCalendarAdapter()
    start = datetime.now(UTC)
    event = EventDetails(summary="Test Meeting", start=start, end=start + timedelta(minutes=30), timezone="UTC")

    event_id = await adapter.create_event(event)
    updated_id = await adapter.update_event(event_id, event)

    assert event_id.startswith("mock_event_")
    assert updated_id == event_id  # update reuses the same event ID
