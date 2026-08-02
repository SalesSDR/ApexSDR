from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import Prospect, ProspectState
from app.services.decision.engine import DecisionEngine


@pytest.mark.asyncio
async def test_database_transient_failure_recovery():
    """
    Simulates a transient DB failure during a decision engine run.
    Validates that the exception bubbles up safely so ARQ can retry.

    decide_and_record()'s first DB call is
    ConversationMemoryService.get_active_context(), which does
    `await db.execute(query)` then `.scalars().all()` on the (synchronous)
    Result - not `db.scalar()`. The original version of this test mocked
    `db.scalar` (never actually called) and left `db.execute` as an
    auto-specced AsyncMock, whose return value is *also* an AsyncMock -
    calling `.scalars()` on that returns an unawaited coroutine, and
    `.all()` on a coroutine is where the test actually blew up (not on the
    intended "DB connection dropped" exception at all). Mocking `execute`
    directly exercises the real failure path this test claims to cover.
    """
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute = AsyncMock(side_effect=Exception("DB connection dropped"))

    prospect = Prospect(id="test_p", tenant_id="tenant_x", current_state=ProspectState.NEW, status=ProspectState.NEW)
    engine = DecisionEngine()

    with pytest.raises(Exception, match="DB connection dropped"):
        await engine.decide_and_record(mock_db, prospect)

@pytest.mark.asyncio
@patch("app.services.voice_ai.production.ProductionVoiceAIProvider.generate_response")
async def test_llm_provider_outage_simulation(mock_generate):
    """
    Simulates an LLM provider returning a 503 during a Voice AI webhook.

    VoiceOrchestrator.process_turn has no try/except around
    provider.generate_response(), and neither does either of its callers in
    api/v1/voice.py - an LLM outage propagates as a raised exception (which
    FastAPI turns into a 500 for the webhook caller/Twilio to retry) rather
    than a silently-swallowed fallback response. This test simulates the
    outage and confirms that real, current behavior - a graceful in-process
    fallback was never implemented here (Voice AI is out of scope to add
    one), so asserting otherwise was testing behavior that doesn't exist.

    The original version of this test also had its own mock bug independent
    of that: it only patched get_or_create_transcript, leaving `transcript`
    an unconfigured AsyncMock - `transcript.total_turns` was then itself an
    AsyncMock, not a real int, so `should_terminate()`'s `>=` comparison
    raised a TypeError before the outage simulation ever ran.
    """
    mock_generate.side_effect = Exception("503 Service Unavailable: Gemini API down")

    from app.services.voice_ai.orchestrator import VoiceOrchestrator

    mock_db = AsyncMock()
    prospect = Prospect(id="test_p", first_name="Test", company_name="Acme")

    # created_at must be a real datetime - ConversationManager's max-duration
    # check (Sprint 7) subtracts it from datetime.now(), which a bare
    # MagicMock attribute can't support.
    fake_transcript = MagicMock(id="transcript_1", total_turns=1, created_at=datetime.now(UTC))

    with patch(
        "app.services.voice_ai.transcript.TranscriptService.get_or_create_transcript",
        new=AsyncMock(return_value=fake_transcript),
    ), patch(
        "app.services.voice_ai.transcript.TranscriptService.get_recent_history",
        new=AsyncMock(return_value=[]),
    ), patch(
        # Sprint 7: process_turn now also builds rich (qualification/signals/
        # enrichment) context via PersonalizationService, which would
        # otherwise run real queries against the bare mock_db above.
        "app.services.personalization.PersonalizationService.build_context",
        new=AsyncMock(return_value={}),
    ):
        with pytest.raises(Exception, match="503 Service Unavailable"):
            await VoiceOrchestrator.process_turn(mock_db, prospect, "call-x", "Hello?")

@pytest.mark.asyncio
async def test_hubspot_crm_outage_resilience():
    """
    Simulates HubSpot being down during a sync operation.
    Validates it logs failure but doesn't crash the pipeline task.
    """
    from app.workers.tasks import sync_crm_safely
    
    mock_crm = AsyncMock()
    mock_crm.sync_status.side_effect = Exception("HubSpot API timeout")
    
    prospect = Prospect(id="test_p", tenant_id="tenant_x")
    
    # Should not raise exception
    await sync_crm_safely(mock_crm, prospect, "test_p")

@pytest.mark.asyncio
async def test_google_calendar_outage_resilience():
    """
    Simulates Google Calendar API outage during a meeting reschedule.
    Should fail gracefully and increment calendar_sync_failures_total.
    """
    from datetime import datetime

    from app.workers.tasks import reschedule_calendar_meeting_task
    
    mock_calendar = AsyncMock()
    mock_calendar.book_or_update_meeting.side_effect = Exception("Google Calendar 503")
    
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = Prospect(id="test_p", first_name="A", last_name="B")
    
    ctx = {
        'sessionmaker': lambda: AsyncMock(__aenter__=AsyncMock(return_value=mock_db), __aexit__=AsyncMock()),
        'calendar_service': mock_calendar
    }
    
    # The task should catch the exception, log it, increment metric, and return safely
    await reschedule_calendar_meeting_task(ctx, "test_p", datetime.now(UTC), datetime.now(UTC))
