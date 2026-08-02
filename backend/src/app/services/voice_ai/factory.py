from app.config import settings
from app.services.voice_ai.base import BaseVoiceAIProvider
from app.services.voice_ai.mock import MockVoiceAIProvider
from app.services.voice_ai.production import ProductionVoiceAIProvider


def get_voice_ai_provider() -> BaseVoiceAIProvider:
    if settings.USE_MOCK_CLIENTS:
        return MockVoiceAIProvider()
    return ProductionVoiceAIProvider()
