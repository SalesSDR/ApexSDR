"""Sequence Engine execution tests (Sprint 2, item 2): the worker must
execute SequenceStep records from the database in step_number order, with
no channel/order hardcoded in Python. Each test below configures a
DIFFERENT order for the same tenant and confirms the executor follows
whatever is configured - the strongest proof "no hardcoded order" actually
holds is reordering the steps and watching the executed channel change."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.ai as ai_module
import app.workers.tasks as tasks_module
from app.models.schemas import Prospect, ProspectState, SequenceRule, SequenceStep
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.linkedin.mock import MockLinkedInAdapter
from app.services.linkedin.service import LinkedInQueueService
from app.workers.tasks import execute_sequence_step_task


@pytest.fixture(autouse=True)
def _no_external_calls(monkeypatch):
    """apply_jitter() sleeps 10-30s per outbound send outside dev_mode, and
    generate_outreach_message()/send_native_email() are real Gemini/Resend
    calls - these tests seed no WorkspaceSetting row and have no valid API
    keys in the test environment, so both would otherwise slow the suite
    down and then fail for reasons unrelated to sequencing. Every channel
    now calls PersonalizationService.generate_message() (Sprint 5, item 1),
    which imports generate_outreach_message from app.services.ai fresh on
    each call - patching it there (not on tasks_module, which no longer
    imports it at all) is what actually takes effect."""
    async def _instant_jitter(ctx, dev_mode=False):
        return None

    async def _fake_generate_message(*a, **kw):
        return "Hi there, this is a test outreach message from ApexSDR."

    async def _fake_send_email(**kw):
        return {"status": "sent", "message_id": "msg_test"}

    monkeypatch.setattr(tasks_module, "apply_jitter", _instant_jitter)
    monkeypatch.setattr(ai_module, "generate_outreach_message", _fake_generate_message)
    monkeypatch.setattr(tasks_module, "send_native_email", _fake_send_email)


class _FakeVoiceAdapter:
    def __init__(self):
        self.calls = []

    async def initiate_call(self, to_number, twimlet_url):
        self.calls.append(to_number)
        from app.services.voice.base import CallResult
        return CallResult(sid="CA_fake", status="queued")


async def _seed_rule_and_steps(db_session, tenant_id: str, step_defs):
    """step_defs: list of (channel, step_number) tuples, in whatever order
    the caller wants to prove the executor actually follows."""
    rule = SequenceRule(id=str(uuid.uuid4()), tenant_id=tenant_id)
    db_session.add(rule)
    await db_session.flush()
    for channel, step_number in step_defs:
        db_session.add(SequenceStep(
            id=str(uuid.uuid4()), sequence_rule_id=rule.id, channel=channel,
            step_number=step_number, title=channel, delay_minutes=1440,
        ))
    await db_session.flush()
    return rule


def _ctx(db_session, **extra):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {
        "sessionmaker": session_factory,
        "crm_service": CRMService(MockHubSpotAdapter()),
        "linkedin_queue": LinkedInQueueService(MockLinkedInAdapter()),
        "voice_adapter": _FakeVoiceAdapter(),
    }
    ctx.update(extra)
    return ctx


async def test_executor_runs_linkedin_first_when_configured_first(db_session):
    await _seed_rule_and_steps(db_session, "seq-tenant-1", [
        ("LINKEDIN", 1), ("EMAIL_1", 2),
    ])
    prospect = Prospect(
        tenant_id="seq-tenant-1", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-seq1", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    await execute_sequence_step_task(_ctx(db_session), prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.LI_REQ_SENT
    assert prospect.sequence_step_index == 1


async def test_executor_runs_email_first_when_configured_first(db_session):
    """The exact same channel set as the test above, reordered - proves the
    order comes from step_number in the DB, not from any hardcoded Python
    preference for LinkedIn-before-email."""
    await _seed_rule_and_steps(db_session, "seq-tenant-2", [
        ("EMAIL_1", 1), ("LINKEDIN", 2),
    ])
    prospect = Prospect(
        tenant_id="seq-tenant-2", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-seq2", status=ProspectState.IDLE,
        email="grace@example.com",
    )
    db_session.add(prospect)
    await db_session.flush()

    await execute_sequence_step_task(_ctx(db_session), prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.EMAIL_SENT  # not LI_REQ_SENT
    assert prospect.sequence_step_index == 1


async def test_executor_advances_through_all_seven_channels_in_configured_order(db_session):
    step_defs = [
        ("LINKEDIN", 1), ("LINKEDIN_FOLLOWUP", 2), ("EMAIL_1", 3), ("EMAIL_2", 4),
        ("CALL", 5), ("VOICEMAIL", 6), ("BREAKUP_EMAIL", 7),
    ]
    await _seed_rule_and_steps(db_session, "seq-tenant-full", step_defs)

    prospect = Prospect(
        tenant_id="seq-tenant-full", first_name="Katherine", last_name="Johnson",
        linkedin_url="https://linkedin.com/in/katherine-seq-full", status=ProspectState.IDLE,
        email="katherine@example.com", phone_number="+15551234567",
    )
    db_session.add(prospect)
    await db_session.flush()

    expected_states = [
        ProspectState.LI_REQ_SENT,       # LINKEDIN
        ProspectState.LI_MSG_SENT,       # LINKEDIN_FOLLOWUP
        ProspectState.EMAIL_SENT,        # EMAIL_1
        ProspectState.EMAIL_2_SENT,      # EMAIL_2
    ]
    for i, expected_state in enumerate(expected_states):
        await execute_sequence_step_task(_ctx(db_session), prospect.id)
        await db_session.refresh(prospect)
        assert prospect.status == expected_state, f"step {i}: expected {expected_state}, got {prospect.status}"
        assert prospect.sequence_step_index == i + 1

    # CALL manages its own transition (awaits the Twilio webhook) rather
    # than advancing generically - see _run_call_channel_step.
    await execute_sequence_step_task(_ctx(db_session), prospect.id)
    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.CALL_IN_PROGRESS
    assert prospect.sequence_step_index == 5  # CALL already advanced the index itself
    assert prospect.next_action_at is None  # awaiting the webhook, not a timer

    # VOICEMAIL
    await execute_sequence_step_task(_ctx(db_session), prospect.id)
    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.VOICEMAIL_LEFT
    assert prospect.sequence_step_index == 6

    # BREAKUP_EMAIL - the final configured step
    await execute_sequence_step_task(_ctx(db_session), prospect.id)
    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.BREAKUP_EMAIL_SENT
    assert prospect.sequence_step_index == 7

    # No more steps configured - a further call is a safe no-op.
    status_before = prospect.status
    index_before = prospect.sequence_step_index
    await execute_sequence_step_task(_ctx(db_session), prospect.id)
    await db_session.refresh(prospect)
    assert prospect.status == status_before
    assert prospect.sequence_step_index == index_before


async def test_executor_is_a_noop_for_a_tenant_with_no_configured_sequence(db_session):
    prospect = Prospect(
        tenant_id="seq-tenant-none", first_name="No", last_name="Sequence",
        linkedin_url="https://linkedin.com/in/no-sequence", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    await execute_sequence_step_task(_ctx(db_session), prospect.id)

    await db_session.refresh(prospect)
    assert prospect.status == ProspectState.IDLE  # untouched
    assert prospect.sequence_step_index == 0
