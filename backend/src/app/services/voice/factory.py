import logging

from app.config import settings
from app.services.voice.base import VoiceAdapter
from app.services.voice.mock import MockTwilioAdapter
from app.services.voice.production import ProductionTwilioAdapter

logger = logging.getLogger(__name__)


def get_voice_adapter() -> VoiceAdapter:
    """Single switch point, same rule as every other adapter factory
    (Sprint 7.1): USE_MOCK_CLIENTS is the ONE thing that decides mock vs.
    production - never credential presence."""
    if settings.USE_MOCK_CLIENTS:
        logger.info("Voice adapter: USE_MOCK_CLIENTS=true, using MockTwilioAdapter.")
        return MockTwilioAdapter()
    logger.info("Voice adapter: using ProductionTwilioAdapter.")
    return ProductionTwilioAdapter(
        account_sid=settings.TWILIO_ACCOUNT_SID,
        auth_token=settings.TWILIO_AUTH_TOKEN,
        from_number=settings.TWILIO_FROM_NUMBER,
        status_callback_base_url=settings.PUBLIC_BASE_URL,
    )
