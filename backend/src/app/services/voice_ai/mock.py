from app.services.voice_ai.base import BaseVoiceAIProvider
from app.services.voice_ai.conversation import ConversationContext, VoiceResponse


class MockVoiceAIProvider(BaseVoiceAIProvider):
    """Deterministic, keyword-driven responses - no Gemini call, no network
    access. Covers every next_action the real provider can return so mock
    mode exercises the full Decision Engine / state-machine pipeline."""

    async def generate_response(self, context: ConversationContext, user_speech: str) -> VoiceResponse:
        if not user_speech or not user_speech.strip():
            return VoiceResponse(
                spoken_response=f"Hi {context.prospect_name}, this is Alex from ApexSDR - do you have a quick minute?",
                intent="GREETING",
                confidence=1.0,
                summary="Call opened; greeted the prospect.",
                next_action="CONTINUE",
            )

        speech_lower = user_speech.lower()

        if "not interested" in speech_lower or "stop calling" in speech_lower:
            return VoiceResponse(
                spoken_response="No problem. Thanks for your time, have a great day.",
                intent="NOT_INTERESTED",
                confidence=0.9,
                summary="Prospect said they are not interested.",
                next_action="CLOSE",
            )
        if "call me back" in speech_lower or "not a good time" in speech_lower or "busy right now" in speech_lower:
            return VoiceResponse(
                spoken_response="No worries at all, I'll follow up with you another time. Take care!",
                intent="PREFERENCE",
                confidence=0.9,
                summary="Prospect asked to be contacted at a later time.",
                next_action="PAUSE",
            )
        if "book" in speech_lower or "meeting" in speech_lower or "demo" in speech_lower or "yes" in speech_lower:
            return VoiceResponse(
                spoken_response="Great, I'll send over a calendar invite for a quick demo.",
                intent="MEETING_REQUEST",
                confidence=0.9,
                summary="Prospect agreed to book a meeting/demo.",
                next_action="BOOK_MEETING",
            )
        if "complaint" in speech_lower or "lawsuit" in speech_lower or "lawyer" in speech_lower or "manager" in speech_lower:
            return VoiceResponse(
                spoken_response="I completely understand - let me get a member of our team to follow up with you directly on that.",
                intent="ESCALATION",
                confidence=0.9,
                summary="Prospect raised an issue requiring human escalation.",
                next_action="HUMAN_REVIEW",
            )
        if "too expensive" in speech_lower or "price" in speech_lower or "budget" in speech_lower:
            return VoiceResponse(
                spoken_response="I hear you on budget - a lot of our customers felt the same before seeing the ROI. Can I share a bit more?",
                intent="OBJECTION",
                confidence=0.85,
                summary="Prospect raised a pricing objection.",
                next_action="CONTINUE",
            )

        return VoiceResponse(
            spoken_response="I hear you. Tell me more about that.",
            intent="NEUTRAL",
            confidence=0.8,
            summary="Prospect made a neutral/unclear statement.",
            next_action="CONTINUE",
        )
