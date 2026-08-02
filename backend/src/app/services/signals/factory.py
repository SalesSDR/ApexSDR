from app.config import settings
from app.services.signals.base import BaseSignalProvider
from app.services.signals.mock import MockSignalProvider
from app.services.signals.production import ProductionSignalProvider


def get_signal_provider(tenant_id: str) -> BaseSignalProvider:
    """
    Returns the appropriate signal provider based on environment config.
    """
    if settings.DEV_MODE:
        return MockSignalProvider(tenant_id)
    return ProductionSignalProvider(tenant_id)
