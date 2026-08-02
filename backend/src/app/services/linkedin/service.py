import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.circuit_breaker import CircuitBreaker
from app.models.schemas import LinkedInAccount
from app.services.linkedin.base import LinkedInAdapter, LinkedInRateLimitError

logger = logging.getLogger(__name__)

DEFAULT_PAUSE_HOURS = 4
_LINKEDIN_PROVIDER = "LINKEDIN"

# Sprint 6, item 3: LinkedIn's own connection-request note limit (enforced
# both by linkedin.com natively and by Unipile's /users/invite endpoint) -
# an over-length note is rejected by the provider outright, not merely
# truncated server-side, so this must never be exceeded before it's sent.
LINKEDIN_CONNECTION_NOTE_MAX_CHARS = 300
_TRUNCATION_SUFFIX = "…"


def truncate_connection_note(message: str | None, max_chars: int = LINKEDIN_CONNECTION_NOTE_MAX_CHARS) -> str | None:
    """Safely shortens a LinkedIn connection-request note to at most
    `max_chars`, never exceeding the provider's hard limit. Prefers cutting
    at the last whole word boundary within the limit (so the note doesn't
    end mid-word) and appends a single-character ellipsis to signal it was
    shortened - both still counted against max_chars, so the result is
    never longer than the limit."""
    if message is None or len(message) <= max_chars:
        return message

    budget = max_chars - len(_TRUNCATION_SUFFIX)
    if budget <= 0:
        return _TRUNCATION_SUFFIX[:max_chars]

    truncated = message[:budget]
    last_space = truncated.rfind(" ")
    # Only cut at the word boundary if it doesn't throw away most of the
    # budget (an unusually long single "word" just gets a hard cut instead).
    if last_space > budget * 0.5:
        truncated = truncated[:last_space]

    return truncated.rstrip() + _TRUNCATION_SUFFIX


def resolve_account_id(tenant_id: str) -> str:
    """Single place resolving which LinkedIn/Unipile account a tenant uses.
    Currently always the global settings.UNIPILE_ACCOUNT_ID (or a per-tenant
    fallback placeholder) - the seam future multi-account support extends."""
    return settings.UNIPILE_ACCOUNT_ID or f"profile_{tenant_id}"


class LinkedInQueueService:
    """Centralized gate every LinkedIn send goes through: resolves the
    sending account, enforces its daily cap and pause state, dispatches via
    the adapter, and pauses the account on provider-side rate-limiting.
    Business-hour timing and jitter stay in core/scheduling.py and
    apply_jitter() (reused, not duplicated) - this service only owns
    account-level queue state (daily count, pause)."""

    def __init__(self, adapter: LinkedInAdapter):
        self.adapter = adapter

    async def get_or_create_account(self, db: AsyncSession, tenant_id: str, account_id: str, daily_limit: int) -> LinkedInAccount:
        query = select(LinkedInAccount).where(
            LinkedInAccount.tenant_id == tenant_id,
            LinkedInAccount.account_id == account_id,
        ).with_for_update()
        res = await db.execute(query)
        account = res.scalar_one_or_none()
        if account is None:
            account = LinkedInAccount(tenant_id=tenant_id, account_id=account_id, daily_limit=daily_limit)
            db.add(account)
            try:
                # SELECT-then-INSERT races when multiple prospects for the
                # same tenant kick off their outbound sequence concurrently -
                # the FOR UPDATE lock above only guards a row that already
                # exists, not its own creation. A savepoint contains the
                # conflict to just this insert, so the caller's outer
                # transaction isn't poisoned by it.
                async with db.begin_nested():
                    await db.flush()
            except IntegrityError:
                db.expunge(account)
                res = await db.execute(query)
                account = res.scalar_one()
        LinkedInQueueService._reset_daily_count_if_needed(account)
        return account

    @staticmethod
    def _reset_daily_count_if_needed(account: LinkedInAccount) -> None:
        today = datetime.now(UTC).date()
        if account.daily_count_date != today:
            account.daily_count_date = today
            account.daily_send_count = 0

    @staticmethod
    def _maybe_lift_pause(account: LinkedInAccount) -> None:
        if account.is_paused and account.paused_until and datetime.now(UTC) >= account.paused_until:
            account.is_paused = False
            account.paused_reason = None
            account.paused_until = None

    @staticmethod
    def can_send(account: LinkedInAccount) -> tuple[bool, str | None]:
        """Returns (allowed, reason). Callers must not attempt a send when
        allowed is False - reschedule the prospect instead. Static/pure so
        callers that only need the queue-availability check (e.g. the
        Decision Engine) don't need an adapter instance to call it. Checks
        the shared LINKEDIN circuit breaker first (Sprint 3, item 4:
        provider-health avoidance) ahead of the account-specific checks."""
        if not CircuitBreaker.is_healthy(_LINKEDIN_PROVIDER):
            return False, "provider_unhealthy"
        LinkedInQueueService._reset_daily_count_if_needed(account)
        LinkedInQueueService._maybe_lift_pause(account)
        if account.is_paused:
            return False, "account_paused"
        if account.daily_send_count >= account.daily_limit:
            return False, "daily_limit_reached"
        return True, None

    @staticmethod
    def pause_account(account: LinkedInAccount, reason: str, duration_hours: int = DEFAULT_PAUSE_HOURS) -> None:
        account.is_paused = True
        account.paused_reason = reason
        account.paused_until = datetime.now(UTC) + timedelta(hours=duration_hours)
        logger.warning(f"LinkedIn account {account.account_id} paused ({reason}) until {account.paused_until}")

    async def send_connection_request(self, account: LinkedInAccount, linkedin_url: str, message: str | None = None) -> dict[str, Any]:
        safe_message = truncate_connection_note(message)
        if safe_message != message:
            logger.warning(
                f"Connection note for {linkedin_url} exceeded {LINKEDIN_CONNECTION_NOTE_MAX_CHARS} chars "
                f"({len(message)}); truncated before sending."
            )
        try:
            result = await CircuitBreaker.call(
                _LINKEDIN_PROVIDER, self.adapter.send_connection_request, linkedin_url, account.account_id, safe_message
            )
        except LinkedInRateLimitError:
            self.pause_account(account, reason="rate_limited")
            raise
        account.daily_send_count += 1
        return result

    async def send_message(self, account: LinkedInAccount, provider_id: str, text: str) -> dict[str, Any]:
        try:
            result = await CircuitBreaker.call(
                _LINKEDIN_PROVIDER, self.adapter.send_message, account.account_id, provider_id, text
            )
        except LinkedInRateLimitError:
            self.pause_account(account, reason="rate_limited")
            raise
        account.daily_send_count += 1
        return result
