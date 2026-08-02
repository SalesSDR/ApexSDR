import logging
import uuid

from app.services.voice.base import CallResult, VoiceAdapter

logger = logging.getLogger(__name__)


class MockTwilioAdapter(VoiceAdapter):
    """Simulates placing a call. Used whenever Twilio credentials are absent
    so the outbound pipeline can run end-to-end without a real Twilio account."""

    async def initiate_call(self, to_number: str, twimlet_url: str) -> CallResult:
        logger.info(f"MOCK ADAPTER ACTIVE: simulating Twilio call to {to_number}")
        return CallResult(sid=f"CA{uuid.uuid4().hex}", status="queued")
