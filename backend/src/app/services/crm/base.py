from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ContactData:
    first_name: str
    last_name: str
    email: str | None
    phone_number: str | None
    company_name: str | None
    linkedin_url: str | None


@dataclass
class CompanyData:
    name: str
    domain: str | None


class CRMAdapter(ABC):
    """Interface for syncing prospect data to an external CRM. Implementations
    should raise only on real I/O failure - CRM sync is a side effect the
    outbound pipeline's own progress must never depend on."""

    @abstractmethod
    async def upsert_contact(self, contact: ContactData, external_id: str | None) -> str:
        """Creates or updates a CRM contact. Returns the CRM's contact ID."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_company(self, company: CompanyData, external_id: str | None) -> str:
        """Creates or updates a CRM company record. Returns the CRM's company ID."""
        raise NotImplementedError

    @abstractmethod
    async def associate_contact_company(self, contact_id: str, company_id: str) -> None:
        """Associates a contact with a company record."""
        raise NotImplementedError

    @abstractmethod
    async def log_note(self, contact_id: str, text: str) -> str:
        """Logs a note/activity entry against a contact. Returns the note's ID."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_deal(self, contact_id: str, deal_id: str | None, deal_name: str, stage: str) -> str:
        """Creates or updates a deal associated with a contact. Returns the deal's ID."""
        raise NotImplementedError

    @abstractmethod
    async def log_meeting(self, contact_id: str, title: str, meeting_time: datetime) -> str:
        """Logs a booked meeting against a contact. Returns the meeting's ID."""
        raise NotImplementedError
