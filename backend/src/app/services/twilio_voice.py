import os
import logging
from twilio.rest import Client

logger = logging.getLogger(__name__)

# Initialize Twilio Client
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_FROM_NUMBER", os.getenv("TWILIO_PHONE_NUMBER"))

class TwilioVoiceService:
    def __init__(self):
        # We handle missing credentials gracefully if they aren't loaded in tests
        self.client = None
        if account_sid and auth_token:
            self.client = Client(account_sid, auth_token)

    async def initiate_call(self, to_number: str, twimlet_url: str) -> dict:
        """
        Initiates an outbound voice call via Twilio.
        """
        logger.info(f"Initiating Twilio call to {to_number}")
        
        if not self.client:
            logger.warning("Twilio client is not configured. Simulating call.")
            return {"sid": "simulated_call_sid", "status": "queued"}
            
        try:
            # Twilio SDK is synchronous, so we execute it
            # In a heavy load system, we might use run_in_executor
            call = self.client.calls.create(
                to=to_number,
                from_=twilio_number,
                url=twimlet_url,
                # Use status callback to receive updates on call progress
                status_callback=os.getenv("NEXT_PUBLIC_API_URL", "https://api.apexsdr.com") + "/webhooks/twilio/call-status",
                status_callback_event=["completed", "answered", "busy", "no-answer", "failed"]
            )
            
            logger.info(f"Twilio call initiated. SID: {call.sid}")
            return {"sid": call.sid, "status": call.status}
        except Exception as e:
            logger.error(f"Twilio call dispatch failed for {to_number}: {str(e)}")
            raise e
