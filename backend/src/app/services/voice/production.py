import logging

from twilio.rest import Client

from app.services.voice.base import CallResult, VoiceAdapter

logger = logging.getLogger(__name__)


class ProductionTwilioAdapter(VoiceAdapter):
    """Places real outbound calls via the Twilio SDK."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str, status_callback_base_url: str):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        self.status_callback_base_url = status_callback_base_url

    async def initiate_call(self, to_number: str, twimlet_url: str) -> CallResult:
        logger.info(f"Initiating Twilio call to {to_number}")
        try:
            # Twilio SDK is synchronous; acceptable here since ARQ tasks run
            # one at a time per worker slot rather than on a shared event loop
            # serving concurrent requests.
            call = self.client.calls.create(
                to=to_number,
                from_=self.from_number,
                url=twimlet_url,
                status_callback=f"{self.status_callback_base_url}/webhooks/twilio/call-status",
                status_callback_event=["completed", "answered", "busy", "no-answer", "failed"],
            )
            logger.info(f"Twilio call initiated. SID: {call.sid}")
            return CallResult(sid=call.sid, status=call.status)
        except Exception as e:
            logger.error(f"Twilio call dispatch failed for {to_number}: {str(e)}")
            raise
