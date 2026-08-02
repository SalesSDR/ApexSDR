import logging

from app.models.schemas import Prospect

logger = logging.getLogger(__name__)

class BaseSignalProvider:
    """
    Abstract base adapter for fetching buying signals from external systems.
    Subclasses should implement fetch_signals.
    """
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def fetch_signals(self, prospect: Prospect) -> list[dict]:
        """
        Fetch new signals for a prospect.
        Returns a list of dicts that can be loaded into BuyingSignalCreate schemas.
        """
        raise NotImplementedError("Subclasses must implement fetch_signals")
