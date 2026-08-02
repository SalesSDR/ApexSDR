from datetime import UTC, datetime

from pydantic import BaseModel, Field

# The only next_action values DecisionEngine.decide_for_voice_turn()
# recognizes - anything else it treats as CONTINUE (fail safe). Voice AI
# suggests one of these per turn; DecisionEngine is the actual authority
# that turns it into a Decision (see services/decision/engine.py).
NEXT_ACTION_VALUES = ("CONTINUE", "RETRY", "BOOK_MEETING", "HUMAN_REVIEW", "PAUSE", "CLOSE")


class VoiceResponse(BaseModel):
    """Structured LLM output for a single voice turn - the ONLY thing a
    voice AI provider returns (Sprint 7). spoken_response is the only text
    that ever reaches the prospect (via TTS); everything else is signal for
    Conversation Memory and the Decision Engine. The LLM never changes
    Prospect state - next_action is a suggestion, not a command."""

    spoken_response: str = Field(..., description="The exact text the TTS engine will speak to the prospect.")
    intent: str = Field(
        ..., description="Detected intent of the prospect (e.g. GREETING, OBJECTION, MEETING_REQUEST, NOT_INTERESTED, PREFERENCE, NEUTRAL)."
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0 of the intent classification.")
    summary: str = Field(..., description="One-sentence summary of what the prospect just said, for conversation memory/transcript.")
    next_action: str = Field(..., description=f"One of {NEXT_ACTION_VALUES} - Voice AI's suggestion for what should happen next.")


class ConversationContext(BaseModel):
    prospect_name: str
    company_name: str | None = None
    current_state: str
    recent_history: list[dict]  # [{"speaker": "ASSISTANT", "text": "Hello..."}, ...]

    # Sprint 7, item 4: the same rich context every other outbound channel
    # gets via services/personalization.py, not just name/company.
    qualification_summary: str | None = None
    buying_signals: str | None = None
    company_description: str | None = None
    industry: str | None = None
    recent_news: str | None = None
    conversation_memory: str | None = None


class ConversationManager:
    """Sits between the API layer and the LLM provider: owns every
    conversational LIMIT (turns, duration, silence) so a runaway or dead
    call can't loop forever. These checks are deterministic and run BEFORE
    the LLM is ever consulted - a silent or over-limit call never spends an
    LLM call finding that out."""

    MAX_TURNS = 15
    MAX_DURATION_SECONDS = 600  # 10 minutes wall-clock, measured from CallTranscript.created_at
    MAX_CONSECUTIVE_SILENCES = 2

    @classmethod
    def should_terminate_for_turns(cls, current_turn_count: int) -> bool:
        return current_turn_count >= cls.MAX_TURNS

    @classmethod
    def should_terminate_for_duration(cls, started_at: datetime) -> bool:
        elapsed = (datetime.now(UTC) - started_at).total_seconds()
        return elapsed >= cls.MAX_DURATION_SECONDS

    @classmethod
    def is_silence(cls, user_speech: str | None) -> bool:
        return not user_speech or not user_speech.strip()

    @classmethod
    def should_terminate_for_silence(cls, consecutive_silences: int) -> bool:
        return consecutive_silences >= cls.MAX_CONSECUTIVE_SILENCES

    @classmethod
    def get_reprompt_response(cls) -> VoiceResponse:
        """A single silent turn doesn't end the call - ask once more before
        MAX_CONSECUTIVE_SILENCES triggers should_terminate_for_silence."""
        return VoiceResponse(
            spoken_response="Sorry, I didn't catch that. Could you say that again?",
            intent="SILENCE",
            confidence=1.0,
            summary="No speech detected.",
            next_action="CONTINUE",
        )

    @classmethod
    def get_fallback_response(cls, reason: str = "error") -> VoiceResponse:
        if reason == "max_turns":
            text = "It sounds like we have a lot to discuss. Let me have an account executive follow up with you directly. Have a great day!"
            next_action = "CLOSE"
        elif reason == "max_duration":
            text = "We've covered a lot of ground - let's continue this conversation another time. Have a great day!"
            next_action = "CLOSE"
        elif reason == "silence":
            text = "I'm having trouble hearing you, so I'll let you go for now. Feel free to call back anytime. Goodbye!"
            next_action = "RETRY"
        else:
            text = "I'm having a little trouble hearing you. Let's reconnect later. Goodbye!"
            next_action = "RETRY"

        return VoiceResponse(
            spoken_response=text,
            intent="TERMINATE",
            confidence=1.0,
            summary=f"Conversation ended: {reason}.",
            next_action=next_action,
        )
