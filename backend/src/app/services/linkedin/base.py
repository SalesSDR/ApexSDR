from abc import ABC, abstractmethod
from typing import Any


class LinkedInRateLimitError(Exception):
    """Raised when the provider signals the account has been rate-limited
    (e.g. HTTP 429) - distinct from a generic send failure so the queue can
    pause the whole account instead of just retrying this one prospect."""


class LinkedInAdapter(ABC):
    """Interface for sending LinkedIn connection requests and messages.
    Implementations must raise on failure - LinkedInRateLimitError for
    provider-side throttling, any other Exception otherwise - rather than
    swallow errors, since callers rely on exceptions to drive retry/pause
    handling."""

    @abstractmethod
    async def send_connection_request(self, linkedin_url: str, account_id: str, message: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def send_message(self, account_id: str, provider_id: str, text: str) -> dict[str, Any]:
        raise NotImplementedError
