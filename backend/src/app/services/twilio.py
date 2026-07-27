import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TwilioClient:
    """
    Service adapter for the Twilio API to execute automated voice engagement steps.
    """
    def __init__(self, account_sid: Optional[str], auth_token: Optional[str], from_number: Optional[str], http_client: httpx.AsyncClient):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.client = http_client
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}" if account_sid else ""

    async def initiate_call(self, to_number: str, twimlet_url: Optional[str] = None, twiml: Optional[str] = None) -> Dict[str, Any]:
        """
        Triggers an automated dial job using the Twilio voice platform.
        Supports either Url or inline Twiml for Media Streams.
        """
        # If Twilio values are default/stub credentials, fall back to mock data
        if not self.account_sid or "ACabcdef" in self.account_sid or not self.auth_token:
            logger.info(f"Twilio: Using mock call placement behavior to number: {to_number}")
            return {
                "sid": "CA1234567890abcdef1234567890abcdef",
                "status": "queued"
            }

        url = f"{self.base_url}/Calls.json"
        data = {
            "To": to_number,
            "From": self.from_number
        }
        if twiml:
            data["Twiml"] = twiml
        elif twimlet_url:
            data["Url"] = twimlet_url
        
        try:
            response = await self.client.post(
                url,
                data=data,
                auth=(self.account_sid, self.auth_token),
                timeout=10.0
            )
            if response.status_code in [200, 201]:
                res_data = response.json()
                logger.info(f"Twilio Call placed successfully to {to_number}. Call SID: {res_data.get('sid')}")
                return res_data
            logger.warning(f"Twilio API returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Twilio call placement request failed: {str(e)}")

        return {}
