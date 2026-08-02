import logging

import httpx

from app.config import settings
from app.services.crm.base import CRMAdapter
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.production import ProductionHubSpotAdapter

logger = logging.getLogger(__name__)


def get_crm_adapter(http_client: httpx.AsyncClient) -> CRMAdapter:
    """Single switch point, same rule as every other adapter factory
    (Sprint 7.1): USE_MOCK_CLIENTS is the ONE thing that decides mock vs.
    production - never credential presence. Switching on "is HUBSPOT_API_KEY
    set" meant USE_MOCK_CLIENTS=true could not actually guarantee zero live
    HubSpot calls whenever a real key also happened to be configured (e.g.
    a shared .env used for both modes) - this closes that gap."""
    if settings.USE_MOCK_CLIENTS:
        logger.info("CRM adapter: USE_MOCK_CLIENTS=true, using MockHubSpotAdapter.")
        return MockHubSpotAdapter()
    logger.info("CRM adapter: using ProductionHubSpotAdapter.")
    return ProductionHubSpotAdapter(api_key=settings.HUBSPOT_API_KEY, http_client=http_client)
