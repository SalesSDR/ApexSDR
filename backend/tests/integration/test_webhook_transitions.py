import json

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1 import webhooks
from app.models.schemas import Prospect, ProspectState
from app.services.decision.engine import SEQUENCE_STEP_TASK_NAME
from tests.conftest import TEST_UNIPILE_WEBHOOK_SECRET


class _FakeRequest:
    def __init__(self, json_body=None, headers=None):
        self._json_body = json_body or {}
        # Real Unipile-Auth secret by default, so these tests exercise the
        # actual verify_unipile_signature() logic rather than bypassing it -
        # pass headers={} explicitly to test the rejection path instead.
        self.headers = {"Unipile-Auth": TEST_UNIPILE_WEBHOOK_SECRET} if headers is None else headers

    async def json(self):
        return self._json_body

    async def body(self):
        return json.dumps(self._json_body).encode("utf-8")


async def _make_prospect(db_session, **overrides):
    defaults = dict(
        tenant_id="test-tenant",
        first_name="Ada",
        last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-webhook",
    )
    defaults.update(overrides)
    prospect = Prospect(**defaults)
    db_session.add(prospect)
    await db_session.flush()
    return prospect


def _fresh_session(db_session):
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return session_factory()


async def _noop_crm_sync(prospect, db=None, log_meeting=False):
    return True


async def _noop_calendar_booking(arq_pool, prospect):
    return None


async def _noop_twilio_signature(request):
    return None


def _noop_resend_signature(request, raw_body):
    return None


# --- Unipile: invitation accepted (regression test for the request.app.state.redis_pool
# AttributeError bug found via live smoke test - that attribute is never set anywhere) ---

async def test_unipile_invitation_accepted_transitions_and_enqueues_followup(db_session, monkeypatch):
    enqueued = []

    async def _fake_enqueue(arq_pool, task_name, *args):
        enqueued.append((task_name, args))

    monkeypatch.setattr(webhooks, "enqueue_task", _fake_enqueue)
    monkeypatch.setattr(webhooks, "sync_crm_after_reply", _noop_crm_sync)

    prospect = await _make_prospect(
        db_session, provider_id="provider_xyz", status=ProspectState.LI_REQ_SENT
    )

    resp = await webhooks.handle_unipile_webhook(
        _FakeRequest({"event": "invitation:accepted", "data": {"sender_id": "provider_xyz"}}),
        db=_fresh_session(db_session),
        redis=None,
        arq_pool=None,
    )

    await db_session.refresh(prospect)
    assert resp == {"status": "received"}
    assert prospect.status == ProspectState.LI_ACCEPTED_NO_MSG
    assert enqueued == [(SEQUENCE_STEP_TASK_NAME, (prospect.id,))]


async def test_unipile_message_positive_intent_books_meeting(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "classify_intent_service", lambda text: _ret("POSITIVE"))
    monkeypatch.setattr(webhooks, "sync_crm_after_reply", _noop_crm_sync)
    monkeypatch.setattr(webhooks, "queue_calendar_booking", _noop_calendar_booking)

    prospect = await _make_prospect(
        db_session, provider_id="provider_pos", status=ProspectState.LI_MSG_SENT
    )

    resp = await webhooks.handle_unipile_webhook(
        _FakeRequest({"event": "message.created", "data": {"sender_id": "provider_pos", "text": "Yes, let's talk!"}}),
        db=_fresh_session(db_session),
        redis=None,
        arq_pool=None,
    )

    await db_session.refresh(prospect)
    assert resp == {"status": "received"}
    assert prospect.status == ProspectState.MEETING_BOOKED


async def test_unipile_message_from_terminal_state_is_a_noop(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "classify_intent_service", lambda text: _ret("POSITIVE"))

    prospect = await _make_prospect(
        db_session, provider_id="provider_dead", status=ProspectState.UNRESPONSIVE_DEAD
    )

    resp = await webhooks.handle_unipile_webhook(
        _FakeRequest({"event": "message.created", "data": {"sender_id": "provider_dead", "text": "hello?"}}),
        db=_fresh_session(db_session),
        redis=None,
        arq_pool=None,
    )

    await db_session.refresh(prospect)
    assert resp == {"status": "received"}
    assert prospect.status == ProspectState.UNRESPONSIVE_DEAD  # untouched - terminal states never transition


