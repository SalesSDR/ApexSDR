from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import (
    EmailBounceSuppression,
    EmailVerification,
    EmailVerificationStatus,
)
from app.services.email_verification.factory import get_email_verification_adapter


async def is_bounce_suppressed(db: AsyncSession, email: str) -> bool:
    row = (
        await db.execute(select(EmailBounceSuppression).where(EmailBounceSuppression.email == email))
    ).scalar_one_or_none()
    return row is not None


async def suppress_bounced_email(db: AsyncSession, email: str, reason: str) -> None:
    """Idempotent: a second bounce for an already-suppressed address is a
    no-op rather than a duplicate-key error."""
    existing = (
        await db.execute(select(EmailBounceSuppression).where(EmailBounceSuppression.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(EmailBounceSuppression(email=email, reason=reason))
    await db.commit()


async def ensure_verified(db: AsyncSession, email: str) -> EmailVerification:
    """Verifies `email` before its first send and caches the result - a
    later call for the same address reuses the stored row instead of
    re-querying the provider."""
    existing = (
        await db.execute(select(EmailVerification).where(EmailVerification.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    adapter = get_email_verification_adapter()
    result = await adapter.verify(email)
    record = EmailVerification(
        email=email,
        status=result.status,
        reason=result.reason,
        provider=type(adapter).__name__,
        checked_at=datetime.now(UTC),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


__all__ = [
    "EmailVerificationStatus",
    "ensure_verified",
    "is_bounce_suppressed",
    "suppress_bounced_email",
]
