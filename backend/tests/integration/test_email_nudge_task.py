import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.ai as ai_module
import app.workers.tasks as tasks
from app.models.schemas import Prospect, ProspectState
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.workers.tasks import send_email_nudge_task


@pytest.fixture(autouse=True)
def _no_real_ai_calls(monkeypatch):
    """send_email_nudge_task now goes through PersonalizationService
    (Sprint 5, item 1), which calls generate_outreach_message from
    app.services.ai - stub it there, not on tasks (which no longer imports
    it at all)."""
    async def _fake_generate(*a, **kw):
        return "Just checking in!"

    monkeypatch.setattr(ai_module, "generate_outreach_message", _fake_generate)


def _ctx(db_session):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return {"sessionmaker": session_factory, "crm_service": CRMService(MockHubSpotAdapter())}


async def test_send_email_nudge_task_is_registered_with_the_worker():
    from app.workers.main import WorkerSettings

    assert send_email_nudge_task in WorkerSettings.functions


async def test_sends_nudge_and_keeps_prospect_paused(db_session, monkeypatch):
    sent = []

    async def _fake_send_email(recipient, subject, text):
        sent.append((recipient, subject, text))
        return {"id": "email_1"}

    monkeypatch.setattr(tasks, "send_native_email", _fake_send_email)
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Nudge",
        last_name="Target",
        linkedin_url="https://linkedin.com/in/nudge-target",
        email="nudge@example.com",
        status=ProspectState.PAUSED_NUDGED,
    )
    db_session.add(prospect)
    await db_session.flush()

    await send_email_nudge_task(_ctx(db_session), prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.PAUSED_NUDGED  # unchanged - still waiting for a real reply
    assert sent == [("nudge@example.com", "Following up", "Just checking in!")]


async def test_skips_prospects_not_currently_paused(db_session, monkeypatch):
    sent = []

    async def _fake_send_email(recipient, subject, text):
        sent.append((recipient, subject, text))

    monkeypatch.setattr(tasks, "send_native_email", _fake_send_email)

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Not",
        last_name="Paused",
        linkedin_url="https://linkedin.com/in/not-paused",
        email="notpaused@example.com",
        status=ProspectState.EMAIL_SENT,
    )
    db_session.add(prospect)
    await db_session.flush()

    await send_email_nudge_task(_ctx(db_session), prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.EMAIL_SENT
    assert sent == []


async def test_send_failure_is_logged_and_leaves_prospect_paused(db_session, monkeypatch):
    async def _raising_send_email(recipient, subject, text):
        raise RuntimeError("simulated Resend outage")

    monkeypatch.setattr(tasks, "send_native_email", _raising_send_email)
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))

    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Failing",
        last_name="Nudge",
        linkedin_url="https://linkedin.com/in/failing-nudge",
        email="failing@example.com",
        status=ProspectState.PAUSED_NUDGED,
    )
    db_session.add(prospect)
    await db_session.flush()

    await send_email_nudge_task(_ctx(db_session), prospect.id)  # must not raise

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.PAUSED_NUDGED


async def _ret(value):
    return value
