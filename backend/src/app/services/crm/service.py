import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import CrmSyncLog, CrmSyncStatus, Prospect, ProspectState
from app.services.crm.base import CompanyData, ContactData, CRMAdapter

logger = logging.getLogger(__name__)

# Maps pipeline states worth reflecting as a HubSpot deal stage. Uses HubSpot's
# default pipeline's internal stage names, since Module 1 targets HubSpot Free
# with no assumption of a custom pipeline. Only states with real deal-worthy
# signal are mapped - a deal isn't created for every mid-pipeline status.
DEAL_STAGE_BY_STATE = {
    ProspectState.MEETING_BOOKED: "appointmentscheduled",
    ProspectState.CLOSED_WON: "closedwon",
    ProspectState.COMPLETED_DECLINED: "closedlost",
    ProspectState.UNRESPONSIVE_DEAD: "closedlost",
    ProspectState.LOST: "closedlost",
}


class CRMService:
    """Business-logic layer over a CRMAdapter: decides what prospect data
    becomes a contact/company/note/deal/meeting, the adapter just performs
    the I/O (or simulates it, in Mock mode). Every sync attempt this
    service makes is recorded to CrmSyncLog (success/failure, the
    provider's response or error, and a timestamp) when a `db` session is
    supplied - callers that don't pass one (mostly tests) simply skip
    logging rather than failing."""

    def __init__(self, adapter: CRMAdapter):
        self.adapter = adapter

    @staticmethod
    def _contact_data(prospect: Prospect) -> ContactData:
        return ContactData(
            first_name=prospect.first_name,
            last_name=prospect.last_name,
            email=prospect.email,
            phone_number=prospect.phone_number,
            company_name=prospect.company_name,
            linkedin_url=prospect.linkedin_url,
        )

    @staticmethod
    def _company_data(prospect: Prospect) -> CompanyData | None:
        if not prospect.company_name:
            return None
        return CompanyData(name=prospect.company_name, domain=prospect.company_domain)

    async def _log_sync(
        self,
        db: AsyncSession | None,
        prospect: Prospect,
        sync_type: str,
        status: CrmSyncStatus,
        provider_response: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        if db is None:
            return
        db.add(CrmSyncLog(
            id=str(uuid.uuid4()),
            tenant_id=prospect.tenant_id,
            prospect_id=prospect.id,
            provider="HUBSPOT",
            sync_type=sync_type,
            status=status,
            provider_response=provider_response or {},
            error_message=error_message,
            created_at=datetime.now(UTC),
        ))
        await db.flush()

    async def sync_contact(self, prospect: Prospect, db: AsyncSession | None = None) -> str:
        try:
            contact_id = await self.adapter.upsert_contact(self._contact_data(prospect), prospect.hubspot_contact_id)
        except Exception as e:
            await self._log_sync(db, prospect, "CONTACT", CrmSyncStatus.FAILURE, error_message=str(e))
            raise
        prospect.hubspot_contact_id = contact_id
        await self._log_sync(db, prospect, "CONTACT", CrmSyncStatus.SUCCESS, provider_response={"id": contact_id})
        return contact_id

    async def sync_company(self, prospect: Prospect, db: AsyncSession | None = None) -> str | None:
        """Upserts the prospect's company in HubSpot and associates it with
        their contact record. Previously entirely missing - only
        company_name was ever synced, as a plain string property on the
        Contact, with no Company object and no association at all."""
        company_data = self._company_data(prospect)
        if not company_data:
            return None
        if not prospect.hubspot_contact_id:
            await self.sync_contact(prospect, db=db)
        try:
            company_id = await self.adapter.upsert_company(company_data, prospect.hubspot_company_id)
            await self.adapter.associate_contact_company(prospect.hubspot_contact_id, company_id)
        except Exception as e:
            await self._log_sync(db, prospect, "COMPANY", CrmSyncStatus.FAILURE, error_message=str(e))
            raise
        prospect.hubspot_company_id = company_id
        await self._log_sync(db, prospect, "COMPANY", CrmSyncStatus.SUCCESS, provider_response={"id": company_id})
        return company_id

    async def log_activity(self, prospect: Prospect, text: str, db: AsyncSession | None = None) -> None:
        if not prospect.hubspot_contact_id:
            await self.sync_contact(prospect, db=db)
        try:
            note_id = await self.adapter.log_note(prospect.hubspot_contact_id, text)
        except Exception as e:
            await self._log_sync(db, prospect, "NOTE", CrmSyncStatus.FAILURE, error_message=str(e))
            raise
        await self._log_sync(db, prospect, "NOTE", CrmSyncStatus.SUCCESS, provider_response={"id": note_id})

    async def sync_status(self, prospect: Prospect, db: AsyncSession | None = None) -> None:
        """Reflects the prospect's current status in HubSpot: a status note,
        a company sync/association, plus a deal stage update for states
        with real deal-worthy signal."""
        if not prospect.hubspot_contact_id:
            await self.sync_contact(prospect, db=db)

        await self.sync_company(prospect, db=db)

        try:
            note_id = await self.adapter.log_note(prospect.hubspot_contact_id, f"Status updated to {prospect.status.value}")
        except Exception as e:
            await self._log_sync(db, prospect, "NOTE", CrmSyncStatus.FAILURE, error_message=str(e))
            raise
        await self._log_sync(db, prospect, "NOTE", CrmSyncStatus.SUCCESS, provider_response={"id": note_id})

        stage = DEAL_STAGE_BY_STATE.get(prospect.status)
        if stage:
            try:
                deal_id = await self.adapter.upsert_deal(
                    prospect.hubspot_contact_id,
                    prospect.hubspot_deal_id,
                    deal_name=f"{prospect.first_name} {prospect.last_name}",
                    stage=stage,
                )
            except Exception as e:
                await self._log_sync(db, prospect, "DEAL", CrmSyncStatus.FAILURE, error_message=str(e))
                raise
            prospect.hubspot_deal_id = deal_id
            await self._log_sync(db, prospect, "DEAL", CrmSyncStatus.SUCCESS, provider_response={"id": deal_id})

    async def log_meeting_booked(self, prospect: Prospect, db: AsyncSession | None = None) -> None:
        if not prospect.hubspot_contact_id:
            await self.sync_contact(prospect, db=db)
        try:
            meeting_id = await self.adapter.log_meeting(
                prospect.hubspot_contact_id,
                title=f"Meeting with {prospect.first_name} {prospect.last_name}",
                meeting_time=datetime.now(UTC),
            )
        except Exception as e:
            await self._log_sync(db, prospect, "MEETING", CrmSyncStatus.FAILURE, error_message=str(e))
            raise
        await self._log_sync(db, prospect, "MEETING", CrmSyncStatus.SUCCESS, provider_response={"id": meeting_id})
