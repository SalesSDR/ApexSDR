"""Sprint 7: DecisionEngine.decide_for_voice_turn is the ONLY authority that
turns a voice conversation turn into an actionable Decision - Voice AI's
next_action is a suggestion, never a command. Pure/no I/O, mirroring
decide_qualification()'s narrow-decision-point pattern."""
import pytest

from app.models.schemas import DecisionType, Prospect, ProspectState
from app.services.decision.engine import DecisionEngine


@pytest.fixture
def prospect():
    return Prospect(
        id="p1", tenant_id="tenant_1", first_name="Jordan",
        linkedin_url="https://linkedin.com/in/jordan", status=ProspectState.CALL_CONNECTED,
    )


@pytest.fixture
def engine():
    return DecisionEngine()


def test_continue_maps_to_wait(engine, prospect):
    decision = engine.decide_for_voice_turn(prospect, "CONTINUE", "NEUTRAL", 0.8)
    assert decision.decision_type == DecisionType.WAIT


def test_retry_maps_to_retry_later(engine, prospect):
    decision = engine.decide_for_voice_turn(prospect, "RETRY", "SILENCE", 1.0)
    assert decision.decision_type == DecisionType.RETRY_LATER


def test_book_meeting_at_high_confidence_is_authorized(engine, prospect):
    decision = engine.decide_for_voice_turn(prospect, "BOOK_MEETING", "MEETING_REQUEST", 0.9)
    assert decision.decision_type == DecisionType.BOOK_MEETING
    assert decision.task_to_enqueue == "book_calendar_meeting_task"


def test_book_meeting_at_low_confidence_is_escalated_instead(engine, prospect):
    """Sprint 7: Decision Engine is the authority, not a rubber stamp - a
    shaky meeting-request detection doesn't auto-book."""
    decision = engine.decide_for_voice_turn(prospect, "BOOK_MEETING", "MEETING_REQUEST", 0.3)
    assert decision.decision_type == DecisionType.HUMAN_REVIEW
    assert decision.task_to_enqueue is None


def test_human_review_maps_regardless_of_confidence(engine, prospect):
    decision = engine.decide_for_voice_turn(prospect, "HUMAN_REVIEW", "ESCALATION", 0.4)
    assert decision.decision_type == DecisionType.HUMAN_REVIEW


def test_pause_maps_to_pause(engine, prospect):
    decision = engine.decide_for_voice_turn(prospect, "PAUSE", "PREFERENCE", 0.9)
    assert decision.decision_type == DecisionType.PAUSE
    assert decision.task_to_enqueue is None


def test_close_maps_to_end_sequence(engine, prospect):
    decision = engine.decide_for_voice_turn(prospect, "CLOSE", "NOT_INTERESTED", 0.9)
    assert decision.decision_type == DecisionType.END_SEQUENCE


def test_unrecognized_next_action_fails_safe_to_wait(engine, prospect):
    decision = engine.decide_for_voice_turn(prospect, "SOMETHING_MADE_UP", "NEUTRAL", 0.9)
    assert decision.decision_type == DecisionType.WAIT


def test_never_mutates_the_prospect(engine, prospect):
    original_status = prospect.status
    engine.decide_for_voice_turn(prospect, "BOOK_MEETING", "MEETING_REQUEST", 0.95)
    assert prospect.status == original_status
