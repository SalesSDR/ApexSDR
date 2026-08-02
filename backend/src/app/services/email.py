import logging
import os

import resend

from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.database import AsyncSessionLocal
from app.models.schemas import EmailVerificationStatus
from app.services.email_verification.service import ensure_verified, is_bounce_suppressed

logger = logging.getLogger(__name__)

# Initialize Resend with the API key from environment
resend.api_key = os.getenv("RESEND_API_KEY")

_RESEND_PROVIDER = "RESEND"


class EmailBlockedError(Exception):
    """Raised instead of attempting a send when the recipient is
    bounce-suppressed or failed email verification (Sprint 3, item 1)."""


async def send_native_email(recipient: str, subject: str, text: str) -> dict:
    """
    Sends an email using the Resend Python SDK, after verifying the
    recipient (once, cached) and confirming it isn't bounce-suppressed.
    Routes the actual dispatch through the shared circuit breaker for the
    RESEND provider so repeated provider outages fail fast instead of
    retrying a known-down provider on every call.
    """
    async with AsyncSessionLocal() as db:
        if await is_bounce_suppressed(db, recipient):
            logger.warning(f"Refusing to send to {recipient}: bounce-suppressed.")
            raise EmailBlockedError(f"{recipient} is bounce-suppressed")

        verification = await ensure_verified(db, recipient)
        if verification.status == EmailVerificationStatus.INVALID:
            logger.warning(f"Refusing to send to {recipient}: verification failed ({verification.reason}).")
            raise EmailBlockedError(f"{recipient} failed email verification: {verification.reason}")

    sender_email = os.getenv("RESEND_SENDER_EMAIL", os.getenv("GMAIL_SENDER_EMAIL", "myagenttest30@gmail.com"))

    logger.info(f"Resend dispatching email from {sender_email} to {recipient}")

    def _dispatch():
        # Convert plain text to simple HTML
        html_content = text.replace('\n', '<br>')
        return resend.Emails.send({
            "from": f"Apex SDR <{sender_email}>",
            "to": [recipient],
            "subject": subject,
            "html": html_content
        })

    try:
        response = await CircuitBreaker.call(_RESEND_PROVIDER, _dispatch)
        logger.info(f"Successfully sent Resend email to {recipient}. ID: {response.get('id')}")
        return {"status": "sent", "message_id": response.get("id")}
    except CircuitOpenError:
        logger.error(f"Resend circuit is open; refusing to send to {recipient}.")
        raise
    except Exception as e:
        logger.error(f"Resend email dispatch failed for {recipient}: {str(e)}")
        raise e
