"""Sprint 5, item 1 (Rich Personalization): every outbound channel - the
Sequence Engine's LinkedIn request/follow-up, Email 1/2, breakup email, and
the legacy follow-up/nudge tasks - must call generate_outreach_message with
a real, non-empty `context` (company enrichment, qualification, buying
signals, conversation memory, industry, funding, tech stack, news, job
title), never a bare name/company prompt. Captures the actual `context`
dict PersonalizationService builds and asserts it's populated from the
prospect's enrichment fields."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.ai as ai_module
from app.models.schemas import (
    BuyingSignal,
    ConversationMemory,
    MemoryType,
    Prospect,
    ProspectState,
    SequenceRule,
    SequenceStep,
    SignalStrength,
    SignalType,
)
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.linkedin.mock import MockLinkedInAdapter
from app.services.linkedin.service import LinkedInQueueService
from app.workers.tasks import (
    execute_email_dispatch_task,
    execute_sequence_step_task,
    send_email_nudge_task,
    send_linkedin_followup_task,
    start_outbound_sequence,
)


@pytest.fixture
def captured_calls(monkeypatch):
    calls = []

    async def _fake_generate(prospect_name, company, prompt_type="linkedin", fallback_mode=True, context=None):
        calls.append({"prompt_type": prompt_type, "context": context})
        return "A generated outreach message."

    monkeypatch.setattr(ai_module, "generate_outreach_message", _fake_generate)
    return calls


@pytest.fixture(autouse=True)
def _instant_jitter(monkeypatch):
    import app.workers.tasks as tasks_module

    async def _noop(ctx, dev_mode=False):
        return None

    monkeypatch.setattr(tasks_module, "apply_jitter", _noop)


@pytest.fixture(autouse=True)
def _fake_email_send(monkeypatch):
    import app.workers.tasks as tasks_module

    async def _fake_send(recipient, subject, text):
        return {"status": "sent", "message_id": "msg_test"}

    monkeypatch.setattr(tasks_module, "send_native_email", _fake_send)


def _rich_prospect(**overrides) -> Prospect:
    defaults = dict(
        tenant_id="rich-tenant", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-rich", email="ada@richcorp.com",
        company_name="RichCorp", job_title="VP of Engineering", industry="Fintech",
        company_description="Builds payment infrastructure.", company_website="https://richcorp.io",
        tech_stack=["Python", "Kubernetes"], funding_stage="SERIES_B", funding_amount=25_000_000,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


def _assert_rich_context(context: dict):
    """The core assertion of this file: context must be populated, not
    None/empty, and must actually carry the enrichment fields set on the
    test prospect - proof this isn't a minimal name/company prompt."""
    assert context is not None
    assert context["job_title"] == "VP of Engineering"
    assert context["industry"] == "Fintech"
    assert context["company_description"] == "Builds payment infrastructure."
    assert context["company_website"] == "https://richcorp.io"
    assert context["tech_stack"] == "Python, Kubernetes"
    assert "Series B" in context["funding_info"]


async def test_legacy_linkedin_request_uses_rich_context(db_session, captured_calls):

    prospect = _rich_prospect(status=ProspectState.IDLE)
    db_session.add(prospect)
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {
        "sessionmaker": session_factory,
        "linkedin_queue": LinkedInQueueService(MockLinkedInAdapter()),
        "crm_service": CRMService(MockHubSpotAdapter()),
    }
    await start_outbound_sequence(ctx, prospect.id, "rich-tenant")

    assert len(captured_calls) == 1
    assert captured_calls[0]["prompt_type"] == "linkedin_request"
    _assert_rich_context(captured_calls[0]["context"])


async def test_legacy_linkedin_followup_uses_rich_context(db_session, captured_calls):
    prospect = _rich_prospect(status=ProspectState.LI_ACCEPTED_NO_MSG)
    db_session.add(prospect)
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {
        "sessionmaker": session_factory,
        "linkedin_queue": LinkedInQueueService(MockLinkedInAdapter()),
        "crm_service": CRMService(MockHubSpotAdapter()),
    }
    await send_linkedin_followup_task(ctx, prospect.id)

    assert len(captured_calls) == 1
    assert captured_calls[0]["prompt_type"] == "linkedin_followup"
    _assert_rich_context(captured_calls[0]["context"])


