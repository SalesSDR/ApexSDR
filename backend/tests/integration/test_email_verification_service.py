"""Integration coverage for the persistence layer in
app.services.email_verification.service: verification results are cached
(one adapter call per address, ever) and bounce suppression is a permanent,
idempotent record checked ahead of verification."""
import uuid

from app.models.schemas import EmailVerificationStatus
from app.services.email_verification import service as verification_service
from app.services.email_verification.base import VerificationResult


def _unique_email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


class _CountingAdapter:
    def __init__(self, result: VerificationResult):
        self.result = result
        self.call_count = 0

    async def verify(self, email: str) -> VerificationResult:
        self.call_count += 1
        return self.result


async def test_ensure_verified_persists_and_returns_the_adapter_result(db_session, monkeypatch):
    adapter = _CountingAdapter(VerificationResult(EmailVerificationStatus.VALID, "MX records present"))
    monkeypatch.setattr(verification_service, "get_email_verification_adapter", lambda: adapter)

    email = _unique_email()
    record = await verification_service.ensure_verified(db_session, email)

    assert record.status == EmailVerificationStatus.VALID
    assert record.email == email
    assert adapter.call_count == 1


async def test_ensure_verified_only_calls_the_adapter_once_per_address(db_session, monkeypatch):
    adapter = _CountingAdapter(VerificationResult(EmailVerificationStatus.VALID, "ok"))
    monkeypatch.setattr(verification_service, "get_email_verification_adapter", lambda: adapter)

    email = _unique_email()
    await verification_service.ensure_verified(db_session, email)
    await verification_service.ensure_verified(db_session, email)
    await verification_service.ensure_verified(db_session, email)

    assert adapter.call_count == 1  # second/third calls reused the cached row


async def test_bounce_suppression_is_checked_by_email_and_starts_false(db_session):
    email = _unique_email()
    assert await verification_service.is_bounce_suppressed(db_session, email) is False


async def test_suppress_bounced_email_marks_the_address_suppressed(db_session):
    email = _unique_email()
    await verification_service.suppress_bounced_email(db_session, email, reason="email.bounced")
    assert await verification_service.is_bounce_suppressed(db_session, email) is True


async def test_suppress_bounced_email_is_idempotent(db_session):
    email = _unique_email()
    await verification_service.suppress_bounced_email(db_session, email, reason="email.bounced")
    await verification_service.suppress_bounced_email(db_session, email, reason="email.complained")
    assert await verification_service.is_bounce_suppressed(db_session, email) is True
