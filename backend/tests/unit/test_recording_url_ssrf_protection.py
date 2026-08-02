"""Sprint 7.1: SSRF protection for the Deepgram STT provider's RecordingUrl
fetch - the one place this codebase downloads a URL supplied by an inbound
webhook rather than one it built itself. Confirms the validator rejects
every class of malicious input the original vulnerability allowed, and
that DeepgramSTTProvider actually calls it before ever attaching Twilio
credentials to an outbound request."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.voice_ai.stt.production import DeepgramSTTProvider
from app.services.voice_ai.stt.recording_url_validation import (
    UntrustedRecordingURLError,
    validate_recording_url,
)


async def test_accepts_a_genuine_twilio_recording_url():
    await validate_recording_url("https://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/RE123.mp3")


async def test_rejects_non_https_scheme():
    with pytest.raises(UntrustedRecordingURLError, match="HTTPS"):
        await validate_recording_url("http://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/RE123.mp3")


async def test_rejects_an_arbitrary_attacker_host():
    with pytest.raises(UntrustedRecordingURLError, match="allowlist"):
        await validate_recording_url("https://attacker.example.com/steal-credentials.mp3")


async def test_rejects_a_lookalike_host():
    """A hostname that merely contains "twilio" as a substring (e.g. a
    subdomain-confusion attack) must not slip past the allowlist."""
    with pytest.raises(UntrustedRecordingURLError, match="allowlist"):
        await validate_recording_url("https://api.twilio.com.attacker.com/RE123.mp3")


async def test_rejects_embedded_credentials_in_the_url():
    with pytest.raises(UntrustedRecordingURLError, match="embedded credentials"):
        await validate_recording_url("https://user:pass@api.twilio.com/RE123.mp3")


async def test_rejects_a_host_that_resolves_to_a_private_ip(monkeypatch):
    """Defense in depth against DNS rebinding: even though the hostname is
    allowlisted, a resolution to a private/loopback address must still be
    rejected before we ever connect to it."""
    import socket

    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UntrustedRecordingURLError, match="non-public"):
        await validate_recording_url("https://api.twilio.com/RE123.mp3")


async def test_rejects_unresolvable_host(monkeypatch):
    import socket

    def fake_getaddrinfo(host, port):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UntrustedRecordingURLError, match="Could not resolve"):
        await validate_recording_url("https://api.twilio.com/RE123.mp3")


# --- DeepgramSTTProvider actually enforces the validator ---

@pytest.fixture
def fake_http_client():
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


async def test_transcribe_rejects_an_attacker_supplied_recording_url_before_any_network_call(fake_http_client):
    """The core exploit this closes: an attacker-controlled RecordingUrl
    must never reach http_client.get() at all - meaning Twilio's real
    Account SID/Auth Token are never attached to a request aimed at it."""
    provider = DeepgramSTTProvider(
        api_key="fake-key", http_client=fake_http_client,
        twilio_account_sid="ACfake", twilio_auth_token="fake-token",
    )

    with pytest.raises(UntrustedRecordingURLError):
        await provider.transcribe("https://attacker.example.com/collect-credentials")

    fake_http_client.get.assert_not_called()
    fake_http_client.post.assert_not_called()


async def test_transcribe_rejects_a_redirect_response(fake_http_client):
    recording_response = MagicMock()
    recording_response.is_redirect = True
    recording_response.headers = {"location": "https://attacker.example.com/steal"}
    fake_http_client.get.return_value = recording_response

    provider = DeepgramSTTProvider(
        api_key="fake-key", http_client=fake_http_client,
        twilio_account_sid="ACfake", twilio_auth_token="fake-token",
    )

    with pytest.raises(UntrustedRecordingURLError, match="redirect"):
        await provider.transcribe("https://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/RE123")

    # follow_redirects must be explicitly disabled - a redirect is surfaced
    # as a 3xx response object, never silently followed.
    _, get_kwargs = fake_http_client.get.call_args
    assert get_kwargs["follow_redirects"] is False
    fake_http_client.post.assert_not_called()
