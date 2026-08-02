from app.config import settings
from app.services.email_verification.base import EmailVerificationAdapter
from app.services.email_verification.mock import MockEmailVerificationAdapter
from app.services.email_verification.production import (
    ProductionEmailVerificationAdapter,
)


def get_email_verification_adapter() -> EmailVerificationAdapter:
    if settings.USE_MOCK_CLIENTS:
        return MockEmailVerificationAdapter()
    return ProductionEmailVerificationAdapter()
