import inspect
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# Providers this sprint names explicitly. Any other string key also works
# (see CircuitBreaker._get) - this tuple only guarantees these six always
# show up in get_all_status(), even before any traffic has gone through them.
SUPPORTED_PROVIDERS = ("HUBSPOT", "GOOGLE", "RESEND", "LINKEDIN", "GEMINI", "APOLLO")


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    """Raised by CircuitBreaker.call()/allow_request() when a provider's
    circuit is OPEN and its recovery timeout has not yet elapsed."""


def _now() -> float:
    """Thin wrapper around time.time() so tests can monkeypatch a single,
    narrow seam instead of patching the shared `time` module."""
    return time.time()


@dataclass
class _ProviderCircuit:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float | None = None
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    half_open_probe_in_flight: bool = False


class CircuitBreaker:
    """Per-provider circuit breaker (Closed/Open/Half-Open). In-memory,
    per-process, class-level state - standard circuit-breaker convention:
    fast-path avoidance of a known-bad provider without a DB round trip.
    State does not need to survive a process restart, since a fresh
    process should re-learn provider health from scratch rather than trust
    stale state.

    Any string provider key works (configure()/allow_request()/
    record_success()/record_failure() all lazily create a CLOSED circuit
    for unknown keys) - SUPPORTED_PROVIDERS just names the providers this
    sprint wires up instrumentation for.
    """

    _circuits: dict[str, _ProviderCircuit] = {}

    @classmethod
    def _get(cls, provider: str) -> _ProviderCircuit:
        if provider not in cls._circuits:
            cls._circuits[provider] = _ProviderCircuit()
        return cls._circuits[provider]

    @classmethod
    def configure(cls, provider: str, failure_threshold: int = 5, recovery_timeout_seconds: float = 60.0) -> None:
        circuit = cls._get(provider)
        circuit.failure_threshold = failure_threshold
        circuit.recovery_timeout_seconds = recovery_timeout_seconds

    @classmethod
    def allow_request(cls, provider: str) -> bool:
        """Whether a call to `provider` may proceed right now. OPEN blocks
        every call until the recovery timeout elapses, at which point
        exactly one probe call is allowed through (HALF_OPEN) while every
        other caller is still blocked."""
        circuit = cls._get(provider)
        if circuit.state == CircuitState.OPEN:
            if circuit.opened_at is not None and _now() - circuit.opened_at >= circuit.recovery_timeout_seconds:
                circuit.state = CircuitState.HALF_OPEN
                circuit.half_open_probe_in_flight = False
            else:
                return False
        if circuit.state == CircuitState.HALF_OPEN:
            if circuit.half_open_probe_in_flight:
                return False
            circuit.half_open_probe_in_flight = True
            return True
        return True

    @classmethod
    def record_success(cls, provider: str) -> None:
        circuit = cls._get(provider)
        circuit.state = CircuitState.CLOSED
        circuit.consecutive_failures = 0
        circuit.opened_at = None
        circuit.half_open_probe_in_flight = False

    @classmethod
    def record_failure(cls, provider: str) -> None:
        circuit = cls._get(provider)
        circuit.consecutive_failures += 1
        circuit.half_open_probe_in_flight = False
        if circuit.state == CircuitState.HALF_OPEN:
            # The probe call failed - back to OPEN for another full timeout.
            circuit.state = CircuitState.OPEN
            circuit.opened_at = _now()
            return
        if circuit.consecutive_failures >= circuit.failure_threshold:
            circuit.state = CircuitState.OPEN
            circuit.opened_at = _now()
            logger.warning(
                f"Circuit for provider '{provider}' opened after "
                f"{circuit.consecutive_failures} consecutive failures."
            )

    @classmethod
    def is_healthy(cls, provider: str) -> bool:
        return cls._get(provider).state != CircuitState.OPEN

    @classmethod
    def get_status(cls, provider: str) -> dict:
        circuit = cls._get(provider)
        return {
            "provider": provider,
            "state": circuit.state.value,
            "consecutive_failures": circuit.consecutive_failures,
            "opened_at": circuit.opened_at,
        }

    @classmethod
    def get_all_status(cls) -> list[dict]:
        keys = set(SUPPORTED_PROVIDERS) | set(cls._circuits.keys())
        return [cls.get_status(p) for p in sorted(keys)]

    @classmethod
    def reset_all(cls) -> None:
        """Test-isolation helper: clears all class-level circuit state."""
        cls._circuits = {}

    @classmethod
    async def call(cls, provider: str, func: Callable[..., Any], *args, **kwargs):
        """Invokes `func(*args, **kwargs)` through the breaker for
        `provider`: raises CircuitOpenError without calling `func` at all
        if the circuit is OPEN, otherwise calls it (awaiting the result if
        it returns an awaitable) and records success/failure accordingly."""
        if not cls.allow_request(provider):
            raise CircuitOpenError(f"Circuit for provider '{provider}' is OPEN")
        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            cls.record_failure(provider)
            raise
        else:
            cls.record_success(provider)
            return result
