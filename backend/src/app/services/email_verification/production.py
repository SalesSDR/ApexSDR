import asyncio
import logging
import re

import dns.resolver

from app.models.schemas import EmailVerificationStatus
from app.services.email_verification.base import (
    EmailVerificationAdapter,
    VerificationResult,
)

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ProductionEmailVerificationAdapter(EmailVerificationAdapter):
    """Real syntax + live MX-record verification - genuinely differs from
    Mock by performing a DNS MX lookup against the recipient's domain
    rather than trusting syntax alone. The lookup runs off the event loop
    via asyncio.to_thread since dnspython's resolver is synchronous."""

    async def verify(self, email: str) -> VerificationResult:
        if not email or not _EMAIL_RE.match(email):
            return VerificationResult(EmailVerificationStatus.INVALID, "malformed address")

        domain = email.rsplit("@", 1)[-1].lower()
        try:
            answers = await asyncio.to_thread(dns.resolver.resolve, domain, "MX")
            if answers:
                return VerificationResult(EmailVerificationStatus.VALID, "MX records present")
            return VerificationResult(EmailVerificationStatus.RISKY, "no MX records returned")
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return VerificationResult(EmailVerificationStatus.INVALID, "domain has no mail exchanger")
        except Exception as e:
            logger.warning(f"MX verification lookup failed for domain {domain}: {e}")
            return VerificationResult(EmailVerificationStatus.UNKNOWN, "verification lookup failed")
