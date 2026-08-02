from collections.abc import Callable

from app.config import settings
from app.services.compliance.base import BaseComplianceProvider
from app.services.compliance.policy import POLICY_REGISTRY, check_business_hours, check_do_not_contact


class ProductionComplianceProvider(BaseComplianceProvider):
    """Loads its enabled policy set from settings.COMPLIANCE_ENABLED_POLICIES
    (a comma-separated list of policy names) instead of a fixed list, so
    ops can enable/disable/reorder policies without a code change - this is
    the actual behavioral difference from MockComplianceProvider's fixed
    set. validate() itself is inherited unchanged from
    BaseComplianceProvider; this class never re-implements that loop."""

    def _default_policies(self) -> list[Callable]:
        names = [n.strip().upper() for n in settings.COMPLIANCE_ENABLED_POLICIES.split(",") if n.strip()]
        resolved = [POLICY_REGISTRY[name] for name in names if name in POLICY_REGISTRY]
        return resolved or [check_do_not_contact, check_business_hours]
