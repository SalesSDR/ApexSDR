from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.schemas import CalendarSyncLog, CalendarSyncStatus, Prospect, ProspectState
from app.services.calendar.base import CalendarAdapter, EventDetails
from app.workers.tasks import book_calendar_meeting_task, cancel_calendar_meeting_task, reschedule_calendar_meeting_task


class _FakeCalendarAdapter(CalendarAdapter):
    def __init__(self):
        self.created = []
        self.updated = []
        self.deleted = []

    async def get_busy_slots(self, start, end, timezone_name):
        return []

    async def create_event(self, event: EventDetails) -> str:
        event_id = f"event_{len(self.created)}"
        self.created.append(event_id)
        return event_id

    async def update_event(self, event_id: str, event: EventDetails) -> str:
        self.updated.append(event_id)
        return event_id

    async def delete_event(self, event_id: str) -> None:
        self.deleted.append(event_id)


class _RaisingCalendarAdapter(CalendarAdapter):
    async def get_busy_slots(self, start, end, timezone_name):
        raise RuntimeError("simulated Google Calendar API outage")

    async def create_event(self, event: EventDetails) -> str:
        raise RuntimeError("simulated Google Calendar API outage")

    async def update_event(self, event_id: str, event: EventDetails) -> str:
        raise RuntimeError("simulated Google Calendar API outage")

    async def delete_event(self, event_id: str) -> None:
        raise RuntimeError("simulated Google Calendar API outage")


class _FakeRedisPool:
    """Records enqueue_job calls so retry-requeue behavior can be asserted
    without a real Redis/ARQ connection."""

    def __init__(self):
        self.enqueued = []

    async def enqueue_job(self, task_name, *args, **kwargs):
        self.enqueued.append((task_name, args, kwargs))


async def test_book_calendar_meeting_task_creates_event_for_meeting_booked_prospect(db_session):
    from app.services.calendar.service import CalendarService

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Ada",
        last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-calendar",
        status=ProspectState.MEETING_BOOKED,
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_adapter = _FakeCalendarAdapter()
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {
        "sessionmaker": session_factory,
        "calendar_service": CalendarService(fake_adapter),
        "redis": _FakeRedisPool(),
    }

    await book_calendar_meeting_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.google_calendar_event_id is not None
    assert len(fake_adapter.created) == 1

    logs = (await db_session.execute(select(CalendarSyncLog).where(CalendarSyncLog.prospect_id == prospect.id))).scalars().all()
    assert any(log.status == CalendarSyncStatus.SUCCESS and log.event_type == "EVENT_CREATED" for log in logs)


async def test_book_calendar_meeting_task_updates_instead_of_duplicating(db_session):
    from app.services.calendar.service import CalendarService

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Grace",
        last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-calendar",
        status=ProspectState.MEETING_BOOKED,
        google_calendar_event_id="already_existing_event",
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_adapter = _FakeCalendarAdapter()
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {
        "sessionmaker": session_factory,
        "calendar_service": CalendarService(fake_adapter),
        "redis": _FakeRedisPool(),
    }

    await book_calendar_meeting_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.google_calendar_event_id == "already_existing_event"
    assert len(fake_adapter.created) == 0  # no duplicate
    assert len(fake_adapter.updated) == 1

    logs = (await db_session.execute(select(CalendarSyncLog).where(CalendarSyncLog.prospect_id == prospect.id))).scalars().all()
    assert any(log.status == CalendarSyncStatus.SUCCESS and log.event_type == "EVENT_UPDATED" for log in logs)


async def test_book_calendar_meeting_task_retries_via_centralized_retry_engine_on_failure(db_session):
    from app.services.calendar.service import CalendarService

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Rosalind",
        last_name="Franklin",
        linkedin_url="https://linkedin.com/in/rosalind-calendar",
        status=ProspectState.MEETING_BOOKED,
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_redis = _FakeRedisPool()
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {
        "sessionmaker": session_factory,
        "calendar_service": CalendarService(_RaisingCalendarAdapter()),
        "redis": fake_redis,
    }

    await book_calendar_meeting_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    # Failure must never change the prospect's own status - the outreach
    # outcome (a real booked meeting) already succeeded independently.
    assert prospect.status == ProspectState.MEETING_BOOKED
    assert prospect.retry_count == 1
    assert fake_redis.enqueued and fake_redis.enqueued[0][0] == "book_calendar_meeting_task"

    logs = (await db_session.execute(select(CalendarSyncLog).where(CalendarSyncLog.prospect_id == prospect.id))).scalars().all()
    assert any(log.status == CalendarSyncStatus.FAILED for log in logs)
    assert any(log.status == CalendarSyncStatus.PENDING for log in logs)


async def test_book_calendar_meeting_task_stops_retrying_after_exhaustion_without_changing_status(db_session):
    from app.services.calendar.service import CalendarService

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Marie",
        last_name="Curie",
        linkedin_url="https://linkedin.com/in/marie-calendar",
        status=ProspectState.MEETING_BOOKED,
        # Sprint 3, item 2: exponential backoff's 5-tier [1, 2, 4, 8, 16]
        # table moved the retry ceiling from 3 to 5.
        retry_count=5,  # already at the retry ceiling
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_redis = _FakeRedisPool()
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {
        "sessionmaker": session_factory,
        "calendar_service": CalendarService(_RaisingCalendarAdapter()),
        "redis": fake_redis,
    }

    await book_calendar_meeting_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.MEETING_BOOKED  # unchanged despite exhausted retries
    assert fake_redis.enqueued == []  # no further retry scheduled


async def test_cancel_calendar_meeting_task_deletes_event(db_session):
    from app.services.calendar.service import CalendarService

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Hedy",
        last_name="Lamarr",
        linkedin_url="https://linkedin.com/in/hedy-calendar",
        status=ProspectState.MEETING_BOOKED,
        google_calendar_event_id="event_to_cancel",
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_adapter = _FakeCalendarAdapter()
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {"sessionmaker": session_factory, "calendar_service": CalendarService(fake_adapter)}

    await cancel_calendar_meeting_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.google_calendar_event_id is None
    assert fake_adapter.deleted == ["event_to_cancel"]


async def test_reschedule_calendar_meeting_task_updates_event(db_session):
    from app.services.calendar.service import CalendarService

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Chien-Shiung",
        last_name="Wu",
        linkedin_url="https://linkedin.com/in/wu-calendar",
        status=ProspectState.MEETING_BOOKED,
        google_calendar_event_id="event_to_reschedule",
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_adapter = _FakeCalendarAdapter()
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {"sessionmaker": session_factory, "calendar_service": CalendarService(fake_adapter)}

    new_start = datetime.now(UTC) + timedelta(days=2)
    new_end = new_start + timedelta(minutes=30)
    await reschedule_calendar_meeting_task(ctx, prospect.id, new_start, new_end, "America/New_York")

    await db_session.refresh(prospect)
    assert prospect.google_calendar_event_id == "event_to_reschedule"
    assert fake_adapter.updated == ["event_to_reschedule"]
