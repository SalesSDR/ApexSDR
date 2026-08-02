import logging
from datetime import UTC, datetime, timedelta

from app.core.scheduling import get_next_business_time
from app.models.schemas import Prospect
from app.services.calendar.base import BusySlot, CalendarAdapter, EventDetails

logger = logging.getLogger(__name__)

DEFAULT_MEETING_DURATION_MINUTES = 30
MAX_SLOT_SEARCH_ATTEMPTS = 5


class CalendarService:
    """Business-logic layer over a CalendarAdapter: decides what meeting gets
    booked/updated/cancelled and when, the adapter just performs the I/O (or
    simulates it, in Mock mode)."""

    def __init__(self, adapter: CalendarAdapter):
        self.adapter = adapter

    async def get_busy_slots(self, start: datetime, end: datetime, prospect_timezone: str) -> list[BusySlot]:
        return await self.adapter.get_busy_slots(start, end, prospect_timezone)

    @staticmethod
    def is_slot_free(candidate_start: datetime, candidate_end: datetime, busy_slots: list[BusySlot]) -> bool:
        return all(candidate_start >= slot.end or candidate_end <= slot.start for slot in busy_slots)

    async def find_next_available_slot(
        self,
        prospect_timezone: str,
        duration_minutes: int = DEFAULT_MEETING_DURATION_MINUTES,
        earliest_start: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        """Searches forward in business-hours increments for a free slot. Falls
        back to the last candidate searched if nothing frees up within the
        bounded search - a slot must always be returned, never block booking."""
        candidate_start = get_next_business_time(
            earliest_start or (datetime.now(UTC) + timedelta(hours=24)), prospect_timezone
        )
        candidate_end = candidate_start + timedelta(minutes=duration_minutes)

        for _ in range(MAX_SLOT_SEARCH_ATTEMPTS):
            busy_slots = await self.get_busy_slots(candidate_start, candidate_end, prospect_timezone)
            if self.is_slot_free(candidate_start, candidate_end, busy_slots):
                break
            candidate_start = get_next_business_time(candidate_start + timedelta(hours=1), prospect_timezone)
            candidate_end = candidate_start + timedelta(minutes=duration_minutes)

        return candidate_start, candidate_end

    async def book_or_update_meeting(
        self,
        prospect: Prospect,
        start: datetime,
        end: datetime,
        prospect_timezone: str,
        description: str | None = None,
    ) -> str:
        """Avoids duplicate events: updates the existing event if one was
        already booked for this prospect, otherwise creates a new one."""
        event = EventDetails(
            summary=f"Meeting with {prospect.first_name} {prospect.last_name}",
            start=start,
            end=end,
            timezone=prospect_timezone,
            description=description,
            attendee_email=prospect.email,
        )
        if prospect.google_calendar_event_id:
            event_id = await self.adapter.update_event(prospect.google_calendar_event_id, event)
        else:
            event_id = await self.adapter.create_event(event)
        prospect.google_calendar_event_id = event_id
        return event_id

    async def schedule_default_meeting(self, prospect: Prospect, prospect_timezone: str = "America/New_York") -> str:
        """No explicit time was negotiated (no scheduling-link UI exists yet),
        so this finds the next free business-hours slot automatically."""
        start, end = await self.find_next_available_slot(prospect_timezone)
        description = f"Automatically scheduled by ApexSDR for {prospect.first_name} {prospect.last_name}."
        return await self.book_or_update_meeting(prospect, start, end, prospect_timezone, description)

    async def cancel_meeting(self, prospect: Prospect) -> None:
        if not prospect.google_calendar_event_id:
            return
        await self.adapter.delete_event(prospect.google_calendar_event_id)
        prospect.google_calendar_event_id = None