async def test_legacy_email_1_dispatch_uses_rich_context(db_session, captured_calls):
    prospect = _rich_prospect(status=ProspectState.LI_REQ_SENT)
    db_session.add(prospect)
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {"sessionmaker": session_factory, "crm_service": CRMService(MockHubSpotAdapter())}
    await execute_email_dispatch_task(ctx, prospect.id)

    assert len(captured_calls) == 1
    assert captured_calls[0]["prompt_type"] == "email_1"
    _assert_rich_context(captured_calls[0]["context"])


async def test_legacy_nudge_uses_rich_context(db_session, captured_calls):
    prospect = _rich_prospect(status=ProspectState.PAUSED_NUDGED)
    db_session.add(prospect)
    await db_session.flush()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    ctx = {"sessionmaker": session_factory, "crm_service": CRMService(MockHubSpotAdapter())}
    await send_email_nudge_task(ctx, prospect.id)

    assert len(captured_calls) == 1
    assert captured_calls[0]["prompt_type"] == "email_nudge"
    _assert_rich_context(captured_calls[0]["context"])


async def _seed_rule_and_steps(db_session, tenant_id, step_defs):
    rule = SequenceRule(id=str(uuid.uuid4()), tenant_id=tenant_id)
    db_session.add(rule)
    await db_session.flush()
    for channel, step_number in step_defs:
        db_session.add(SequenceStep(
            id=str(uuid.uuid4()), sequence_rule_id=rule.id, channel=channel,
            step_number=step_number, title=channel, delay_minutes=60,
        ))
    await db_session.flush()


def _sequence_ctx(db_session):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return {
        "sessionmaker": session_factory,
        "crm_service": CRMService(MockHubSpotAdapter()),
        "linkedin_queue": LinkedInQueueService(MockLinkedInAdapter()),
    }


@pytest.mark.parametrize(
    "channel,status,expected_prompt_type",
    [
        ("LINKEDIN", ProspectState.IDLE, "linkedin_request"),
        ("LINKEDIN_FOLLOWUP", ProspectState.IDLE, "linkedin_followup"),
        ("EMAIL_1", ProspectState.IDLE, "email_1"),
        ("EMAIL_2", ProspectState.IDLE, "email_2"),
        ("BREAKUP_EMAIL", ProspectState.IDLE, "breakup_email"),
    ],
)
async def test_sequence_engine_channel_uses_rich_context(db_session, captured_calls, channel, status, expected_prompt_type):
    tenant_id = f"rich-seq-{channel.lower()}"
    await _seed_rule_and_steps(db_session, tenant_id, [(channel, 1)])

    prospect = _rich_prospect(tenant_id=tenant_id, status=status, phone_number="+15551234567")
    db_session.add(prospect)
    await db_session.flush()

    memory = ConversationMemory(
        tenant_id=tenant_id, prospect_id=prospect.id, memory_type=MemoryType.AI_NOTE,
        content="Prospect mentioned budget approval next quarter.", source="SYSTEM",
    )
    signal = BuyingSignal(
        tenant_id=tenant_id, prospect_id=prospect.id, signal_type=SignalType.COMPANY_HIRING,
        signal_source="test", signal_strength=SignalStrength.HIGH, summary="Hiring 5 engineers",
    )
    db_session.add_all([memory, signal])
    await db_session.flush()

    await execute_sequence_step_task(_sequence_ctx(db_session), prospect.id)

    assert len(captured_calls) == 1
    assert captured_calls[0]["prompt_type"] == expected_prompt_type
    context = captured_calls[0]["context"]
    _assert_rich_context(context)
    assert "Prospect mentioned budget approval" in context["conversation_memory"]
    assert "Hiring 5 engineers" in context["hiring_signals"]
