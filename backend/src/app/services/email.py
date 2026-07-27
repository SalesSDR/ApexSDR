import os
import logging
import resend

logger = logging.getLogger(__name__)

# Initialize Resend with the API key from environment
resend.api_key = os.getenv("RESEND_API_KEY")

async def send_native_email(recipient: str, subject: str, text: str) -> dict:
    """
    Sends an email using the Resend Python SDK.
    """
    sender_email = os.getenv("RESEND_SENDER_EMAIL", os.getenv("GMAIL_SENDER_EMAIL", "myagenttest30@gmail.com"))
    
    logger.info(f"Resend dispatching email from {sender_email} to {recipient}")

    try:
        # Convert plain text to simple HTML
        html_content = text.replace('\n', '<br>')
        
        # Resend SDK call (synchronous in the underlying library, but we can wrap it or just call it)
        # Assuming we can just call it in an async context, or we can use asyncio.to_thread if it blocks.
        # Since resend SDK is synchronous, we use it directly:
        response = resend.Emails.send({
            "from": f"Apex SDR <{sender_email}>",
            "to": [recipient],
            "subject": subject,
            "html": html_content
        })
        
        logger.info(f"Successfully sent Resend email to {recipient}. ID: {response.get('id')}")
        return {"status": "sent", "message_id": response.get("id")}
    except Exception as e:
        logger.error(f"Resend email dispatch failed for {recipient}: {str(e)}")
        raise e
