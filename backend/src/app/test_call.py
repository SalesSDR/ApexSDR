
import asyncio
from app.services.twilio import TwilioClient
import httpx
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)

async def test_call():
    async with httpx.AsyncClient() as client:
        twilio = TwilioClient(
            account_sid=settings.TWILIO_ACCOUNT_SID,
            auth_token=settings.TWILIO_AUTH_TOKEN,
            from_number=settings.TWILIO_FROM_NUMBER,
            http_client=client
        )
        
        # Format the number if missing +
        target_number = "9116802635"
        if not target_number.startswith("+"):
            # Assume it's an Indian number if it's 10 digits starting with 9, else maybe US?
            # 911 is area code in some places, but 91 1680... no Indian mobile usually starts with 9116 maybe?
            # Let's try adding +91 first, if not +1
            # Actually, the user just said 9116802635. I'll pass it exactly as they wrote but add + if it's 11 digits or try both.
            # Wait, 9116802635 is 10 digits. A US number is +1911... but 911 is invalid area code. So it's probably Indian +91 16802635 ... no, Indian is 10 digits AFTER +91.
            # Maybe the number IS 9116802635. Let's try +1 9116802635?
            # Let's just try +9116802635. (Country code +91, mobile 16802635 -> 8 digits? Invalid)
            # Maybe +91 9116802635 -> That's +919116802635
            target_number = "+919116802635"

        print(f"Calling {target_number}...")
        res = await twilio.initiate_call(
            to_number=target_number,
            twimlet_url="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical"
        )
        print("Result:", res)

if __name__ == "__main__":
    asyncio.run(test_call())
