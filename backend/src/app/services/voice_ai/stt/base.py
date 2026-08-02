from abc import ABC, abstractmethod


class BaseSTTProvider(ABC):
    """Turns a recorded prospect utterance into text. Implementations must
    raise on failure rather than return an empty/placeholder string -
    ConversationManager treats a raised exception as "could not transcribe"
    (counted as silence) and an empty string as "the prospect said nothing",
    which are different outcomes and must not be conflated."""

    @abstractmethod
    async def transcribe(self, recording_url: str) -> str:
        raise NotImplementedError
