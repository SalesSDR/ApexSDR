import re

from app.models.schemas import EmailVerificationStatus
from app.services.email_verification.base import (
    EmailVerificationAdapter,
    VerificationResult,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MockEmailVerificationAdapter(EmailVerificationAdapter):
    """Deterministic, no network calls: syntax check plus a fixed denylist
    of obviously-fake test domains, so tests can exercise the INVALID path
    without needing to mock DNS."""

    BLOCKED_DOMAINS = {"invalid.test", "bounced.test", "example.invalid"}

    async def verify(self, email: str) -> VerificationResult:
        if not email or not _EMAIL_RE.match(email):
            return VerificationResult(EmailVerificationStatus.INVALID, "malformed address")
        domain = email.rsplit("@", 1)[-1].lower()
        if domain in self.BLOCKED_DOMAINS:
            return VerificationResult(EmailVerificationStatus.INVALID, "domain on mock denylist")
        return VerificationResult(EmailVerificationStatus.VALID, "syntax ok (mock)")
