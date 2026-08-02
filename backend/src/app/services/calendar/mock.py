import logging
import uuid
from datetime import datetime

from app.services.calendar.base import BusySlot, CalendarAdapter, EventDetails

logger = logging.getLogger(__name__)


class MockGoogleCalendarAdapter(CalendarAdapter):
    """Simulates Google Calendar. Used whenever Google OAuth credentials are
    absent so meeting booking can run end-to-end without a real Google account.
    Always reports the calendar as free - there's no real calendar to check."""

    async def get_busy_slots(self, start: datetime, end: datetime, timezone: str) -> list[BusySlot]:
        logger.info(f"MOCK CALENDAR ACTIVE: reporting no busy slots between {start} and {end} ({timezone})")
        return []

    async def create_event(self, event: EventDetails) -> str:
        event_id = f"mock_event_{uuid.uuid4().hex[:12]}"
        logger.info(f"MOCK CALENDAR ACTIVE: created event {event_id} ({event.summary} at {event.start})")
        return event_id

    async def update_event(self, event_id: str, event: EventDetails) -> str:
        logger.info(f"MOCK CALENDAR ACTIVE: updated event {event_id} ({event.summary} at {event.start})")
        return event_id

    async def delete_event(self, event_id: str) -> None:
        logger.info(f"MOCK CALENDAR ACTIVE: deleted event {event_id}")
