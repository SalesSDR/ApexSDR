import httpx

from app.config import settings
from app.services.voice_ai.tts.base import BaseTTSProvider
from app.services.voice_ai.tts.mock import MockTTSProvider
from app.services.voice_ai.tts.production import ElevenLabsTTSProvider


def get_tts_provider(http_client: httpx.AsyncClient) -> BaseTTSProvider:
    if settings.USE_MOCK_CLIENTS:
        return MockTTSProvider()
    return ElevenLabsTTSProvider(
        api_key=settings.ELEVENLABS_API_KEY,
        voice_id=settings.ELEVENLABS_VOICE_ID,
        http_client=http_client,
    )
