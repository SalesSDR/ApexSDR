"""Sprint 7: ConversationManager owns every conversational LIMIT (turns,
duration, silence) deterministically, before any LLM call happens."""
from datetime import UTC, datetime, timedelta

from app.services.voice_ai.conversation import ConversationManager


def test_should_terminate_for_turns_at_the_limit():
    assert ConversationManager.should_terminate_for_turns(ConversationManager.MAX_TURNS) is True


def test_should_not_terminate_for_turns_below_the_limit():
    assert ConversationManager.should_terminate_for_turns(ConversationManager.MAX_TURNS - 1) is False


def test_should_terminate_for_duration_once_max_duration_elapsed():
    started_at = datetime.now(UTC) - timedelta(seconds=ConversationManager.MAX_DURATION_SECONDS + 5)
    assert ConversationManager.should_terminate_for_duration(started_at) is True


def test_should_not_terminate_for_duration_within_limit():
    started_at = datetime.now(UTC) - timedelta(seconds=10)
    assert ConversationManager.should_terminate_for_duration(started_at) is False


def test_is_silence_true_for_empty_or_whitespace():
    assert ConversationManager.is_silence("") is True
    assert ConversationManager.is_silence("   ") is True
    assert ConversationManager.is_silence(None) is True


def test_is_silence_false_for_real_speech():
    assert ConversationManager.is_silence("hello there") is False


def test_should_terminate_for_silence_at_the_limit():
    assert ConversationManager.should_terminate_for_silence(ConversationManager.MAX_CONSECUTIVE_SILENCES) is True
    assert ConversationManager.should_terminate_for_silence(ConversationManager.MAX_CONSECUTIVE_SILENCES - 1) is False


def test_get_reprompt_response_continues_the_call():
    response = ConversationManager.get_reprompt_response()
    assert response.next_action == "CONTINUE"
    assert response.intent == "SILENCE"


def test_get_fallback_response_max_turns_closes():
    response = ConversationManager.get_fallback_response("max_turns")
    assert response.next_action == "CLOSE"
    assert response.intent == "TERMINATE"


def test_get_fallback_response_max_duration_closes():
    response = ConversationManager.get_fallback_response("max_duration")
    assert response.next_action == "CLOSE"


def test_get_fallback_response_silence_retries():
    response = ConversationManager.get_fallback_response("silence")
    assert response.next_action == "RETRY"


def test_get_fallback_response_unknown_reason_retries():
    response = ConversationManager.get_fallback_response("some_unexpected_error")
    assert response.next_action == "RETRY"
