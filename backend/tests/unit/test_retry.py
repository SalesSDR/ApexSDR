from datetime import UTC, datetime

from app.core.retry import DEFAULT_RETRY_POLICY, RetryPolicy, evaluate_retry
from app.models.schemas import Prospect, ProspectState


def _prospect_with_retry_count(count: int) -> Prospect:
    return Prospect(
        tenant_id="test-tenant",
        first_name="Alan",
        last_name="Turing",
        linkedin_url="https://linkedin.com/in/alan",
        retry_count=count,
    )


def test_retries_while_under_the_limit():
    for count in (0, 1, 2, 3, 4):
        outcome = evaluate_retry(_prospect_with_retry_count(count))
        assert outcome.should_retry is True
        assert outcome.new_status is None
        assert outcome.next_action_at is not None


def test_backoff_grows_with_each_attempt():
    first = evaluate_retry(_prospect_with_retry_count(0))
    second = evaluate_retry(_prospect_with_retry_count(1))
    assert second.next_action_at > first.next_action_at


def test_gives_up_once_max_retries_reached():
    # Sprint 3, item 2: the 5-tier [1, 2, 4, 8, 16]-hour backoff table means
    # retries are exhausted at retry_count == 5, not the old linear
    # policy's 3.
    outcome = evaluate_retry(_prospect_with_retry_count(5))
    assert outcome.should_retry is False
    assert outcome.new_status == ProspectState.ERROR_NEEDS_HUMAN
    assert outcome.next_action_at is None


def test_default_policy_is_the_five_tier_exponential_backoff_table():
    assert DEFAULT_RETRY_POLICY.backoff_hours == [1, 2, 4, 8, 16]
    assert DEFAULT_RETRY_POLICY.max_retries == 5


def test_backoff_hours_follow_the_exact_exponential_table():
    """Attempt N (1-indexed, i.e. retry_count == N-1) must wait exactly the
    Nth table value - not just "more than the previous attempt"."""
    policy = DEFAULT_RETRY_POLICY
    before = datetime.now(UTC)
    for attempt, expected_hours in enumerate([1, 2, 4, 8, 16], start=1):
        outcome = evaluate_retry(_prospect_with_retry_count(attempt - 1), policy=policy)
        delta_hours = (outcome.next_action_at - before).total_seconds() / 3600
        assert abs(delta_hours - expected_hours) < 0.01, f"attempt {attempt}: expected ~{expected_hours}h"


def test_delay_for_attempt_caps_at_the_last_table_value_beyond_its_length():
    policy = RetryPolicy(backoff_hours=[1, 2, 4])
    assert policy.delay_for_attempt(1) == 1
    assert policy.delay_for_attempt(3) == 4
    assert policy.delay_for_attempt(10) == 4  # capped, not IndexError


def test_custom_policy_is_reusable_independent_of_the_default():
    short_policy = RetryPolicy(backoff_hours=[1])
    outcome = evaluate_retry(_prospect_with_retry_count(1), policy=short_policy)
    assert outcome.should_retry is False  # exhausted after just 1 tier
    assert outcome.new_status == ProspectState.ERROR_NEEDS_HUMAN
