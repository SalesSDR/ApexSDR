from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.schemas import Prospect, ProspectState, WorkspaceSetting
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.voice.base import CallResult, VoiceAdapter
from app.workers.tasks import execute_call_task


class _FakeVoiceAdapter(VoiceAdapter):
    async def initiate_call(self, to_number, twimlet_url):
        return CallResult(sid="CA_fake_sid", status="queued")


class _RaisingVoiceAdapter(VoiceAdapter):
    async def initiate_call(self, to_number, twimlet_url):
        raise RuntimeError("simulated Twilio outage")


def _noop_crm_service() -> CRMService:
    return CRMService(MockHubSpotAdapter())


async def test_execute_call_task_transitions_to_in_progress_via_ctx_adapter(db_session):
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Katherine",
        last_name="Johnson",
        linkedin_url="https://linkedin.com/in/katherine",
        phone_number="+15551234567",
        status=ProspectState.EMAIL_SENT,
    )
    db_session.add(prospect)
    await db_session.flush()

    # execute_call_task opens its own session via ctx['sessionmaker']; bind it
    # to the same connection as db_session so both see the same in-progress
    # transaction, which the outer fixture rolls back at teardown.
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {"sessionmaker": session_factory, "voice_adapter": _FakeVoiceAdapter(), "crm_service": _noop_crm_service()}

    await execute_call_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.CALL_IN_PROGRESS
    assert prospect.call_attempts == 1


async def test_execute_call_task_retries_on_failure_without_dev_mode(db_session):
    # Regression test for a NameError that used to occur here: dev_mode was
    # referenced in this task's except block but never fetched, so any
    # Twilio failure crashed the task instead of applying the retry policy.
    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=False))
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Rosalind",
        last_name="Franklin",
        linkedin_url="https://linkedin.com/in/rosalind",
        phone_number="+15551234567",
        status=ProspectState.EMAIL_SENT,
    )
    db_session.add(prospect)
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {"sessionmaker": session_factory, "voice_adapter": _RaisingVoiceAdapter(), "crm_service": _noop_crm_service()}

    await execute_call_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.EMAIL_SENT  # unchanged, still queued for retry
    assert prospect.retry_count == 1
    assert prospect.next_action_at is not None


async def test_execute_call_task_bypasses_failure_in_dev_mode(db_session):
    db_session.add(WorkspaceSetting(tenant_id="test-tenant", dev_mode=True))
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Ada",
        last_name="King",
        linkedin_url="https://linkedin.com/in/ada-king",
        phone_number="+15551234567",
        status=ProspectState.EMAIL_SENT,
    )
    db_session.add(prospect)
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {"sessionmaker": session_factory, "voice_adapter": _RaisingVoiceAdapter(), "crm_service": _noop_crm_service()}

    await execute_call_task(ctx, prospect.id)

    await db_session.refresh(prospect)
    assert prospect.retry_count == 0
    assert prospect.status == ProspectState.CALL_IN_PROGRESS
