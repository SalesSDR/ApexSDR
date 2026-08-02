import logging
import uuid
from datetime import datetime

from app.services.crm.base import CompanyData, ContactData, CRMAdapter

logger = logging.getLogger(__name__)


class MockHubSpotAdapter(CRMAdapter):
    """Simulates HubSpot sync. Used whenever HUBSPOT_API_KEY is absent so the
    outbound pipeline can run end-to-end without a real HubSpot account."""

    async def upsert_contact(self, contact: ContactData, external_id: str | None) -> str:
        contact_id = external_id or f"mock_contact_{uuid.uuid4().hex[:12]}"
        logger.info(f"MOCK CRM ACTIVE: upserted contact {contact_id} ({contact.first_name} {contact.last_name})")
        return contact_id

    async def upsert_company(self, company: CompanyData, external_id: str | None) -> str:
        company_id = external_id or f"mock_company_{uuid.uuid4().hex[:12]}"
        logger.info(f"MOCK CRM ACTIVE: upserted company {company_id} ({company.name})")
        return company_id

    async def associate_contact_company(self, contact_id: str, company_id: str) -> None:
        logger.info(f"MOCK CRM ACTIVE: associated contact {contact_id} with company {company_id}")

    async def log_note(self, contact_id: str, text: str) -> str:
        note_id = f"mock_note_{uuid.uuid4().hex[:12]}"
        logger.info(f"MOCK CRM ACTIVE: logged note {note_id} on contact {contact_id}: {text[:80]}")
        return note_id

    async def upsert_deal(self, contact_id: str, deal_id: str | None, deal_name: str, stage: str) -> str:
        deal_id = deal_id or f"mock_deal_{uuid.uuid4().hex[:12]}"
        logger.info(f"MOCK CRM ACTIVE: upserted deal {deal_id} ({deal_name}, stage={stage}) for contact {contact_id}")
        return deal_id

    async def log_meeting(self, contact_id: str, title: str, meeting_time: datetime) -> str:
        meeting_id = f"mock_meeting_{uuid.uuid4().hex[:12]}"
        logger.info(f"MOCK CRM ACTIVE: logged meeting {meeting_id} ({title} at {meeting_time}) for contact {contact_id}")
        return meeting_id
