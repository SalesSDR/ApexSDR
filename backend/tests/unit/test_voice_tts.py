"""Sprint 7: Text-to-Speech adapter - mock (no network, no real audio),
production (ElevenLabs, HTTP mocked), the factory switch, and the ephemeral
Redis-backed audio cache Twilio's <Play> verb fetches from."""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import settings
from app.services.voice_ai import audio_cache
from app.services.voice_ai.tts.factory import get_tts_provider
from app.services.voice_ai.tts.mock import MockTTSProvider
from app.services.voice_ai.tts.production import ElevenLabsTTSProvider


async def test_mock_tts_produces_no_real_audio():
    provider = MockTTSProvider()
    result = await provider.synthesize("Hello there")
    assert result.audio_bytes is None


def test_factory_returns_mock_when_use_mock_clients(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    provider = get_tts_provider(httpx.AsyncClient())
    assert isinstance(provider, MockTTSProvider)


def test_factory_returns_elevenlabs_when_not_mock(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", False)
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "fake-elevenlabs-key")
    provider = get_tts_provider(httpx.AsyncClient())
    assert isinstance(provider, ElevenLabsTTSProvider)


async def test_elevenlabs_provider_returns_synthesized_audio_bytes():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.content = b"fake-mp3-bytes"
    fake_client.post = AsyncMock(return_value=fake_response)

    provider = ElevenLabsTTSProvider(api_key="fake-key", voice_id="voice123", http_client=fake_client)
    result = await provider.synthesize("Hello, this is a test.")

    assert result.audio_bytes == b"fake-mp3-bytes"
    assert result.content_type == "audio/mpeg"
    args, kwargs = fake_client.post.call_args
    assert "voice123" in args[0]
    assert kwargs["headers"]["xi-api-key"] == "fake-key"
    assert kwargs["json"]["text"] == "Hello, this is a test."


# --- Ephemeral audio cache ---

@pytest.fixture
def fake_redis():
    store = {}

    class _FakeRedis:
        async def set(self, key, value, ex=None):
            store[key] = value

        async def get(self, key):
            return store.get(key)

    return _FakeRedis()


async def test_audio_round_trips_through_the_cache(fake_redis):
    audio_id = await audio_cache.store_audio(fake_redis, b"\x00\x01binarydata", "audio/mpeg")
    result = await audio_cache.get_audio(fake_redis, audio_id)

    assert result is not None
    audio_bytes, content_type = result
    assert audio_bytes == b"\x00\x01binarydata"
    assert content_type == "audio/mpeg"


async def test_missing_audio_id_returns_none(fake_redis):
    result = await audio_cache.get_audio(fake_redis, "does-not-exist")
    assert result is None
