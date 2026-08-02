from app.config import settings
from app.services.voice.factory import get_voice_adapter
from app.services.voice.mock import MockTwilioAdapter
from app.services.voice.production import ProductionTwilioAdapter


async def test_factory_returns_mock_when_use_mock_clients(monkeypatch):
    # Sprint 7.1: USE_MOCK_CLIENTS is the ONE switch - even with real-looking
    # credentials configured, USE_MOCK_CLIENTS=true must guarantee no live
    # Twilio call.
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_fake_sid_for_test")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "fake_auth_token")

    adapter = get_voice_adapter()

    assert isinstance(adapter, MockTwilioAdapter)


async def test_factory_returns_production_when_not_mock(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_fake_sid_for_test")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "fake_auth_token")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15550001111")

    adapter = get_voice_adapter()

    assert isinstance(adapter, ProductionTwilioAdapter)


async def test_mock_adapter_returns_queued_call_without_network_access():
    adapter = MockTwilioAdapter()

    result = await adapter.initiate_call(to_number="+15551234567", twimlet_url="http://example.com/twiml")

    assert result.status == "queued"
    assert result.sid.startswith("CA")
