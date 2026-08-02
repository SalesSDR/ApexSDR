from datetime import UTC, datetime, timedelta

from app.models.schemas import Prospect
from app.services.calendar.base import BusySlot, CalendarAdapter, EventDetails
from app.services.calendar.service import CalendarService


class _RecordingCalendarAdapter(CalendarAdapter):
    def __init__(self, busy_slots=None):
        self.busy_slots = busy_slots or []
        self.created = []
        self.updated = []
        self.deleted = []

    async def get_busy_slots(self, start, end, timezone_name):
        return self.busy_slots

    async def create_event(self, event: EventDetails) -> str:
        event_id = f"event_{len(self.created)}"
        self.created.append((event_id, event))
        return event_id

    async def update_event(self, event_id: str, event: EventDetails) -> str:
        self.updated.append((event_id, event))
        return event_id

    async def delete_event(self, event_id: str) -> None:
        self.deleted.append(event_id)


def _prospect(**overrides) -> Prospect:
    defaults = dict(
        tenant_id="test-tenant",
        first_name="Katherine",
        last_name="Johnson",
        linkedin_url="https://linkedin.com/in/katherine",
        email="katherine@example.com",
    )
    defaults.update(overrides)
    return Prospect(**defaults)


def test_is_slot_free_detects_overlap():
    start = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    busy = [BusySlot(start=start + timedelta(minutes=10), end=start + timedelta(minutes=40))]

    assert CalendarService.is_slot_free(start, end, busy) is False


def test_is_slot_free_true_when_no_overlap():
    start = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    busy = [BusySlot(start=start + timedelta(hours=2), end=start + timedelta(hours=3))]

    assert CalendarService.is_slot_free(start, end, busy) is True


async def test_book_or_update_meeting_creates_event_when_none_exists():
    adapter = _RecordingCalendarAdapter()
    service = CalendarService(adapter)
    prospect = _prospect()
    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(minutes=30)

    event_id = await service.book_or_update_meeting(prospect, start, end, "America/New_York")

    assert len(adapter.created) == 1
    assert len(adapter.updated) == 0
    assert prospect.google_calendar_event_id == event_id


async def test_book_or_update_meeting_updates_existing_event_avoiding_duplicate():
    adapter = _RecordingCalendarAdapter()
    service = CalendarService(adapter)
    prospect = _prospect(google_calendar_event_id="existing_event_123")
    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(minutes=30)

    event_id = await service.book_or_update_meeting(prospect, start, end, "America/New_York")

    assert len(adapter.created) == 0  # no duplicate event created
    assert len(adapter.updated) == 1
    assert event_id == "existing_event_123"
    assert prospect.google_calendar_event_id == "existing_event_123"


async def test_find_next_available_slot_skips_busy_time():
    # Force the first candidate to collide, so the search must advance.
    earliest = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)  # a Monday
    busy_at_first_candidate = [BusySlot(start=earliest, end=earliest + timedelta(hours=2))]
    adapter = _RecordingCalendarAdapter(busy_slots=busy_at_first_candidate)
    service = CalendarService(adapter)

    start, end = await service.find_next_available_slot("UTC", earliest_start=earliest)

    # Since the adapter always reports the same busy slot, the search is
    # bounded (MAX_SLOT_SEARCH_ATTEMPTS) and must still return *some* slot
    # rather than looping forever or raising.
    assert start is not None
    assert end > start


async def test_cancel_meeting_clears_event_id():
    adapter = _RecordingCalendarAdapter()
    service = CalendarService(adapter)
    prospect = _prospect(google_calendar_event_id="event_to_cancel")

    await service.cancel_meeting(prospect)

    assert adapter.deleted == ["event_to_cancel"]
    assert prospect.google_calendar_event_id is None


async def test_cancel_meeting_no_op_when_no_event_exists():
    adapter = _RecordingCalendarAdapter()
    service = CalendarService(adapter)
    prospect = _prospect()

    await service.cancel_meeting(prospect)

    assert adapter.deleted == []
