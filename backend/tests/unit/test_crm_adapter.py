from app.config import settings
from app.services.crm.factory import get_crm_adapter
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.production import ProductionHubSpotAdapter


async def test_factory_returns_mock_when_use_mock_clients(monkeypatch):
    # Sprint 7.1: USE_MOCK_CLIENTS is the ONE switch - even with a real-looking
    # key configured, USE_MOCK_CLIENTS=true must guarantee no live HubSpot call.
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    monkeypatch.setattr(settings, "HUBSPOT_API_KEY", "fake-private-app-token")

    adapter = get_crm_adapter(http_client=None)

    assert isinstance(adapter, MockHubSpotAdapter)


async def test_factory_returns_production_when_not_mock(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", False)
    monkeypatch.setattr(settings, "HUBSPOT_API_KEY", "fake-private-app-token")

    adapter = get_crm_adapter(http_client=None)

    assert isinstance(adapter, ProductionHubSpotAdapter)


async def test_mock_adapter_upsert_contact_generates_stable_id_when_given_one():
    from app.services.crm.base import ContactData

    adapter = MockHubSpotAdapter()
    contact = ContactData(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        phone_number=None,
        company_name=None,
        linkedin_url=None,
    )

    first_id = await adapter.upsert_contact(contact, external_id=None)
    second_id = await adapter.upsert_contact(contact, external_id=first_id)

    assert first_id.startswith("mock_contact_")
    assert second_id == first_id
