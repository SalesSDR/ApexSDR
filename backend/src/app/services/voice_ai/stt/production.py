import logging

import httpx

from app.services.voice_ai.stt.base import BaseSTTProvider
from app.services.voice_ai.stt.recording_url_validation import (
    UntrustedRecordingURLError,
    validate_recording_url,
)

logger = logging.getLogger(__name__)

DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"


class DeepgramSTTProvider(BaseSTTProvider):
    """Transcribes a Twilio call recording via Deepgram's prerecorded-audio
    API. Twilio recordings require Twilio's own Basic Auth to fetch (they
    are not public URLs), so this downloads the audio first and posts the
    raw bytes to Deepgram, rather than handing Deepgram the bare
    `recording_url` (which Deepgram could not authenticate against)."""

    def __init__(
        self,
        api_key: str | None,
        http_client: httpx.AsyncClient,
        twilio_account_sid: str | None,
        twilio_auth_token: str | None,
    ):
        self.api_key = api_key
        self.http_client = http_client
        self.twilio_account_sid = twilio_account_sid
        self.twilio_auth_token = twilio_auth_token

    async def transcribe(self, recording_url: str) -> str:
        audio_bytes = await self._download_recording(recording_url)

        response = await self.http_client.post(
            DEEPGRAM_LISTEN_URL,
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "audio/mpeg",
            },
            content=audio_bytes,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        try:
            return data["results"]["channels"][0]["alternatives"][0]["transcript"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected Deepgram response shape: {data}") from e

    async def _download_recording(self, recording_url: str) -> bytes:
        # Twilio's RecordingUrl needs an explicit media extension to return
        # the audio bytes rather than a metadata JSON document.
        url = recording_url if recording_url.endswith(".mp3") else f"{recording_url}.mp3"

        # SSRF protection (Sprint 7.1): recording_url ultimately comes from
        # an inbound webhook's form data, not from anything this backend
        # constructed itself - never fetch it, and never attach Twilio's
        # real credentials to it, without validating it first.
        await validate_recording_url(url)

        auth = (self.twilio_account_sid, self.twilio_auth_token) if self.twilio_account_sid else None
        response = await self.http_client.get(url, auth=auth, timeout=30.0, follow_redirects=False)
        if response.is_redirect:
            raise UntrustedRecordingURLError(
                f"Recording URL returned an unexpected redirect to {response.headers.get('location')!r}"
            )
        response.raise_for_status()
        return response.content
