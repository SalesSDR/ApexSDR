from collections.abc import Callable

from app.services.compliance.base import BaseComplianceProvider
from app.services.compliance.policy import check_business_hours, check_do_not_contact


class MockComplianceProvider(BaseComplianceProvider):
    """Fixed, deterministic policy set for testing/dev - always DNC then
    business hours, regardless of settings.COMPLIANCE_ENABLED_POLICIES -
    so pipeline tests get predictable behavior independent of environment
    configuration. validate() itself is inherited unchanged from
    BaseComplianceProvider; only the policy list differs from Production."""

    def _default_policies(self) -> list[Callable]:
        return [check_do_not_contact, check_business_hours]
