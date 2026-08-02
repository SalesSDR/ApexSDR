from app.config import settings
from app.services.linkedin.factory import get_linkedin_adapter
from app.services.linkedin.mock import MockLinkedInAdapter
from app.services.linkedin.production import ProductionLinkedInAdapter


def test_factory_returns_mock_when_use_mock_clients(monkeypatch):
    # Sprint 7.1: USE_MOCK_CLIENTS is the ONE switch - even with a real
    # account configured, USE_MOCK_CLIENTS=true must guarantee no live call.
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", "acc_live_123")

    adapter = get_linkedin_adapter(http_client=None)

    assert isinstance(adapter, MockLinkedInAdapter)


def test_factory_returns_production_when_not_mock(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", False)
    monkeypatch.setattr(settings, "UNIPILE_ACCOUNT_ID", "acc_live_123")
    monkeypatch.setattr(settings, "UNIPILE_API_KEY", "real_key")

    adapter = get_linkedin_adapter(http_client=object())

    assert isinstance(adapter, ProductionLinkedInAdapter)


async def test_mock_adapter_returns_sent_status_without_network_access():
    adapter = MockLinkedInAdapter()

    conn_result = await adapter.send_connection_request("https://linkedin.com/in/someone", "acc_1", "hi")
    msg_result = await adapter.send_message("acc_1", "provider_123", "hello")

    assert conn_result["status"] == "sent"
    assert msg_result["status"] == "sent"
