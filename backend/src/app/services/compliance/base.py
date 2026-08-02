from collections.abc import Callable
from dataclasses import dataclass

from app.models.schemas import CompliancePolicyType, DecisionType, PolicySeverity, Prospect


@dataclass
class ComplianceCheck:
    """Result of a policy evaluation."""
    is_allowed: bool
    policy_type: CompliancePolicyType | None = None
    severity: PolicySeverity | None = None
    reason: str | None = None
    metadata_: dict | None = None

class BaseComplianceProvider:
    """Abstract base adapter for the Compliance Engine. validate() itself is
    concrete and shared by every subclass - a generic first-match-wins loop
    over self.policies - so Mock and Production never duplicate that
    control-flow; only _default_policies() (which policies run, and in
    what order) differs between them."""

    def __init__(self, tenant_id: str, policies: list[Callable] | None = None):
        self.tenant_id = tenant_id
        self.policies: list[Callable] = policies if policies is not None else self._default_policies()

    def _default_policies(self) -> list[Callable]:
        raise NotImplementedError("Subclasses must implement _default_policies")

    async def validate(self, db_session, prospect: Prospect, proposed_action: DecisionType, prospect_tz: str = "UTC") -> ComplianceCheck:
        for policy_fn in self.policies:
            check = await policy_fn(db_session, prospect, proposed_action, prospect_tz)
            if not check.is_allowed:
                return check
        return ComplianceCheck(is_allowed=True)
