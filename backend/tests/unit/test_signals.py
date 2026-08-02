from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import BuyingSignal, MemoryType, Prospect, SignalStrength, SignalType
from app.services.memory.service import ConversationMemoryService
from app.services.signals.engine import BuyingSignalEngine


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db

@pytest.fixture
def mock_prospect():
    p = Prospect(
        id="test_prospect_id",
        tenant_id="test_tenant_id",
        first_name="Test",
        last_name="User",
        email="test@example.com"
    )
    return p

@pytest.mark.asyncio
async def test_buying_signal_expiration_calc():
    engine = BuyingSignalEngine()
    
    # JOB_CHANGE -> 90 days
    exp1 = engine._calculate_expiration(SignalType.JOB_CHANGE)
    assert (exp1 - datetime.now(UTC)).days in (89, 90)
    
    # WEBSITE_VISIT -> 7 days
    exp2 = engine._calculate_expiration(SignalType.WEBSITE_VISIT)
    assert (exp2 - datetime.now(UTC)).days in (6, 7)

@pytest.mark.asyncio
async def test_process_single_signal(mock_db, mock_prospect, monkeypatch):
    # Mock ConversationMemoryService.add_memory
    add_memory_mock = AsyncMock()
    monkeypatch.setattr(ConversationMemoryService, "add_memory", add_memory_mock)

    engine = BuyingSignalEngine()
    
    # Mock deduplication to return nothing (no existing signal)
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_execute)

    raw_signal = {
        "signal_type": SignalType.COMPANY_HIRING,
        "signal_source": "NEWS_API",
        "signal_strength": SignalStrength.HIGH,
        "summary": "Company is hiring",
    }
    
    await engine._process_single_signal(mock_db, mock_prospect, raw_signal)
    
    # Verify BuyingSignal was added
    assert mock_db.add.called
    added_obj = mock_db.add.call_args[0][0]
    assert isinstance(added_obj, BuyingSignal)
    assert added_obj.signal_type == SignalType.COMPANY_HIRING
    assert added_obj.is_active is True

    # Verify ConversationMemory was added
    assert add_memory_mock.called
    kwargs = add_memory_mock.call_args[1]
    assert kwargs["memory_type"] == MemoryType.BUYING_SIGNAL
    assert kwargs["importance_score"] == 8
    assert kwargs["is_resolved"] is False

@pytest.mark.asyncio
async def test_expire_old_signals(mock_db):
    engine = BuyingSignalEngine()
    
    # Mock the update query result
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = ["signal_1", "signal_2"]
    
    # Needs AsyncMock for db.execute
    async_execute = AsyncMock(return_value=mock_result)
    mock_db.execute = async_execute
    
    expired = await engine.expire_old_signals(mock_db)
    
    assert expired == 2
    assert mock_db.commit.called
