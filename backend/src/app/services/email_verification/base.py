from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.schemas import EmailVerificationStatus


@dataclass
class VerificationResult:
    status: EmailVerificationStatus
    reason: str


class EmailVerificationAdapter(ABC):
    """Module 12: verifies a recipient address before its first send.
    Mock/Production/Factory mirror the adapter pattern already used for
    CRM, Calendar, LinkedIn, Voice, Compliance, and Signals."""

    @abstractmethod
    async def verify(self, email: str) -> VerificationResult:
        ...