async def test_unipile_webhook_rejects_missing_auth_header(db_session):
    resp_or_exc = None
    try:
        await webhooks.handle_unipile_webhook(
            _FakeRequest({"event": "invitation:accepted", "data": {"sender_id": "provider_xyz"}}, headers={}),
            db=_fresh_session(db_session),
            redis=None,
            arq_pool=None,
        )
    except Exception as e:  # HTTPException
        resp_or_exc = e

    assert resp_or_exc is not None
    assert getattr(resp_or_exc, "status_code", None) == 401


async def test_unipile_webhook_rejects_wrong_auth_header(db_session):
    resp_or_exc = None
    try:
        await webhooks.handle_unipile_webhook(
            _FakeRequest(
                {"event": "invitation:accepted", "data": {"sender_id": "provider_xyz"}},
                headers={"Unipile-Auth": "wrong-secret"},
            ),
            db=_fresh_session(db_session),
            redis=None,
            arq_pool=None,
        )
    except Exception as e:  # HTTPException
        resp_or_exc = e

    assert resp_or_exc is not None
    assert getattr(resp_or_exc, "status_code", None) == 401


# --- Email reply ---

async def test_email_reply_negative_intent_pauses_and_nudges(db_session, monkeypatch):
    enqueued = []

    async def _fake_enqueue(arq_pool, task_name, *args):
        enqueued.append((task_name, args))

    monkeypatch.setattr(webhooks, "enqueue_task", _fake_enqueue)
    monkeypatch.setattr(webhooks, "classify_intent_service", lambda text: _ret("NEGATIVE"))
    monkeypatch.setattr(webhooks, "sync_crm_after_reply", _noop_crm_sync)
    monkeypatch.setattr(webhooks, "verify_resend_signature", _noop_resend_signature)

    prospect = await _make_prospect(
        db_session, email="ada@example.com", status=ProspectState.EMAIL_SENT
    )

    resp = await webhooks.handle_email_webhook(
        _FakeRequest({"from_email": "ada@example.com", "text": "not interested"}),
        db=_fresh_session(db_session),
        arq_pool=None,
    )

    await db_session.refresh(prospect)
    assert resp == {"status": "received"}
    assert prospect.status == ProspectState.PAUSED_NUDGED
    assert enqueued == [("send_email_nudge_task", (prospect.id,))]


# --- Twilio call status ---

async def test_twilio_answered_transitions_to_call_connected(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "verify_twilio_signature", _noop_twilio_signature)

    prospect = await _make_prospect(
        db_session, phone_number="+15551234567", status=ProspectState.CALL_IN_PROGRESS
    )

    resp = await webhooks.handle_twilio_webhook(
        None, db=_fresh_session(db_session), arq_pool=None, CallStatus="answered", To="+15551234567"
    )

    await db_session.refresh(prospect)
    assert resp == {"status": "received"}
    assert prospect.status == ProspectState.CALL_CONNECTED


async def test_twilio_completed_without_answered_is_gracefully_ignored(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "verify_twilio_signature", _noop_twilio_signature)

    # Sprint 7: "completed" no longer force-transitions to MEETING_BOOKED -
    # the real outcome is decided turn-by-turn by the live conversation
    # (services/voice_ai/orchestrator.py). A prospect that never reached
    # CALL_CONNECTED (an out-of-order or duplicate "completed" webhook) is
    # left untouched rather than raising an illegal-transition error.
    prospect = await _make_prospect(
        db_session, phone_number="+15559876543", status=ProspectState.CALL_QUEUED
    )

    resp = await webhooks.handle_twilio_webhook(
        None, db=_fresh_session(db_session), arq_pool=None, CallStatus="completed", To="+15559876543"
    )

    await db_session.refresh(prospect)
    assert resp == {"status": "received"}
    assert prospect.status == ProspectState.CALL_QUEUED  # unchanged


async def _ret(value):
    return value
