from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BusySlot:
    start: datetime
    end: datetime


@dataclass
class EventDetails:
    summary: str
    start: datetime
    end: datetime
    timezone: str
    description: str | None = None
    attendee_email: str | None = None
    reminder_minutes_before: list[int] = field(default_factory=lambda: [30, 24 * 60])


class CalendarAdapter(ABC):
    """Interface for calendar availability and event management. Implementations
    should raise only on real I/O failure - the pipeline's own retry engine
    (core/retry.py) decides what happens next, not the adapter."""

    @abstractmethod
    async def get_busy_slots(self, start: datetime, end: datetime, timezone: str) -> list[BusySlot]:
        """Returns busy time ranges within [start, end] for free/busy detection."""
        raise NotImplementedError

    @abstractmethod
    async def create_event(self, event: EventDetails) -> str:
        """Creates a calendar event. Returns the calendar's event ID."""
        raise NotImplementedError

    @abstractmethod
    async def update_event(self, event_id: str, event: EventDetails) -> str:
        """Updates an existing event (reschedule, detail changes). Returns the event ID."""
        raise NotImplementedError

    @abstractmethod
    async def delete_event(self, event_id: str) -> None:
        """Cancels/deletes an existing event."""
        raise NotImplementedError
