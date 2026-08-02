"""CRM Company synchronization + CrmSyncLog audit trail (Sprint 2, item 3).
Uses real Postgres (db_session) since the point is verifying CrmSyncLog rows
actually get persisted - a pure-mock unit test wouldn't prove that."""
from sqlalchemy import select

from app.models.schemas import CrmSyncLog, CrmSyncStatus, Prospect
from app.services.crm.base import CRMAdapter
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService


class _FailingCompanyAdapter(CRMAdapter):
    """upsert_contact succeeds, upsert_company always fails - lets tests
    exercise the FAILURE branch of sync logging deterministically."""

    async def upsert_contact(self, contact, external_id):
        return external_id or "contact_1"

    async def upsert_company(self, company, external_id):
        raise Exception("HubSpot company API is down")

    async def associate_contact_company(self, contact_id, company_id):
        pass

    async def log_note(self, contact_id, text):
        return "note_1"

    async def upsert_deal(self, contact_id, deal_id, deal_name, stage):
        return deal_id or "deal_1"

    async def log_meeting(self, contact_id, title, meeting_time):
        return "meeting_1"


def _prospect(**overrides) -> Prospect:
    defaults = dict(
        tenant_id="crm-company-tenant", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-crm-company",
        company_name="Acme Corp", company_domain="acme.com",
    )
    defaults.update(overrides)
    return Prospect(**defaults)


# --- CRM company tests ---

async def test_sync_company_upserts_and_associates(db_session):
    prospect = _prospect()
    db_session.add(prospect)
    await db_session.flush()

    service = CRMService(MockHubSpotAdapter())
    company_id = await service.sync_company(prospect, db=db_session)

    assert company_id is not None
    assert prospect.hubspot_company_id == company_id


async def test_sync_company_is_a_noop_without_a_company_name(db_session):
    prospect = _prospect(company_name=None, company_domain=None)
    db_session.add(prospect)
    await db_session.flush()

    service = CRMService(MockHubSpotAdapter())
    company_id = await service.sync_company(prospect, db=db_session)

    assert company_id is None
    assert prospect.hubspot_company_id is None


async def test_sync_company_syncs_contact_first_if_missing(db_session):
    prospect = _prospect()
    db_session.add(prospect)
    await db_session.flush()
    assert prospect.hubspot_contact_id is None

    service = CRMService(MockHubSpotAdapter())
    await service.sync_company(prospect, db=db_session)

    assert prospect.hubspot_contact_id is not None  # auto-synced as a prerequisite


async def test_sync_status_also_syncs_company_when_present(db_session):
    prospect = _prospect()
    db_session.add(prospect)
    await db_session.flush()

    service = CRMService(MockHubSpotAdapter())
    await service.sync_status(prospect, db=db_session)

    assert prospect.hubspot_company_id is not None


# --- CRM sync log tests ---

async def test_successful_contact_sync_is_logged(db_session):
    prospect = _prospect()
    db_session.add(prospect)
    await db_session.flush()

    service = CRMService(MockHubSpotAdapter())
    contact_id = await service.sync_contact(prospect, db=db_session)

    rows = (await db_session.execute(
        select(CrmSyncLog).where(CrmSyncLog.prospect_id == prospect.id, CrmSyncLog.sync_type == "CONTACT")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == CrmSyncStatus.SUCCESS
    assert rows[0].provider == "HUBSPOT"
    assert rows[0].provider_response == {"id": contact_id}
    assert rows[0].created_at is not None
    assert rows[0].error_message is None


async def test_successful_company_sync_is_logged(db_session):
    prospect = _prospect()
    db_session.add(prospect)
    await db_session.flush()

    service = CRMService(MockHubSpotAdapter())
    company_id = await service.sync_company(prospect, db=db_session)

    rows = (await db_session.execute(
        select(CrmSyncLog).where(CrmSyncLog.prospect_id == prospect.id, CrmSyncLog.sync_type == "COMPANY")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == CrmSyncStatus.SUCCESS
    assert rows[0].provider_response == {"id": company_id}


async def test_failed_company_sync_is_logged_with_error_and_reraises(db_session):
    prospect = _prospect()
    db_session.add(prospect)
    await db_session.flush()

    service = CRMService(_FailingCompanyAdapter())

    raised = False
    try:
        await service.sync_company(prospect, db=db_session)
    except Exception as e:
        raised = True
        assert "HubSpot company API is down" in str(e)
    assert raised  # failures still propagate to the caller unchanged

    rows = (await db_session.execute(
        select(CrmSyncLog).where(CrmSyncLog.prospect_id == prospect.id, CrmSyncLog.sync_type == "COMPANY")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == CrmSyncStatus.FAILURE
    assert rows[0].error_message == "HubSpot company API is down"
    assert rows[0].provider_response == {}


async def test_sync_log_is_skipped_without_a_db_session_but_sync_still_works(db_session):
    """Backward compatibility: callers (mostly unit tests) that don't pass
    `db` still get a working sync, just without an audit row - never a
    crash from the logging path itself."""
    prospect = _prospect()
    db_session.add(prospect)
    await db_session.flush()

    service = CRMService(MockHubSpotAdapter())
    contact_id = await service.sync_contact(prospect)  # no db= kwarg

    assert contact_id is not None
    rows = (await db_session.execute(
        select(CrmSyncLog).where(CrmSyncLog.prospect_id == prospect.id)
    )).scalars().all()
    assert rows == []
