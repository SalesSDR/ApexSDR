"""Sprint 7: VoiceOrchestrator end-to-end against a real DB session (no
mocked ORM calls) - covers the full per-turn pipeline: Conversation Manager
limits -> LLM -> transcript/memory persistence -> Decision Engine -> state
transition. Voice AI (the mock LLM provider) never touches Prospect state
directly - only VoiceOrchestrator._apply_decision does, and only by
translating the Decision Engine's own Decision."""
import uuid

from sqlalchemy import select

from app.config import settings
from app.models.schemas import (
    CallTranscript,
    ConversationMemory,
    DecisionLog,
    MemoryType,
    Prospect,
    ProspectState,
)
from app.services.voice_ai.orchestrator import VoiceOrchestrator


def _make_prospect(**overrides) -> Prospect:
    defaults = dict(
        id=str(uuid.uuid4()), tenant_id="tenant_voice", first_name="Jordan", last_name="Prospect", company_name="Acme Co",
        linkedin_url="https://linkedin.com/in/jordan-voice", phone_number="+15551234567",
        status=ProspectState.CALL_CONNECTED,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


async def test_meeting_request_books_a_meeting_and_ends_the_call(db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = _make_prospect()
    db_session.add(prospect)
    await db_session.flush()

    turn = await VoiceOrchestrator.process_turn(db_session, prospect, "call-book-meeting", "Yes, let's book a demo.")

    assert turn.call_ended is True
    assert turn.voice_response.next_action == "BOOK_MEETING"
    assert prospect.status == ProspectState.MEETING_BOOKED

    memories = (await db_session.execute(
        select(ConversationMemory).where(ConversationMemory.prospect_id == prospect.id)
    )).scalars().all()
    signal_memories = [m for m in memories if m.memory_type == MemoryType.BUYING_SIGNAL]
    assert len(signal_memories) == 1
    assert signal_memories[0].metadata_["signal_type"] == "MEETING_REQUEST"

    logs = (await db_session.execute(
        select(DecisionLog).where(DecisionLog.prospect_id == prospect.id)
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].decision_type.value == "BOOK_MEETING"


async def test_objection_continues_the_call_and_records_memory(db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = _make_prospect()
    db_session.add(prospect)
    await db_session.flush()

    turn = await VoiceOrchestrator.process_turn(db_session, prospect, "call-objection", "That's too expensive for our budget.")

    assert turn.call_ended is False
    assert turn.voice_response.next_action == "CONTINUE"
    assert prospect.status == ProspectState.CALL_CONNECTED  # untouched - CONTINUE never transitions

    memories = (await db_session.execute(
        select(ConversationMemory).where(ConversationMemory.prospect_id == prospect.id)
    )).scalars().all()
    assert any(m.memory_type == MemoryType.OBJECTION for m in memories)


async def test_not_interested_closes_the_call(db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = _make_prospect()
    db_session.add(prospect)
    await db_session.flush()

    turn = await VoiceOrchestrator.process_turn(db_session, prospect, "call-not-interested", "I'm not interested, please stop calling.")

    assert turn.call_ended is True
    assert turn.voice_response.next_action == "CLOSE"
    assert prospect.status == ProspectState.COMPLETED_DECLINED


async def test_first_turn_with_no_speech_is_a_greeting_not_silence(db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = _make_prospect()
    db_session.add(prospect)
    await db_session.flush()

    turn = await VoiceOrchestrator.process_turn(db_session, prospect, "call-greeting", "")

    assert turn.voice_response.intent == "GREETING"
    assert turn.call_ended is False
    assert prospect.status == ProspectState.CALL_CONNECTED


async def test_consecutive_silence_eventually_retries_the_call(db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = _make_prospect()
    db_session.add(prospect)
    await db_session.flush()

    # Turn 1: real speech, so total_turns > 0 afterwards.
    await VoiceOrchestrator.process_turn(db_session, prospect, "call-silence", "hi there")
    assert prospect.status == ProspectState.CALL_CONNECTED

    # Turn 2: silence -> reprompt, call continues.
    turn2 = await VoiceOrchestrator.process_turn(db_session, prospect, "call-silence", "")
    assert turn2.call_ended is False
    assert turn2.voice_response.intent == "SILENCE"
    assert prospect.status == ProspectState.CALL_CONNECTED

    # Turn 3: second consecutive silence -> terminate with a retry outcome.
    turn3 = await VoiceOrchestrator.process_turn(db_session, prospect, "call-silence", "")
    assert turn3.call_ended is True
    assert turn3.voice_response.next_action == "RETRY"
    assert prospect.status == ProspectState.CALL_QUEUED
    assert prospect.next_action_at is not None


async def test_max_turns_terminates_the_call(db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = _make_prospect()
    db_session.add(prospect)
    await db_session.flush()
    transcript = CallTranscript(
        prospect_id=prospect.id, tenant_id=prospect.tenant_id, call_sid="call-max-turns",
        total_turns=15, status="IN_PROGRESS",
    )
    db_session.add(transcript)
    await db_session.flush()

    turn = await VoiceOrchestrator.process_turn(db_session, prospect, "call-max-turns", "still talking")

    assert turn.call_ended is True
    assert turn.voice_response.intent == "TERMINATE"
    assert prospect.status == ProspectState.COMPLETED_DECLINED
    assert transcript.status == "COMPLETED"
