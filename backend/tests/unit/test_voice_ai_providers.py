"""Sprint 7: intent/mock-provider tests - the mock provider must cover every
next_action the real provider can return (Decision Engine relies on the
mock pipeline being able to reach BOOK_MEETING/HUMAN_REVIEW/PAUSE/CLOSE just
like production, not only the happy CONTINUE path)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.voice_ai.conversation import ConversationContext, VoiceResponse
from app.services.voice_ai.mock import MockVoiceAIProvider
from app.services.voice_ai.production import ProductionVoiceAIProvider


def _context(**overrides) -> ConversationContext:
    defaults = dict(
        prospect_name="Jordan",
        company_name="Acme Co",
        current_state="QUALIFYING",
        recent_history=[],
    )
    defaults.update(overrides)
    return ConversationContext(**defaults)


@pytest.fixture
def provider():
    return MockVoiceAIProvider()


async def test_empty_speech_is_a_greeting(provider):
    response = await provider.generate_response(_context(), "")
    assert response.intent == "GREETING"
    assert response.next_action == "CONTINUE"
    assert "Jordan" not in "" and "Jordan" in response.spoken_response


async def test_not_interested_closes(provider):
    response = await provider.generate_response(_context(), "I'm really not interested, thanks.")
    assert response.intent == "NOT_INTERESTED"
    assert response.next_action == "CLOSE"


async def test_call_back_later_pauses(provider):
    response = await provider.generate_response(_context(), "Can you call me back another time, not a good time.")
    assert response.intent == "PREFERENCE"
    assert response.next_action == "PAUSE"


async def test_agreeing_to_a_demo_books_a_meeting(provider):
    response = await provider.generate_response(_context(), "Yes, let's book a demo.")
    assert response.intent == "MEETING_REQUEST"
    assert response.next_action == "BOOK_MEETING"


async def test_escalation_language_requests_human_review(provider):
    response = await provider.generate_response(_context(), "I want to speak to your manager about a complaint.")
    assert response.intent == "ESCALATION"
    assert response.next_action == "HUMAN_REVIEW"


async def test_pricing_objection_continues(provider):
    response = await provider.generate_response(_context(), "That sounds too expensive for our budget.")
    assert response.intent == "OBJECTION"
    assert response.next_action == "CONTINUE"


async def test_neutral_speech_continues(provider):
    response = await provider.generate_response(_context(), "Tell me more about your product.")
    assert response.intent == "NEUTRAL"
    assert response.next_action == "CONTINUE"


async def test_confidence_is_always_a_valid_probability(provider):
    for speech in ("", "not interested", "book a demo", "too expensive", "random text"):
        response = await provider.generate_response(_context(), speech)
        assert 0.0 <= response.confidence <= 1.0


# --- Production provider: Gemini call is mocked, only request/response shape is under test ---

async def test_production_provider_parses_valid_gemini_json(monkeypatch):
    monkeypatch.setattr("app.services.voice_ai.production.settings.GEMINI_API_KEY", "fake-key")
    fake_model = MagicMock()
    fake_model.generate_content.return_value = MagicMock(text=json.dumps({
        "spoken_response": "Great, let's get that scheduled.",
        "intent": "MEETING_REQUEST",
        "confidence": 0.95,
        "summary": "Prospect agreed to a demo.",
        "next_action": "BOOK_MEETING",
    }))

    with patch("app.services.voice_ai.production.genai.configure"):
        with patch("app.services.voice_ai.production.genai.GenerativeModel", return_value=fake_model):
            provider = ProductionVoiceAIProvider()
            response = await provider.generate_response(_context(), "Yes let's do it")

    assert isinstance(response, VoiceResponse)
    assert response.next_action == "BOOK_MEETING"
    assert response.confidence == 0.95


async def test_production_provider_falls_back_on_malformed_gemini_output(monkeypatch):
    monkeypatch.setattr("app.services.voice_ai.production.settings.GEMINI_API_KEY", "fake-key")
    fake_model = MagicMock()
    fake_model.generate_content.return_value = MagicMock(text="not valid json at all")

    with patch("app.services.voice_ai.production.genai.configure"):
        with patch("app.services.voice_ai.production.genai.GenerativeModel", return_value=fake_model):
            provider = ProductionVoiceAIProvider()
            response = await provider.generate_response(_context(), "garbled audio")

    # Falls back to ConversationManager.get_fallback_response("error") -
    # never raises, never leaves the call in an undefined state.
    assert response.next_action == "RETRY"
    assert response.intent == "TERMINATE"
