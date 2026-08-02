from datetime import datetime

from app.models.schemas import Prospect, ProspectState
from app.services.crm.base import CRMAdapter
from app.services.crm.service import CRMService


class _RecordingCRMAdapter(CRMAdapter):
    def __init__(self):
        self.contacts = []
        self.companies = []
        self.associations = []
        self.notes = []
        self.deals = []
        self.meetings = []

    async def upsert_contact(self, contact, external_id):
        contact_id = external_id or f"contact_{len(self.contacts)}"
        self.contacts.append((contact_id, contact))
        return contact_id

    async def upsert_company(self, company, external_id):
        company_id = external_id or f"company_{len(self.companies)}"
        self.companies.append((company_id, company))
        return company_id

    async def associate_contact_company(self, contact_id, company_id):
        self.associations.append((contact_id, company_id))

    async def log_note(self, contact_id, text):
        note_id = f"note_{len(self.notes)}"
        self.notes.append((contact_id, text))
        return note_id

    async def upsert_deal(self, contact_id, deal_id, deal_name, stage):
        deal_id = deal_id or f"deal_{len(self.deals)}"
        self.deals.append((contact_id, deal_id, deal_name, stage))
        return deal_id

    async def log_meeting(self, contact_id, title, meeting_time):
        meeting_id = f"meeting_{len(self.meetings)}"
        self.meetings.append((contact_id, title, meeting_time))
        return meeting_id


def _prospect(**overrides) -> Prospect:
    defaults = dict(
        tenant_id="test-tenant",
        first_name="Grace",
        last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace",
        status=ProspectState.IDLE,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


async def test_sync_contact_persists_external_id_on_prospect():
    adapter = _RecordingCRMAdapter()
    service = CRMService(adapter)
    prospect = _prospect()

    contact_id = await service.sync_contact(prospect)

    assert prospect.hubspot_contact_id == contact_id
    assert len(adapter.contacts) == 1


async def test_sync_contact_reuses_existing_external_id():
    adapter = _RecordingCRMAdapter()
    service = CRMService(adapter)
    prospect = _prospect(hubspot_contact_id="existing_contact_1")

    contact_id = await service.sync_contact(prospect)

    assert contact_id == "existing_contact_1"
    assert adapter.contacts[0][0] == "existing_contact_1"


async def test_sync_status_logs_a_note_for_every_status():
    adapter = _RecordingCRMAdapter()
    service = CRMService(adapter)
    prospect = _prospect(status=ProspectState.LI_REQ_SENT)

    await service.sync_status(prospect)

    assert len(adapter.notes) == 1
    assert "LI_REQ_SENT" in adapter.notes[0][1]
    assert len(adapter.deals) == 0  # not a deal-worthy state


async def test_sync_status_creates_deal_on_meeting_booked():
    adapter = _RecordingCRMAdapter()
    service = CRMService(adapter)
    prospect = _prospect(status=ProspectState.MEETING_BOOKED)

    await service.sync_status(prospect)

    assert len(adapter.deals) == 1
    _, deal_id, _, stage = adapter.deals[0]
    assert stage == "appointmentscheduled"
    assert prospect.hubspot_deal_id == deal_id


async def test_sync_status_marks_deal_closed_lost_on_terminal_states():
    for state in (ProspectState.COMPLETED_DECLINED, ProspectState.UNRESPONSIVE_DEAD, ProspectState.LOST):
        adapter = _RecordingCRMAdapter()
        service = CRMService(adapter)
        prospect = _prospect(status=state)

        await service.sync_status(prospect)

        assert adapter.deals[0][3] == "closedlost"


async def test_log_meeting_booked_syncs_contact_first_if_missing():
    adapter = _RecordingCRMAdapter()
    service = CRMService(adapter)
    prospect = _prospect()

    await service.log_meeting_booked(prospect)

    assert len(adapter.contacts) == 1  # auto-synced since hubspot_contact_id was unset
    assert len(adapter.meetings) == 1
    assert isinstance(adapter.meetings[0][2], datetime)
