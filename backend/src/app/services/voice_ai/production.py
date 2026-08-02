import json
import logging

import google.generativeai as genai

from app.config import settings
from app.services.voice_ai.base import BaseVoiceAIProvider
from app.services.voice_ai.conversation import (
    ConversationContext,
    ConversationManager,
    VoiceResponse,
)
from app.services.voice_ai.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class ProductionVoiceAIProvider(BaseVoiceAIProvider):
    """Real Gemini-backed voice AI provider. Returns ONLY the structured
    VoiceResponse shape - never executes business logic, never touches
    Prospect state (see conversation.py's VoiceResponse docstring)."""

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)

    async def generate_response(self, context: ConversationContext, user_speech: str) -> VoiceResponse:
        system_prompt = PromptBuilder.build_system_prompt()
        user_prompt = PromptBuilder.build_user_prompt(context, user_speech)

        try:
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            response = model.generate_content(user_prompt)
            data = json.loads(response.text)
            return VoiceResponse(**data)
        except Exception as e:
            logger.error(f"Voice AI generation failed, falling back: {e}")
            return ConversationManager.get_fallback_response("error")
