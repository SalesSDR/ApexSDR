from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.ai as ai_module
from app.config import settings
from app.models.schemas import LinkedInAccount, Prospect, ProspectState, WorkspaceSetting
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.linkedin.base import LinkedInRateLimitError
from app.services.linkedin.service import LinkedInQueueService
from app.workers.tasks import send_linkedin_followup_task, start_outbound_sequence


@pytest.fixture(autouse=True)
def _no_real_ai_calls(monkeypatch):
    """Both start_outbound_sequence (LinkedIn request) and
    send_linkedin_followup_task now go through PersonalizationService
    (Sprint 5, item 1), which calls generate_outreach_message - stub it out
    everywhere in this file so these queue/retry-focused tests never make a
    real Gemini call."""
    async def _fake_generate(*a, **kw):
        return "Great to connect!"

    monkeypatch.setattr(ai_module, "generate_outreach_message", _fake_generate)


class _RecordingAdapter:
    def __init__(self):
        self.connection_calls = []

    async def send_connection_request(self, linkedin_url, account_id, message=None):
        self.connection_calls.append((linkedin_url, account_id, message))
        return {"status": "sent"}

    async def send_message(self, account_id, provider_id, text):
        return {"status": "sent"}


class _RaisingAdapter:
    async def send_connection_request(self, linkedin_url, account_id, message=None):
        raise RuntimeError("simulated Unipile outage")

    async def send_message(self, account_id, provider_id, text):
        raise RuntimeError("simulated Unipile outage")


class _RateLimitedAdapter:
    async def send_connection_request(self, linkedin_url, account_id, message=None):
        raise LinkedInRateLimitError("429 from Unipile")

    async def send_message(self, account_id, provider_id, text):
        raise LinkedInRateLimitError("429 from Unipile")


def _ctx(db_session, adapter, jitter_patch=True):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return {
        "sessionmaker": session_factory,
        "linkedin_queue": LinkedInQueueService(adapter),
        "crm_service": CRMService(MockHubSpotAdapter()),
    }


async def test_start_outbound_sequence_sends_and_increments_daily_count(db_session, monkeypatch):
    import app.workers.tasks as tasks
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    # .env.production sets a real UNIPILE_ACCOUNT_ID - pin it to None here so
    # account resolution deterministically falls back to
    # f"profile_{tenant_id}", matching the fixtures below.
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)

    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=True))
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Ada",
        last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-queue",
        status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    await start_outbound_sequence(_ctx(db_session, _RecordingAdapter()), prospect.id, "test-tenant")

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.LI_REQ_SENT

    account = (await db_session.execute(select(LinkedInAccount).where(LinkedInAccount.tenant_id == "test-tenant"))).scalar_one()
    assert account.daily_send_count == 1


async def test_start_outbound_sequence_defers_without_sending_when_daily_limit_reached(db_session, monkeypatch):
    import app.workers.tasks as tasks
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    # .env.production sets a real UNIPILE_ACCOUNT_ID - pin it to None here so
    # account resolution deterministically falls back to
    # f"profile_{tenant_id}", matching the fixtures below.
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)

    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=True))
    db_session.add(LinkedInAccount(
        tenant_id="test-tenant", account_id="profile_test-tenant",
        daily_send_count=20, daily_limit=20, daily_count_date=date.today(),
    ))
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="At",
        last_name="Limit",
        linkedin_url="https://linkedin.com/in/at-limit",
        status=ProspectState.IDLE,
        retry_count=0,
    )
    db_session.add(prospect)
    await db_session.flush()

    adapter = _RecordingAdapter()
    await start_outbound_sequence(_ctx(db_session, adapter), prospect.id, "test-tenant")

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.IDLE  # never attempted
    assert prospect.retry_count == 0  # a policy defer is not a failure
    assert prospect.next_action_at is not None
    assert adapter.connection_calls == []


async def test_start_outbound_sequence_defers_when_account_paused(db_session, monkeypatch):
    import app.workers.tasks as tasks
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    # .env.production sets a real UNIPILE_ACCOUNT_ID - pin it to None here so
    # account resolution deterministically falls back to
    # f"profile_{tenant_id}", matching the fixtures below.
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)

    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=True))
    db_session.add(LinkedInAccount(
        tenant_id="test-tenant", account_id="profile_test-tenant",
        daily_count_date=date.today(), is_paused=True, paused_reason="rate_limited",
        paused_until=datetime.now(UTC) + timedelta(hours=2),
    ))
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Paused",
        last_name="Account",
        linkedin_url="https://linkedin.com/in/paused-account",
        status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    adapter = _RecordingAdapter()
    await start_outbound_sequence(_ctx(db_session, adapter), prospect.id, "test-tenant")

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.IDLE
    assert prospect.retry_count == 0
    assert adapter.connection_calls == []


async def test_start_outbound_sequence_pauses_account_on_rate_limit_response(db_session, monkeypatch):
    import app.workers.tasks as tasks
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    # .env.production sets a real UNIPILE_ACCOUNT_ID - pin it to None here so
    # account resolution deterministically falls back to
    # f"profile_{tenant_id}", matching the fixtures below.
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)

    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=False))
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Rate",
        last_name="Limited",
        linkedin_url="https://linkedin.com/in/rate-limited",
        status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    await start_outbound_sequence(_ctx(db_session, _RateLimitedAdapter()), prospect.id, "test-tenant")

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.IDLE  # unchanged - never a "failure" of this prospect's own
    assert prospect.retry_count == 0  # rate limiting doesn't burn this prospect's retry budget

    account = (await db_session.execute(select(LinkedInAccount).where(LinkedInAccount.tenant_id == "test-tenant"))).scalar_one()
    assert account.is_paused is True
    assert account.paused_reason == "rate_limited"


async def test_start_outbound_sequence_generic_failure_still_uses_retry_engine(db_session, monkeypatch):
    # Regression check: a plain send failure (not rate-limiting) must keep
    # using core/retry.py's evaluate_retry exactly as before Module 4.
    import app.workers.tasks as tasks
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    # .env.production sets a real UNIPILE_ACCOUNT_ID - pin it to None here so
    # account resolution deterministically falls back to
    # f"profile_{tenant_id}", matching the fixtures below.
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)

    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=False))
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Generic",
        last_name="Failure",
        linkedin_url="https://linkedin.com/in/generic-failure",
        status=ProspectState.IDLE,
        retry_count=0,
    )
    db_session.add(prospect)
    await db_session.flush()

    await start_outbound_sequence(_ctx(db_session, _RaisingAdapter()), prospect.id, "test-tenant")

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.IDLE
    assert prospect.retry_count == 1
    assert prospect.next_action_at is not None


async def test_send_linkedin_followup_task_sends_and_increments_daily_count(db_session, monkeypatch):
    import app.workers.tasks as tasks
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    # .env.production sets a real UNIPILE_ACCOUNT_ID - pin it to None here so
    # account resolution deterministically falls back to
    # f"profile_{tenant_id}", matching the fixtures below.
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", None)

    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=True))
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Follow",
        last_name="Up",
        linkedin_url="https://linkedin.com/in/follow-up",
        status=ProspectState.LI_ACCEPTED_NO_MSG,
    )
    db_session.add(prospect)
    await db_session.flush()

    await send_linkedin_followup_task(_ctx(db_session, _RecordingAdapter()), prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.LI_MSG_SENT

    account = (await db_session.execute(select(LinkedInAccount).where(LinkedInAccount.tenant_id == "test-tenant"))).scalar_one()
    assert account.daily_send_count == 1


async def _ret(value):
    return value
