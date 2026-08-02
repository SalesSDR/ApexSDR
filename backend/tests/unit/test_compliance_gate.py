"""Sprint 7.1: DecisionEngine.apply_compliance_gate is the single shared
choke point every Decision Engine action - autonomous pipeline and live
voice turns alike - passes through before being recorded or acted on."""
from unittest.mock import AsyncMock, patch

from app.models.schemas import (
    CompliancePolicyType,
    DecisionType,
    PolicySeverity,
    Prospect,
    ProspectState,
)
from app.services.compliance.base import ComplianceCheck
from app.services.decision.engine import Decision, DecisionEngine


def _prospect(**overrides) -> Prospect:
    defaults = dict(
        id="p1", tenant_id="tenant_gate", first_name="Jordan",
        linkedin_url="https://linkedin.com/in/jordan-gate", status=ProspectState.CALL_CONNECTED,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


async def test_allowed_decision_passes_through_unchanged():
    prospect = _prospect()
    original = Decision(DecisionType.BOOK_MEETING, "Prospect agreed.", 0.9, task_to_enqueue="book_calendar_meeting_task")

    with patch(
        "app.services.decision.engine.ComplianceEngine.validate",
        new=AsyncMock(return_value=ComplianceCheck(is_allowed=True)),
    ):
        result = await DecisionEngine().apply_compliance_gate(AsyncMock(), prospect, original, cid="call-1")

    assert result is original


async def test_permanently_blocked_decision_is_overridden_to_end_sequence():
    prospect = _prospect()
    original = Decision(DecisionType.SEND_EMAIL, "Would send.", 0.9, task_to_enqueue="execute_sequence_step_task")
    blocked_check = ComplianceCheck(
        is_allowed=False, policy_type=CompliancePolicyType.DO_NOT_CONTACT,
        severity=PolicySeverity.PERMANENT_BLOCK, reason="On the do-not-contact list",
    )

    with patch(
        "app.services.decision.engine.ComplianceEngine.validate", new=AsyncMock(return_value=blocked_check),
    ), patch(
        "app.services.decision.engine.ComplianceEngine.record_violation", new=AsyncMock(),
    ) as mock_record_violation:
        db = AsyncMock()
        result = await DecisionEngine().apply_compliance_gate(db, prospect, original, cid="call-2")

    assert result.decision_type == DecisionType.END_SEQUENCE
    assert "do-not-contact" in result.reason.lower() or "blocked" in result.reason.lower()
    mock_record_violation.assert_called_once()


async def test_temporarily_blocked_decision_is_overridden_to_wait():
    prospect = _prospect()
    original = Decision(DecisionType.SCHEDULE_CALL, "Would call.", 0.8, task_to_enqueue="execute_sequence_step_task")
    blocked_check = ComplianceCheck(
        is_allowed=False, policy_type=CompliancePolicyType.BUSINESS_HOURS,
        severity=PolicySeverity.TEMPORARY_BLOCK, reason="Outside business hours",
    )

    with patch(
        "app.services.decision.engine.ComplianceEngine.validate", new=AsyncMock(return_value=blocked_check),
    ), patch(
        "app.services.decision.engine.ComplianceEngine.record_violation", new=AsyncMock(),
    ):
        db = AsyncMock()
        result = await DecisionEngine().apply_compliance_gate(db, prospect, original, cid="call-3")

    assert result.decision_type == DecisionType.WAIT
