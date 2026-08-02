import httpx

from app.config import settings
from app.services.voice_ai.stt.base import BaseSTTProvider
from app.services.voice_ai.stt.mock import MockSTTProvider
from app.services.voice_ai.stt.production import DeepgramSTTProvider


def get_stt_provider(http_client: httpx.AsyncClient) -> BaseSTTProvider:
    if settings.USE_MOCK_CLIENTS:
        return MockSTTProvider()
    return DeepgramSTTProvider(
        api_key=settings.DEEPGRAM_API_KEY,
        http_client=http_client,
        twilio_account_sid=settings.TWILIO_ACCOUNT_SID,
        twilio_auth_token=settings.TWILIO_AUTH_TOKEN,
    )
