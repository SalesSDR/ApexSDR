from app.config import settings
from app.services.compliance.base import BaseComplianceProvider
from app.services.compliance.mock import MockComplianceProvider
from app.services.compliance.production import ProductionComplianceProvider


def get_compliance_provider(tenant_id: str) -> BaseComplianceProvider:
    """Returns the environment-appropriate ComplianceProvider."""
    if settings.USE_MOCK_CLIENTS:
        return MockComplianceProvider(tenant_id=tenant_id)
    return ProductionComplianceProvider(tenant_id=tenant_id)
