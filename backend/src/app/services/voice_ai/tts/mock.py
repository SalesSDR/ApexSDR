import logging

from app.services.voice_ai.tts.base import BaseTTSProvider, SynthesizedAudio

logger = logging.getLogger(__name__)


class MockTTSProvider(BaseTTSProvider):
    """No network access, no ElevenLabs account needed. Produces no real
    audio - callers must render this via TwiML `<Say>` instead of `<Play>`,
    same as every other mock adapter in this codebase never claiming to
    have done real work it didn't do."""

    async def synthesize(self, text: str) -> SynthesizedAudio:
        logger.info(f"MOCK TTS ACTIVE: not synthesizing audio for '{text[:60]}'")
        return SynthesizedAudio(audio_bytes=None)
