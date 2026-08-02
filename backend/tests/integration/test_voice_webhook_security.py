"""Sprint 7.1: the two live-call Twilio webhooks (/webhook/incoming,
/webhook/recording) must never process an unauthenticated request, and
must never mutate a prospect the request doesn't actually correspond to.
Covers: missing/invalid signature -> 401; valid signature but a To-number
or call-state mismatch -> rejected without mutating anything; valid
signature + genuine ownership -> the real turn runs."""
import uuid

from twilio.request_validator import RequestValidator

from app.config import settings
from app.models.schemas import Prospect, ProspectState

_PUBLIC_BASE_URL = "https://api.apexsdr.test"
_AUTH_TOKEN = "test-twilio-auth-token"


def _sign(path: str, query: str, form_params: dict) -> str:
    url = f"{_PUBLIC_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    return RequestValidator(_AUTH_TOKEN).compute_signature(url, form_params)


async def _seed_prospect(db_session, **overrides) -> Prospect:
    defaults = dict(
        id=str(uuid.uuid4()), tenant_id="org_voice_webhook_sec", first_name="Riley", last_name="Prospect",
        linkedin_url=f"https://linkedin.com/in/{uuid.uuid4().hex}", phone_number="+15551230000",
        status=ProspectState.CALL_CONNECTED,
    )
    defaults.update(overrides)
    prospect = Prospect(**defaults)
    db_session.add(prospect)
    await db_session.flush()
    return prospect


def _configure_twilio(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", _AUTH_TOKEN)
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", _PUBLIC_BASE_URL)
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)


async def test_incoming_webhook_rejects_missing_signature(client, db_session, monkeypatch):
    _configure_twilio(monkeypatch)
    prospect = await _seed_prospect(db_session)
    await db_session.commit()

    response = await client.post(f"/api/v1/voice/webhook/incoming?prospect_id={prospect.id}", data={"CallSid": "CA1", "To": "+15551230000"})
    assert response.status_code == 401


async def test_incoming_webhook_rejects_invalid_signature(client, db_session, monkeypatch):
    _configure_twilio(monkeypatch)
    prospect = await _seed_prospect(db_session)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/voice/webhook/incoming?prospect_id={prospect.id}",
        data={"CallSid": "CA1", "To": "+15551230000"},
        headers={"X-Twilio-Signature": "not-a-real-signature"},
    )
    assert response.status_code == 401


async def test_incoming_webhook_accepts_a_genuine_signature_for_an_owned_prospect(client, db_session, monkeypatch):
    _configure_twilio(monkeypatch)
    prospect = await _seed_prospect(db_session, status=ProspectState.CALL_IN_PROGRESS)
    await db_session.commit()

    form = {"CallSid": "CA1", "To": "+15551230000"}
    query = f"prospect_id={prospect.id}"
    signature = _sign("/api/v1/voice/webhook/incoming", query, form)

    response = await client.post(
        f"/api/v1/voice/webhook/incoming?{query}", data=form, headers={"X-Twilio-Signature": signature},
    )
    assert response.status_code == 200
    assert "<Response>" in response.text


async def test_incoming_webhook_rejects_a_signature_that_does_not_cover_the_query_string(client, db_session, monkeypatch):
    """A signature computed for a different prospect_id must not authorize
    a request that swaps in another prospect_id, even if the form body is
    identical."""
    _configure_twilio(monkeypatch)
    prospect = await _seed_prospect(db_session, status=ProspectState.CALL_IN_PROGRESS)
    other_prospect = await _seed_prospect(db_session, status=ProspectState.CALL_IN_PROGRESS, phone_number="+15551239999")
    await db_session.commit()

    form = {"CallSid": "CA1", "To": "+15551230000"}
    signature = _sign("/api/v1/voice/webhook/incoming", f"prospect_id={prospect.id}", form)

    response = await client.post(
        f"/api/v1/voice/webhook/incoming?prospect_id={other_prospect.id}",
        data=form, headers={"X-Twilio-Signature": signature},
    )
    assert response.status_code == 401


async def test_recording_webhook_rejects_when_to_number_does_not_match_prospect(client, db_session, monkeypatch):
    """Tenant/ownership isolation: a genuinely-signed Twilio request whose
    To number doesn't match the claimed prospect_id's phone_number must be
    rejected (TwiML Reject), not processed against the wrong prospect."""
    _configure_twilio(monkeypatch)
    prospect = await _seed_prospect(db_session, status=ProspectState.CALL_CONNECTED, phone_number="+15551230000")
    await db_session.commit()

    form = {"CallSid": "CA2", "To": "+19995550000", "RecordingUrl": ""}
    query = f"prospect_id={prospect.id}&call_sid=CA2"
    signature = _sign("/api/v1/voice/webhook/recording", query, form)

    response = await client.post(
        f"/api/v1/voice/webhook/recording?{query}", data=form, headers={"X-Twilio-Signature": signature},
    )
    assert response.status_code == 200
    assert "<Reject" in response.text

    refreshed = await db_session.get(Prospect, prospect.id)
    assert refreshed.status == ProspectState.CALL_CONNECTED  # untouched


async def test_recording_webhook_rejects_when_prospect_is_not_mid_call(client, db_session, monkeypatch):
    """A prospect that isn't currently in an active-call state (e.g. the
    call already concluded) must not be reachable via a replayed/late
    webhook, even with a valid signature and matching phone number."""
    _configure_twilio(monkeypatch)
    prospect = await _seed_prospect(db_session, status=ProspectState.MEETING_BOOKED, phone_number="+15551230000")
    await db_session.commit()

    form = {"CallSid": "CA3", "To": "+15551230000", "RecordingUrl": ""}
    query = f"prospect_id={prospect.id}&call_sid=CA3"
    signature = _sign("/api/v1/voice/webhook/recording", query, form)

    response = await client.post(
        f"/api/v1/voice/webhook/recording?{query}", data=form, headers={"X-Twilio-Signature": signature},
    )
    assert response.status_code == 200
    assert "<Reject" in response.text

    refreshed = await db_session.get(Prospect, prospect.id)
    assert refreshed.status == ProspectState.MEETING_BOOKED  # untouched


async def test_recording_webhook_processes_a_genuine_turn_for_the_owned_prospect(client, db_session, monkeypatch):
    _configure_twilio(monkeypatch)
    prospect = await _seed_prospect(db_session, status=ProspectState.CALL_CONNECTED, phone_number="+15551230000")
    await db_session.commit()

    form = {"CallSid": "CA4", "To": "+15551230000", "RecordingUrl": "Yes, let's book a demo."}
    query = f"prospect_id={prospect.id}&call_sid=CA4"
    signature = _sign("/api/v1/voice/webhook/recording", query, form)

    response = await client.post(
        f"/api/v1/voice/webhook/recording?{query}", data=form, headers={"X-Twilio-Signature": signature},
    )
    assert response.status_code == 200
    assert "<Hangup" in response.text

    refreshed = await db_session.get(Prospect, prospect.id)
    assert refreshed.status == ProspectState.MEETING_BOOKED
