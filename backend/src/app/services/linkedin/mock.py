import logging
import uuid

from app.services.linkedin.base import LinkedInAdapter

logger = logging.getLogger(__name__)


class MockLinkedInAdapter(LinkedInAdapter):
    """Simulates LinkedIn connection requests/messages. Used whenever a
    Unipile account isn't configured so the outbound pipeline can run
    end-to-end without a real LinkedIn account."""

    async def send_connection_request(self, linkedin_url, account_id, message=None):
        logger.info(f"MOCK LINKEDIN ACTIVE: simulating connection request to {linkedin_url}")
        return {"id": f"mock_invite_{uuid.uuid4().hex}", "status": "sent"}

    async def send_message(self, account_id, provider_id, text):
        logger.info(f"MOCK LINKEDIN ACTIVE: simulating message to {provider_id}")
        return {"id": f"mock_msg_{uuid.uuid4().hex}", "status": "sent"}
