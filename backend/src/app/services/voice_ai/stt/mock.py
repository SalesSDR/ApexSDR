import logging

from app.services.voice_ai.stt.base import BaseSTTProvider

logger = logging.getLogger(__name__)


class MockSTTProvider(BaseSTTProvider):
    """No network access, no Deepgram account needed. Treats `recording_url`
    as the transcript itself (identity passthrough) so tests/mock-mode
    callers can simulate "the prospect said X" by passing X directly,
    without needing a real audio file anywhere."""

    async def transcribe(self, recording_url: str) -> str:
        logger.info(f"MOCK STT ACTIVE: passing through '{recording_url}' as the transcript")
        return recording_url
