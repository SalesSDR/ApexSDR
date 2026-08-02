from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.schemas import Prospect, ProspectState
from app.services.crm.base import CRMAdapter
from app.services.voice.base import CallResult, VoiceAdapter
from app.workers.tasks import execute_call_task, sync_crm_contact_task


class _FakeCRMAdapter(CRMAdapter):
    def __init__(self):
        self.contacts = []
        self.companies = []
        self.associations = []
        self.notes = []
        self.deals = []
        self.meetings = []

    async def upsert_contact(self, contact, external_id):
        contact_id = external_id or f"contact_{len(self.contacts)}"
        self.contacts.append(contact_id)
        return contact_id

    async def upsert_company(self, company, external_id):
        company_id = external_id or f"company_{len(self.companies)}"
        self.companies.append(company_id)
        return company_id

    async def associate_contact_company(self, contact_id, company_id):
        self.associations.append((contact_id, company_id))

    async def log_note(self, contact_id, text):
        self.notes.append((contact_id, text))
        return f"note_{len(self.notes)}"

    async def upsert_deal(self, contact_id, deal_id, deal_name, stage):
        deal_id = deal_id or f"deal_{len(self.deals)}"
        self.deals.append((contact_id, deal_id, stage))
        return deal_id

    async def log_meeting(self, contact_id, title, meeting_time):
        self.meetings.append((contact_id, title))
        return f"meeting_{len(self.meetings)}"


class _FakeVoiceAdapter(VoiceAdapter):
    async def initiate_call(self, to_number, twimlet_url):
        return CallResult(sid="CA_fake_sid", status="queued")


async def test_sync_crm_contact_task_upserts_contact_for_new_prospect(db_session):
    from app.services.crm.service import CRMService

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Katherine",
        last_name="Johnson",
        linkedin_url="https://linkedin.com/in/katherine-crm",
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_crm = _FakeCRMAdapter()
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {"sessionmaker": session_factory, "crm_service": CRMService(fake_crm)}

    await sync_crm_contact_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.hubspot_contact_id is not None
    assert len(fake_crm.contacts) == 1


async def test_execute_call_task_syncs_crm_status_on_transition(db_session):
    from app.services.crm.service import CRMService

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Rosalind",
        last_name="Franklin",
        linkedin_url="https://linkedin.com/in/rosalind-crm",
        phone_number="+15551234567",
        status=ProspectState.EMAIL_SENT,
    )
    db_session.add(prospect)
    await db_session.flush()

    fake_crm = _FakeCRMAdapter()
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {
        "sessionmaker": session_factory,
        "voice_adapter": _FakeVoiceAdapter(),
        "crm_service": CRMService(fake_crm),
    }

    await execute_call_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.CALL_IN_PROGRESS
    assert prospect.hubspot_contact_id is not None
    assert len(fake_crm.notes) == 1
    assert "CALL_IN_PROGRESS" in fake_crm.notes[0][1]
