from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import CompliancePolicyType, DecisionType, DoNotContactList, PolicySeverity, Prospect
from app.services.compliance.policy import check_do_not_contact
from app.services.decision.engine import DecisionEngine


@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def mock_prospect():
    return Prospect(
        id="test_prospect",
        tenant_id="tenant_1",
        email="test@example.com",
        phone_number="+1234567890",
        status="IDLE"
    )

@pytest.mark.asyncio
async def test_do_not_contact_email(mock_db, mock_prospect):
    # Mock DNC list containing the prospect's email
    dnc = DoNotContactList(value="test@example.com", type="EMAIL")
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [dnc]
    mock_db.execute = AsyncMock(return_value=mock_result)
    
    check = await check_do_not_contact(mock_db, mock_prospect, DecisionType.SEND_EMAIL)
    assert not check.is_allowed
    assert check.policy_type == CompliancePolicyType.DO_NOT_CONTACT
    assert check.severity == PolicySeverity.PERMANENT_BLOCK

@pytest.mark.asyncio
async def test_do_not_contact_domain(mock_db, mock_prospect):
    # Mock DNC list containing the prospect's domain
    dnc = DoNotContactList(value="example.com", type="DOMAIN")
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [dnc]
    mock_db.execute = AsyncMock(return_value=mock_result)
    
    check = await check_do_not_contact(mock_db, mock_prospect, DecisionType.SEND_EMAIL)
    assert not check.is_allowed
    assert check.policy_type == CompliancePolicyType.DO_NOT_CONTACT

@pytest.mark.asyncio
async def test_decision_engine_compliance_override(mock_db, mock_prospect, monkeypatch):
    # Mock the ComplianceEngine to always block with PERMANENT_BLOCK
    mock_engine = AsyncMock()
    mock_engine.validate.return_value = MagicMock(
        is_allowed=False, 
        severity=PolicySeverity.PERMANENT_BLOCK,
        policy_type=CompliancePolicyType.UNSUBSCRIBE,
        reason="Unsubscribed"
    )
    monkeypatch.setattr("app.services.decision.engine.ComplianceEngine", lambda: mock_engine)
    
    decision_engine = DecisionEngine()
    
    # Mock decide_for_prospect to return SEND_EMAIL
    decision_engine.decide_for_prospect = AsyncMock(return_value=MagicMock(decision_type=DecisionType.SEND_EMAIL, reason=""))
    decision_engine.record_decision = AsyncMock()
    
    final_decision = await decision_engine.decide_and_record(mock_db, mock_prospect)
    
    assert final_decision.decision_type == DecisionType.END_SEQUENCE
    assert "Permanently blocked" in final_decision.reason
