"""Sprint 7: Speech-to-Text adapter - mock (no network), production
(Deepgram, HTTP mocked), and the factory switch between them."""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import settings
from app.services.voice_ai.stt.factory import get_stt_provider
from app.services.voice_ai.stt.mock import MockSTTProvider
from app.services.voice_ai.stt.production import DeepgramSTTProvider


async def test_mock_stt_passes_through_the_input_as_the_transcript():
    provider = MockSTTProvider()
    result = await provider.transcribe("the prospect said yes to a demo")
    assert result == "the prospect said yes to a demo"


def test_factory_returns_mock_when_use_mock_clients(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    provider = get_stt_provider(httpx.AsyncClient())
    assert isinstance(provider, MockSTTProvider)


def test_factory_returns_deepgram_when_not_mock(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", False)
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "fake-deepgram-key")
    provider = get_stt_provider(httpx.AsyncClient())
    assert isinstance(provider, DeepgramSTTProvider)


@pytest.fixture
def fake_http_client():
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


async def test_deepgram_provider_downloads_recording_then_transcribes(fake_http_client):
    recording_response = MagicMock()
    recording_response.content = b"fake-audio-bytes"
    recording_response.raise_for_status = MagicMock()
    recording_response.is_redirect = False
    fake_http_client.get.return_value = recording_response

    deepgram_response = MagicMock()
    deepgram_response.raise_for_status = MagicMock()
    deepgram_response.json.return_value = {
        "results": {"channels": [{"alternatives": [{"transcript": "yes let's book a demo"}]}]}
    }
    fake_http_client.post.return_value = deepgram_response

    provider = DeepgramSTTProvider(
        api_key="fake-key", http_client=fake_http_client,
        twilio_account_sid="ACfake", twilio_auth_token="fake-token",
    )
    result = await provider.transcribe("https://api.twilio.com/recordings/RE123")

    assert result == "yes let's book a demo"
    # Downloaded with the .mp3 suffix and Twilio Basic Auth.
    get_args, get_kwargs = fake_http_client.get.call_args
    assert get_args[0] == "https://api.twilio.com/recordings/RE123.mp3"
    assert get_kwargs["auth"] == ("ACfake", "fake-token")
    # Posted the downloaded bytes (not the bare URL) to Deepgram.
    post_args, post_kwargs = fake_http_client.post.call_args
    assert post_kwargs["content"] == b"fake-audio-bytes"
    assert "Token fake-key" in post_kwargs["headers"]["Authorization"]


async def test_deepgram_provider_raises_on_unexpected_response_shape(fake_http_client):
    recording_response = MagicMock()
    recording_response.content = b"fake-audio-bytes"
    recording_response.raise_for_status = MagicMock()
    recording_response.is_redirect = False
    fake_http_client.get.return_value = recording_response

    deepgram_response = MagicMock()
    deepgram_response.raise_for_status = MagicMock()
    deepgram_response.json.return_value = {"unexpected": "shape"}
    fake_http_client.post.return_value = deepgram_response

    provider = DeepgramSTTProvider(
        api_key="fake-key", http_client=fake_http_client,
        twilio_account_sid="ACfake", twilio_auth_token="fake-token",
    )
    with pytest.raises(ValueError):
        await provider.transcribe("https://api.twilio.com/recordings/RE123")
