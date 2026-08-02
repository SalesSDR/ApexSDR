import base64
import hashlib
import hmac
import time

import pytest
from fastapi import HTTPException
from twilio.request_validator import RequestValidator

from app.api.v1 import webhooks
from app.config import settings


class _FakeURL:
    def __init__(self, path, query=""):
        self.path = path
        self.query = query


class _FakeTwilioRequest:
    """Minimal stand-in for starlette.Request - only the attributes
    verify_twilio_signature() actually reads: .headers, .url.path,
    .url.query, and an async .form()."""

    def __init__(
        self, form_params: dict, signature: str = None,
        path: str = "/api/v1/webhooks/twilio/call-status", query: str = "",
    ):
        self._form_params = form_params
        self.headers = {"X-Twilio-Signature": signature} if signature else {}
        self.url = _FakeURL(path, query)

    async def form(self):
        return self._form_params


def _sign(auth_token: str, url: str, params: dict) -> str:
    return RequestValidator(auth_token).compute_signature(url, params)


# --- Twilio ---

async def test_twilio_valid_signature_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "real-auth-token")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.apexsdr.com")

    params = {"CallStatus": "completed", "To": "+15551234567"}
    url = "https://api.apexsdr.com/api/v1/webhooks/twilio/call-status"
    signature = _sign("real-auth-token", url, params)

    request = _FakeTwilioRequest(params, signature=signature)
    await webhooks.verify_twilio_signature(request)  # must not raise


async def test_twilio_invalid_signature_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "real-auth-token")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.apexsdr.com")

    params = {"CallStatus": "completed", "To": "+15551234567"}
    request = _FakeTwilioRequest(params, signature="totally-wrong-signature")

    with pytest.raises(HTTPException) as exc_info:
        await webhooks.verify_twilio_signature(request)
    assert exc_info.value.status_code == 401


async def test_twilio_missing_signature_header_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "real-auth-token")

    request = _FakeTwilioRequest({"CallStatus": "completed", "To": "+15551234567"}, signature=None)

    with pytest.raises(HTTPException) as exc_info:
        await webhooks.verify_twilio_signature(request)
    assert exc_info.value.status_code == 401


async def test_twilio_tampered_params_are_rejected(monkeypatch):
    """Signature was computed over a different To number than what's
    actually posted - must be caught even though a signature is present."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "real-auth-token")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.apexsdr.com")

    signed_params = {"CallStatus": "completed", "To": "+15551234567"}
    url = "https://api.apexsdr.com/api/v1/webhooks/twilio/call-status"
    signature = _sign("real-auth-token", url, signed_params)

    tampered_request = _FakeTwilioRequest({"CallStatus": "completed", "To": "+19998887777"}, signature=signature)

    with pytest.raises(HTTPException) as exc_info:
        await webhooks.verify_twilio_signature(tampered_request)
    assert exc_info.value.status_code == 401


async def test_twilio_signature_over_a_url_with_a_query_string_is_accepted(monkeypatch):
    """Sprint 7.1: the voice webhooks carry `?prospect_id=...&call_sid=...`
    in their callback URL - Twilio signs the FULL URL it requested,
    including the query string, so verify_twilio_signature must include it
    too rather than validating against the bare path."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "real-auth-token")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.apexsdr.com")

    params = {"CallSid": "CA123", "To": "+15551234567"}
    url = "https://api.apexsdr.com/api/v1/voice/webhook/recording?prospect_id=abc-123&call_sid=CA123"
    signature = _sign("real-auth-token", url, params)

    request = _FakeTwilioRequest(
        params, signature=signature,
        path="/api/v1/voice/webhook/recording", query="prospect_id=abc-123&call_sid=CA123",
    )
    await webhooks.verify_twilio_signature(request)  # must not raise


