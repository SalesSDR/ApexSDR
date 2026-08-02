"""Integration coverage for services.email.send_native_email: the actual
send boundary that gates on bounce-suppression and email verification
before ever calling Resend (Sprint 3, item 1), and that routes the real
dispatch through the shared RESEND circuit breaker (item 3).

send_native_email opens its own short-lived DB session (app.database.
AsyncSessionLocal) rather than taking one as a parameter - workers/tasks.py
(the Sequence Engine, out of scope this sprint) calls it with only
recipient/subject/text and no session to pass in. Tests here use unique,
randomly-generated addresses per test to avoid collisions with permanent
rows (EmailVerification/EmailBounceSuppression) committed by earlier runs.
"""
import uuid

import pytest

import app.services.email as email_module
from app.core.circuit_breaker import CircuitBreaker
from app.database import AsyncSessionLocal
from app.services.email import EmailBlockedError, send_native_email
from app.services.email_verification.mock import MockEmailVerificationAdapter
from app.services.email_verification.service import suppress_bounced_email


def _unique_email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    CircuitBreaker.reset_all()
    yield
    CircuitBreaker.reset_all()


@pytest.fixture(autouse=True)
async def _ensure_schema_migrated(test_engine):
    """This file's tests exercise send_native_email's own AsyncSessionLocal
    session directly rather than the db_session fixture, so nothing here
    would otherwise trigger the session-scoped test_engine fixture (which
    applies the Alembic migration chain) - depending on it explicitly
    guarantees the schema exists even when this file runs in isolation."""
    yield


@pytest.fixture(autouse=True)
def _use_mock_verification(monkeypatch):
    """Deterministic, no real DNS lookups - this file tests the send-gating
    logic, not the verification adapter itself (see
    test_email_verification_adapters.py for that)."""
    monkeypatch.setattr(
        "app.services.email_verification.service.get_email_verification_adapter",
        lambda: MockEmailVerificationAdapter(),
    )


async def test_send_is_blocked_for_a_bounce_suppressed_address():
    # send_native_email opens its own AsyncSessionLocal session rather than
    # taking one as a parameter, so suppression must be seeded through a
    # real, separately-committed session (not the rollback-per-test
    # db_session fixture, which lives on an isolated connection/transaction
    # that a second connection can't see uncommitted writes from).
    email = _unique_email()
    async with AsyncSessionLocal() as db:
        await suppress_bounced_email(db, email, reason="email.bounced")

    with pytest.raises(EmailBlockedError):
        await send_native_email(email, "subject", "body")


async def test_send_is_blocked_for_a_verification_denylisted_address():
    with pytest.raises(EmailBlockedError):
        await send_native_email("someone@bounced.test", "subject", "body")


async def test_send_succeeds_for_a_valid_address_and_records_success_on_the_circuit(monkeypatch):
    monkeypatch.setattr(
        email_module.resend.Emails, "send", lambda payload: {"id": "msg_123"}
    )

    result = await send_native_email(_unique_email(), "subject", "body")

    assert result == {"status": "sent", "message_id": "msg_123"}
    assert CircuitBreaker.get_status("RESEND")["consecutive_failures"] == 0


async def test_send_records_a_failure_on_the_circuit_when_resend_raises(monkeypatch):
    def _boom(payload):
        raise RuntimeError("Resend 500")

    monkeypatch.setattr(email_module.resend.Emails, "send", _boom)

    with pytest.raises(RuntimeError):
        await send_native_email(_unique_email(), "subject", "body")

    assert CircuitBreaker.get_status("RESEND")["consecutive_failures"] == 1


async def test_send_refuses_to_call_resend_at_all_once_the_circuit_is_open(monkeypatch):
    calls = []
    monkeypatch.setattr(
        email_module.resend.Emails, "send", lambda payload: calls.append(payload) or {"id": "should_not_happen"}
    )
    CircuitBreaker.configure("RESEND", failure_threshold=1)
    CircuitBreaker.record_failure("RESEND")  # circuit now OPEN

    from app.core.circuit_breaker import CircuitOpenError

    with pytest.raises(CircuitOpenError):
        await send_native_email(_unique_email(), "subject", "body")

    assert calls == []  # Resend was never actually invoked
