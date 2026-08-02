import logging
from datetime import datetime

import httpx

from app.services.calendar.base import BusySlot, CalendarAdapter, EventDetails

logger = logging.getLogger(__name__)


class GoogleCalendarAdapter(CalendarAdapter):
    """Syncs meetings to a real Google Calendar via the Calendar v3 API,
    authenticated with an OAuth2 refresh token (offline access)."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    BASE_URL = "https://www.googleapis.com/calendar/v3"
    CALENDAR_ID = "primary"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, http_client: httpx.AsyncClient):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.client = http_client

    async def _get_access_token(self) -> str:
        # A fresh token is requested per operation rather than cached: calendar
        # operations are infrequent (one per meeting), so the extra round-trip
        # is negligible next to the complexity of tracking token expiry.
        response = await self.client.post(
            self.TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10.0,
        )
        if response.status_code != 200:
            raise Exception(f"Google OAuth token refresh failed: {response.status_code}: {response.text}")
        return response.json()["access_token"]

    async def _headers(self) -> dict:
        token = await self._get_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _event_payload(self, event: EventDetails) -> dict:
        payload = {
            "summary": event.summary,
            "start": {"dateTime": event.start.isoformat(), "timeZone": event.timezone},
            "end": {"dateTime": event.end.isoformat(), "timeZone": event.timezone},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": m} for m in event.reminder_minutes_before],
            },
        }
        if event.description:
            payload["description"] = event.description
        if event.attendee_email:
            payload["attendees"] = [{"email": event.attendee_email}]
        return payload

    async def get_busy_slots(self, start: datetime, end: datetime, timezone: str) -> list[BusySlot]:
        headers = await self._headers()
        payload = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": timezone,
            "items": [{"id": self.CALENDAR_ID}],
        }
        response = await self.client.post(f"{self.BASE_URL}/freeBusy", json=payload, headers=headers, timeout=10.0)
        if response.status_code != 200:
            raise Exception(f"Google Calendar freeBusy query failed: {response.status_code}: {response.text}")

        busy_ranges = response.json()["calendars"][self.CALENDAR_ID].get("busy", [])
        return [
            BusySlot(start=datetime.fromisoformat(r["start"]), end=datetime.fromisoformat(r["end"]))
            for r in busy_ranges
        ]

    async def create_event(self, event: EventDetails) -> str:
        headers = await self._headers()
        response = await self.client.post(
            f"{self.BASE_URL}/calendars/{self.CALENDAR_ID}/events",
            json=self._event_payload(event),
            headers=headers,
            timeout=10.0,
        )
        if response.status_code not in (200, 201):
            raise Exception(f"Google Calendar event create failed: {response.status_code}: {response.text}")
        return response.json()["id"]

    async def update_event(self, event_id: str, event: EventDetails) -> str:
        headers = await self._headers()
        response = await self.client.patch(
            f"{self.BASE_URL}/calendars/{self.CALENDAR_ID}/events/{event_id}",
            json=self._event_payload(event),
            headers=headers,
            timeout=10.0,
        )
        if response.status_code not in (200, 201):
            raise Exception(f"Google Calendar event update failed: {response.status_code}: {response.text}")
        return response.json()["id"]

    async def delete_event(self, event_id: str) -> None:
        headers = await self._headers()
        response = await self.client.delete(
            f"{self.BASE_URL}/calendars/{self.CALENDAR_ID}/events/{event_id}",
            headers=headers,
            timeout=10.0,
        )
        # Google returns 410 Gone if the event was already deleted - treat as success.
        if response.status_code not in (200, 204, 410):
            raise Exception(f"Google Calendar event delete failed: {response.status_code}: {response.text}")
