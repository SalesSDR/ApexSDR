from abc import ABC, abstractmethod

from app.services.voice_ai.conversation import ConversationContext, VoiceResponse


class BaseVoiceAIProvider(ABC):
    @abstractmethod
    async def generate_response(self, context: ConversationContext, user_speech: str) -> VoiceResponse:
        pass
