from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.models.schemas import Prospect, ProspectState

# 5-tier exponential backoff, in hours: attempt 1 waits 1h, attempt 2 waits
# 2h, ... attempt 5 waits 16h. Retries are exhausted once retry_count
# reaches len(backoff_hours).
DEFAULT_BACKOFF_HOURS: list[int] = [1, 2, 4, 8, 16]


@dataclass(frozen=True)
class RetryPolicy:
    """Reusable exponential-backoff policy: any caller needing a different
    schedule (e.g. a shorter table for a cheaper channel) constructs its own
    RetryPolicy rather than this module growing per-channel special cases."""

    backoff_hours: list[int] = field(default_factory=lambda: list(DEFAULT_BACKOFF_HOURS))

    @property
    def max_retries(self) -> int:
        return len(self.backoff_hours)

    def delay_for_attempt(self, attempt: int) -> int:
        """1-indexed attempt number -> hours to wait. Attempts beyond the
        table length reuse the last (largest) configured delay rather than
        raising, so a caller that races past max_retries by one before the
        give-up check runs still gets a sane delay."""
        attempt = max(attempt, 1)
        index = min(attempt, len(self.backoff_hours)) - 1
        return self.backoff_hours[index]


DEFAULT_RETRY_POLICY = RetryPolicy()


@dataclass
class RetryOutcome:
    should_retry: bool
    next_action_at: datetime | None
    new_status: ProspectState | None  # set only when retries are exhausted


def evaluate_retry(prospect: Prospect, policy: RetryPolicy = DEFAULT_RETRY_POLICY) -> RetryOutcome:
    """Pure decision function for the per-channel retry policy shared by
    every outbound task. No DB/Redis I/O - the caller applies the resulting
    mutation. Exponential backoff via `policy` (default: 1, 2, 4, 8, 16
    hours) replaces the old fixed linear delay."""
    if prospect.retry_count >= policy.max_retries:
        return RetryOutcome(should_retry=False, next_action_at=None, new_status=ProspectState.ERROR_NEEDS_HUMAN)
    attempt = prospect.retry_count + 1
    delay_hours = policy.delay_for_attempt(attempt)
    next_action_at = datetime.now(UTC) + timedelta(hours=delay_hours)
    return RetryOutcome(should_retry=True, next_action_at=next_action_at, new_status=None)
