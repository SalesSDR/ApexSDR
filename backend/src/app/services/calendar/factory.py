import logging

import httpx

from app.config import settings
from app.services.calendar.base import CalendarAdapter
from app.services.calendar.mock import MockGoogleCalendarAdapter
from app.services.calendar.production import GoogleCalendarAdapter

logger = logging.getLogger(__name__)


def get_calendar_adapter(http_client: httpx.AsyncClient) -> CalendarAdapter:
    """Single switch point, same rule as every other adapter factory
    (Sprint 7.1): USE_MOCK_CLIENTS is the ONE thing that decides mock vs.
    production - never credential presence."""
    if settings.USE_MOCK_CLIENTS:
        logger.info("Calendar adapter: USE_MOCK_CLIENTS=true, using MockGoogleCalendarAdapter.")
        return MockGoogleCalendarAdapter()
    logger.info("Calendar adapter: using GoogleCalendarAdapter.")
    return GoogleCalendarAdapter(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        refresh_token=settings.GOOGLE_REFRESH_TOKEN,
        http_client=http_client,
    )
