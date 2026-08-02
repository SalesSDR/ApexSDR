"""Sprint 3, item 4: the Decision Engine must avoid unhealthy providers.
For LinkedIn this is satisfied without touching decision/engine.py (out of
scope this sprint) - DecisionEngine._linkedin_send_decision already gates
every LinkedIn send through LinkedInQueueService.can_send(), so extending
that one static method's health check is sufficient."""
from datetime import date

import pytest

from app.core.circuit_breaker import CircuitBreaker
from app.models.schemas import LinkedInAccount
from app.services.linkedin.service import LinkedInQueueService


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    CircuitBreaker.reset_all()
    yield
    CircuitBreaker.reset_all()


def _healthy_account() -> LinkedInAccount:
    return LinkedInAccount(
        tenant_id="t1", account_id="acct-1",
        daily_send_count=0, daily_limit=20, daily_count_date=date.today(),
    )


def test_can_send_is_true_for_a_healthy_account_and_healthy_provider():
    allowed, reason = LinkedInQueueService.can_send(_healthy_account())
    assert allowed is True
    assert reason is None


def test_can_send_is_false_when_the_linkedin_circuit_is_open():
    CircuitBreaker.configure("LINKEDIN", failure_threshold=1)
    CircuitBreaker.record_failure("LINKEDIN")

    allowed, reason = LinkedInQueueService.can_send(_healthy_account())
    assert allowed is False
    assert reason == "provider_unhealthy"


def test_provider_health_check_takes_priority_over_account_state():
    """Even an account with room in its daily quota must not be used while
    the shared provider circuit is open."""
    CircuitBreaker.configure("LINKEDIN", failure_threshold=1)
    CircuitBreaker.record_failure("LINKEDIN")

    account = _healthy_account()
    account.daily_send_count = 0
    account.is_paused = False

    allowed, reason = LinkedInQueueService.can_send(account)
    assert allowed is False
    assert reason == "provider_unhealthy"


def test_can_send_recovers_once_the_provider_circuit_closes_again():
    CircuitBreaker.configure("LINKEDIN", failure_threshold=1)
    CircuitBreaker.record_failure("LINKEDIN")
    assert LinkedInQueueService.can_send(_healthy_account())[0] is False

    CircuitBreaker.record_success("LINKEDIN")
    allowed, reason = LinkedInQueueService.can_send(_healthy_account())
    assert allowed is True
    assert reason is None
