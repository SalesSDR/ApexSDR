import logging

import httpx

from app.services.voice_ai.tts.base import BaseTTSProvider, SynthesizedAudio

logger = logging.getLogger(__name__)


class ElevenLabsTTSProvider(BaseTTSProvider):
    """Synthesizes speech via the ElevenLabs text-to-speech API."""

    def __init__(self, api_key: str | None, voice_id: str, http_client: httpx.AsyncClient):
        self.api_key = api_key
        self.voice_id = voice_id
        self.http_client = http_client

    async def synthesize(self, text: str) -> SynthesizedAudio:
        response = await self.http_client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return SynthesizedAudio(audio_bytes=response.content, content_type="audio/mpeg")
