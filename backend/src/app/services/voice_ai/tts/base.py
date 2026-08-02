from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SynthesizedAudio:
    """audio_bytes is None for adapters that don't produce real playable
    audio (the mock provider) - callers must fall back to TwiML `<Say>` in
    that case rather than `<Play>` a nonexistent file."""

    audio_bytes: bytes | None
    content_type: str = "audio/mpeg"


class BaseTTSProvider(ABC):
    """Turns spoken_response text into audio for Twilio to `<Play>` to the
    prospect."""

    @abstractmethod
    async def synthesize(self, text: str) -> SynthesizedAudio:
        raise NotImplementedError