async def test_twilio_signature_rejects_a_tampered_query_string(monkeypatch):
    """The signature was computed for one prospect_id - a request claiming
    a different one (even with an otherwise-valid-looking signature must
    fail, since the query string is part of what Twilio actually signed."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "real-auth-token")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.apexsdr.com")

    params = {"CallSid": "CA123", "To": "+15551234567"}
    signed_url = "https://api.apexsdr.com/api/v1/voice/webhook/recording?prospect_id=abc-123&call_sid=CA123"
    signature = _sign("real-auth-token", signed_url, params)

    request = _FakeTwilioRequest(
        params, signature=signature,
        path="/api/v1/voice/webhook/recording", query="prospect_id=someone-elses-prospect&call_sid=CA123",
    )
    with pytest.raises(HTTPException) as exc_info:
        await webhooks.verify_twilio_signature(request)
    assert exc_info.value.status_code == 401


async def test_twilio_verification_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", None)
    request = _FakeTwilioRequest({"CallStatus": "completed", "To": "+15551234567"}, signature="anything")

    with pytest.raises(HTTPException) as exc_info:
        await webhooks.verify_twilio_signature(request)
    assert exc_info.value.status_code == 401


# --- Unipile ---

class _FakeUnipileRequest:
    def __init__(self, headers: dict):
        self.headers = headers


def test_unipile_valid_shared_secret_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_WEBHOOK_SECRET", "correct-secret")
    request = _FakeUnipileRequest({"Unipile-Auth": "correct-secret"})
    webhooks.verify_unipile_signature(request)  # must not raise


def test_unipile_wrong_secret_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_WEBHOOK_SECRET", "correct-secret")
    request = _FakeUnipileRequest({"Unipile-Auth": "wrong-secret"})

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_unipile_signature(request)
    assert exc_info.value.status_code == 401


def test_unipile_missing_header_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_WEBHOOK_SECRET", "correct-secret")
    request = _FakeUnipileRequest({})

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_unipile_signature(request)
    assert exc_info.value.status_code == 401


def test_unipile_verification_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_WEBHOOK_SECRET", None)
    request = _FakeUnipileRequest({"Unipile-Auth": "anything"})

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_unipile_signature(request)
    assert exc_info.value.status_code == 401


# --- Resend (delivered via Svix) ---

_TEST_WHSEC_RAW_KEY = b"0123456789abcdef0123456789abcdef"
_TEST_WHSEC = "whsec_" + base64.b64encode(_TEST_WHSEC_RAW_KEY).decode("utf-8")


class _FakeResendRequest:
    def __init__(self, headers: dict):
        self.headers = headers


def _sign_resend_payload(secret_with_prefix: str, svix_id: str, svix_timestamp: str, raw_body: bytes) -> str:
    """Mirrors the exact algorithm verify_resend_signature implements, so
    these tests prove the implementation against an independently
    constructed reference signature, not against itself."""
    raw_key = base64.b64decode(secret_with_prefix[len("whsec_"):])
    signed_content = f"{svix_id}.{svix_timestamp}.".encode() + raw_body
    digest = hmac.new(raw_key, signed_content, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_resend_valid_signature_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", _TEST_WHSEC)

    raw_body = b'{"from_email": "prospect@example.com", "text": "sounds good"}'
    svix_id = "msg_2abc"
    svix_timestamp = str(int(time.time()))
    signature = _sign_resend_payload(_TEST_WHSEC, svix_id, svix_timestamp, raw_body)

    request = _FakeResendRequest({
        "svix-id": svix_id,
        "svix-timestamp": svix_timestamp,
        "svix-signature": f"v1,{signature}",
    })
    webhooks.verify_resend_signature(request, raw_body)  # must not raise


def test_resend_accepts_a_match_among_multiple_space_delimited_signatures(monkeypatch):
    """svix-signature can carry multiple versioned entries (e.g. secret
    rotation) - any single match must be accepted."""
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", _TEST_WHSEC)

    raw_body = b'{"from_email": "prospect@example.com", "text": "sounds good"}'
    svix_id = "msg_2abc"
    svix_timestamp = str(int(time.time()))
    real_signature = _sign_resend_payload(_TEST_WHSEC, svix_id, svix_timestamp, raw_body)

    request = _FakeResendRequest({
        "svix-id": svix_id,
        "svix-timestamp": svix_timestamp,
        "svix-signature": f"v1,not-the-real-signature v1,{real_signature}",
    })
    webhooks.verify_resend_signature(request, raw_body)  # must not raise


def test_resend_invalid_signature_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", _TEST_WHSEC)

    raw_body = b'{"from_email": "prospect@example.com", "text": "sounds good"}'
    request = _FakeResendRequest({
        "svix-id": "msg_2abc",
        "svix-timestamp": str(int(time.time())),
        "svix-signature": "v1,dG90YWxseS13cm9uZw==",
    })

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_resend_signature(request, raw_body)
    assert exc_info.value.status_code == 401


def test_resend_tampered_body_is_rejected(monkeypatch):
    """Signature was computed over a different body than what's actually
    delivered - must be caught even though a well-formed signature header
    is present."""
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", _TEST_WHSEC)

    svix_id = "msg_2abc"
    svix_timestamp = str(int(time.time()))
    signed_body = b'{"from_email": "prospect@example.com", "text": "sounds good"}'
    signature = _sign_resend_payload(_TEST_WHSEC, svix_id, svix_timestamp, signed_body)

    tampered_body = b'{"from_email": "prospect@example.com", "text": "please stop contacting me"}'
    request = _FakeResendRequest({
        "svix-id": svix_id,
        "svix-timestamp": svix_timestamp,
        "svix-signature": f"v1,{signature}",
    })

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_resend_signature(request, tampered_body)
    assert exc_info.value.status_code == 401


def test_resend_missing_headers_are_rejected(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", _TEST_WHSEC)
    request = _FakeResendRequest({})

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_resend_signature(request, b"{}")
    assert exc_info.value.status_code == 401


def test_resend_stale_timestamp_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", _TEST_WHSEC)

    raw_body = b'{"from_email": "prospect@example.com", "text": "sounds good"}'
    svix_id = "msg_2abc"
    stale_timestamp = str(int(time.time()) - 3600)  # 1 hour old, outside tolerance
    signature = _sign_resend_payload(_TEST_WHSEC, svix_id, stale_timestamp, raw_body)

    request = _FakeResendRequest({
        "svix-id": svix_id,
        "svix-timestamp": stale_timestamp,
        "svix-signature": f"v1,{signature}",
    })

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_resend_signature(request, raw_body)
    assert exc_info.value.status_code == 401


def test_resend_verification_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", None)
    request = _FakeResendRequest({
        "svix-id": "msg_2abc",
        "svix-timestamp": str(int(time.time())),
        "svix-signature": "v1,anything",
    })

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_resend_signature(request, b"{}")
    assert exc_info.value.status_code == 401
