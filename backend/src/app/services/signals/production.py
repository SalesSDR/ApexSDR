
from app.models.schemas import Prospect
from app.services.signals.base import BaseSignalProvider


class ProductionSignalProvider(BaseSignalProvider):
    async def fetch_signals(self, prospect: Prospect) -> list[dict]:
        """
        Production stub: Here we would integrate with Clearbit, Apollo, or Proxycurl
        to fetch live signals.
        """
        # For now, it behaves as a pass-through until real vendor APIs are configured.
        return []
