import pytest

import app.core.circuit_breaker as cb_module
from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Class-level state must not leak between tests in the same process."""
    CircuitBreaker.reset_all()
    yield
    CircuitBreaker.reset_all()


class _FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def advance(self, seconds: float):
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def test_starts_closed_and_allows_requests():
    assert CircuitBreaker.is_healthy("HUBSPOT") is True
    assert CircuitBreaker.allow_request("HUBSPOT") is True


def test_opens_after_reaching_the_failure_threshold():
    CircuitBreaker.configure("GEMINI", failure_threshold=3, recovery_timeout_seconds=60.0)
    for _ in range(3):
        CircuitBreaker.record_failure("GEMINI")
    assert CircuitBreaker.get_status("GEMINI")["state"] == CircuitState.OPEN.value
    assert CircuitBreaker.is_healthy("GEMINI") is False
    assert CircuitBreaker.allow_request("GEMINI") is False


def test_a_success_before_the_threshold_resets_the_failure_count():
    CircuitBreaker.configure("APOLLO", failure_threshold=3)
    CircuitBreaker.record_failure("APOLLO")
    CircuitBreaker.record_failure("APOLLO")
    CircuitBreaker.record_success("APOLLO")
    assert CircuitBreaker.get_status("APOLLO")["consecutive_failures"] == 0
    assert CircuitBreaker.is_healthy("APOLLO") is True


def test_transitions_to_half_open_after_the_recovery_timeout(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(cb_module, "_now", clock)

    CircuitBreaker.configure("RESEND", failure_threshold=1, recovery_timeout_seconds=30.0)
    CircuitBreaker.record_failure("RESEND")
    assert CircuitBreaker.get_status("RESEND")["state"] == CircuitState.OPEN.value
    assert CircuitBreaker.allow_request("RESEND") is False  # still within timeout

    clock.advance(31.0)
    assert CircuitBreaker.allow_request("RESEND") is True  # single probe allowed through
    assert CircuitBreaker.get_status("RESEND")["state"] == CircuitState.HALF_OPEN.value
    # A second concurrent caller must not also get a probe slot.
    assert CircuitBreaker.allow_request("RESEND") is False


def test_half_open_success_closes_the_circuit(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(cb_module, "_now", clock)

    CircuitBreaker.configure("LINKEDIN", failure_threshold=1, recovery_timeout_seconds=10.0)
    CircuitBreaker.record_failure("LINKEDIN")
    clock.advance(11.0)
    assert CircuitBreaker.allow_request("LINKEDIN") is True
    CircuitBreaker.record_success("LINKEDIN")
    assert CircuitBreaker.get_status("LINKEDIN")["state"] == CircuitState.CLOSED.value


def test_half_open_failure_reopens_the_circuit(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(cb_module, "_now", clock)

    CircuitBreaker.configure("GOOGLE", failure_threshold=1, recovery_timeout_seconds=10.0)
    CircuitBreaker.record_failure("GOOGLE")
    clock.advance(11.0)
    assert CircuitBreaker.allow_request("GOOGLE") is True
    CircuitBreaker.record_failure("GOOGLE")
    assert CircuitBreaker.get_status("GOOGLE")["state"] == CircuitState.OPEN.value


async def test_call_records_success_on_a_clean_call():
    async def _ok():
        return "fine"

    result = await CircuitBreaker.call("HUBSPOT", _ok)
    assert result == "fine"
    assert CircuitBreaker.get_status("HUBSPOT")["consecutive_failures"] == 0


async def test_call_records_failure_and_reraises_on_exception():
    CircuitBreaker.configure("APOLLO", failure_threshold=5)

    async def _boom():
        raise ValueError("upstream exploded")

    with pytest.raises(ValueError):
        await CircuitBreaker.call("APOLLO", _boom)
    assert CircuitBreaker.get_status("APOLLO")["consecutive_failures"] == 1


async def test_call_refuses_to_invoke_func_when_the_circuit_is_open():
    CircuitBreaker.configure("RESEND", failure_threshold=1)
    CircuitBreaker.record_failure("RESEND")

    calls = []

    async def _would_call():
        calls.append(1)
        return "should never happen"

    with pytest.raises(CircuitOpenError):
        await CircuitBreaker.call("RESEND", _would_call)
    assert calls == []  # func itself was never invoked


async def test_call_supports_sync_callables_too():
    def _sync_ok():
        return 42

    result = await CircuitBreaker.call("GEMINI", _sync_ok)
    assert result == 42


def test_get_all_status_always_includes_the_named_providers():
    statuses = {row["provider"] for row in CircuitBreaker.get_all_status()}
    for provider in ("HUBSPOT", "GOOGLE", "RESEND", "LINKEDIN", "GEMINI", "APOLLO"):
        assert provider in statuses
