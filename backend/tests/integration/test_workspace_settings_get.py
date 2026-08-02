"""Sprint 6, item 2 (Dashboard Integration): GET /campaigns/settings - the
read half of the existing PUT, needed so a real admin-settings UI has
something to render instead of a permanent placeholder."""
from tests.conftest import bearer_for


async def test_get_settings_returns_defaults_when_none_saved_yet(client):
    response = await client.get("/api/v1/campaigns/settings", headers=bearer_for("org_settings_defaults"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tenant_id"] == "org_settings_defaults"
    assert data["timezone"] == "UTC"
    assert data["icp_profile"] == {}


async def test_get_settings_reflects_a_previous_put(client):
    await client.put(
        "/api/v1/campaigns/settings",
        json={"timezone": "America/New_York", "dev_mode": True},
        headers=bearer_for("org_settings_roundtrip"),
    )

    response = await client.get("/api/v1/campaigns/settings", headers=bearer_for("org_settings_roundtrip"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["timezone"] == "America/New_York"
    assert data["dev_mode"] is True


async def test_get_settings_requires_authentication(client):
    response = await client.get("/api/v1/campaigns/settings")
    assert response.status_code in (401, 403)
