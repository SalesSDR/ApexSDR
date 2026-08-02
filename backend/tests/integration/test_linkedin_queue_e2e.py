import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.ai as ai_module
from app.config import settings
from app.models.schemas import LinkedInAccount, Prospect, ProspectState, WorkspaceSetting
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.linkedin.service import LinkedInQueueService
from app.workers.tasks import start_outbound_sequence


@pytest.fixture(autouse=True)
def _no_real_ai_calls(monkeypatch):
    """start_outbound_sequence now goes through PersonalizationService
    (Sprint 5, item 1) for the connection-request note."""
    async def _fake_generate(*a, **kw):
        return "Looking forward to connecting!"

    monkeypatch.setattr(ai_module, "generate_outreach_message", _fake_generate)


class _RecordingAdapter:
    def __init__(self):
        self.sent = []

    async def send_connection_request(self, linkedin_url, account_id, message=None):
        self.sent.append(linkedin_url)
        return {"status": "sent"}

    async def send_message(self, account_id, provider_id, text):
        return {"status": "sent"}


async def test_daily_cap_shared_across_prospects_on_the_same_account(db_session, monkeypatch):
    """End-to-end: two IDLE prospects on the same tenant/account, a daily
    limit of 1. The first prospect's send consumes the whole quota; the
    second is deferred without ever calling the adapter - proving the cap
    is enforced per-account across prospects, not per-prospect."""
    import app.workers.tasks as tasks
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)
    monkeypatch.setattr(settings, "MAX_LINKEDIN_INVITES_PER_DAY", 1)

    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=True))
    first = Prospect(
        tenant_id="test-tenant", first_name="First", last_name="Prospect",
        linkedin_url="https://linkedin.com/in/first-e2e", status=ProspectState.IDLE,
    )
    second = Prospect(
        tenant_id="test-tenant", first_name="Second", last_name="Prospect",
        linkedin_url="https://linkedin.com/in/second-e2e", status=ProspectState.IDLE,
    )
    db_session.add_all([first, second])
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    adapter = _RecordingAdapter()
    ctx = {
        "sessionmaker": session_factory,
        "linkedin_queue": LinkedInQueueService(adapter),
        "crm_service": CRMService(MockHubSpotAdapter()),
    }

    await start_outbound_sequence(ctx, first.id, "test-tenant")
    await start_outbound_sequence(ctx, second.id, "test-tenant")

    await db_session.refresh(first)
    await db_session.refresh(second)

    assert first.status == ProspectState.LI_REQ_SENT
    assert second.status == ProspectState.IDLE  # deferred, quota exhausted
    assert second.next_action_at is not None
    assert adapter.sent == ["https://linkedin.com/in/first-e2e"]

    account = (await db_session.execute(
        select(LinkedInAccount).where(LinkedInAccount.tenant_id == "test-tenant")
    )).scalar_one()
    assert account.daily_send_count == 1
    assert account.daily_limit == 1


async def _ret(value):
    return value
