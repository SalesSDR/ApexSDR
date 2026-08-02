import logging

import httpx

from app.config import settings
from app.services.linkedin.base import LinkedInAdapter
from app.services.linkedin.mock import MockLinkedInAdapter
from app.services.linkedin.production import ProductionLinkedInAdapter

logger = logging.getLogger(__name__)


def get_linkedin_adapter(http_client: httpx.AsyncClient) -> LinkedInAdapter:
    """Single switch point, same rule as every other adapter factory
    (Sprint 7.1): USE_MOCK_CLIENTS is the ONE thing that decides mock vs.
    production - never credential presence."""
    if settings.USE_MOCK_CLIENTS:
        logger.info("LinkedIn adapter: USE_MOCK_CLIENTS=true, using MockLinkedInAdapter.")
        return MockLinkedInAdapter()
    logger.info("LinkedIn adapter: using ProductionLinkedInAdapter.")
    return ProductionLinkedInAdapter(
        api_key=settings.UNIPILE_API_KEY,
        base_url=settings.UNIPILE_BASE_URL,
        http_client=http_client,
    )
