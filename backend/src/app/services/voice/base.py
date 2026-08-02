from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CallResult:
    sid: str
    status: str


class VoiceAdapter(ABC):
    """Interface for placing outbound voice calls. Implementations must raise
    on failure rather than swallow errors, since callers rely on exceptions
    to drive retry/dev_mode handling."""

    @abstractmethod
    async def initiate_call(self, to_number: str, twimlet_url: str) -> CallResult:
        raise NotImplementedError
