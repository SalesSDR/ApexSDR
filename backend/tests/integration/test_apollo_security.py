from app.config import settings
from tests.conftest import bearer_for

APOLLO_SEARCH = "/api/v1/apollo/search"


async def test_apollo_search_requires_authentication(client):
    response = await client.post(APOLLO_SEARCH, json={"q_keywords": "engineer"})
    assert response.status_code == 401


async def test_apollo_search_authenticated_request_is_not_rejected_by_auth(client, monkeypatch):
    """With no APOLLO_API_KEY configured, an authenticated request still
    fails - but with a 500 from the missing-key check, not a 401. This
    proves auth + rate limiting run and pass before the Apollo-specific
    logic is ever reached."""
    monkeypatch.setattr(settings, "APOLLO_API_KEY", None)
    response = await client.post(
        APOLLO_SEARCH, json={"q_keywords": "engineer"}, headers=bearer_for("org_apollo_1")
    )
    assert response.status_code == 500
    assert response.status_code != 401


async def test_apollo_search_is_rate_limited_per_tenant(client, monkeypatch):
    monkeypatch.setattr(settings, "APOLLO_API_KEY", None)
    monkeypatch.setattr(settings, "APOLLO_RATE_LIMIT_PER_MINUTE", 3)
    headers = bearer_for("org_apollo_rate_limited")

    statuses = []
    for _ in range(5):
        response = await client.post(APOLLO_SEARCH, json={"q_keywords": "engineer"}, headers=headers)
        statuses.append(response.status_code)

    # First 3 pass rate limiting (and fail downstream on the missing API key
    # check with 500); requests 4 and 5 are rejected by the limiter itself.
    assert statuses[:3] == [500, 500, 500]
    assert statuses[3:] == [429, 429]


async def test_apollo_rate_limit_is_scoped_per_tenant(client, monkeypatch):
    """One tenant hitting its limit must not affect another tenant's quota."""
    monkeypatch.setattr(settings, "APOLLO_API_KEY", None)
    monkeypatch.setattr(settings, "APOLLO_RATE_LIMIT_PER_MINUTE", 1)

    first_tenant_headers = bearer_for("org_apollo_a")
    second_tenant_headers = bearer_for("org_apollo_b")

    r1 = await client.post(APOLLO_SEARCH, json={}, headers=first_tenant_headers)
    r2 = await client.post(APOLLO_SEARCH, json={}, headers=first_tenant_headers)  # exceeds org_apollo_a's limit
    r3 = await client.post(APOLLO_SEARCH, json={}, headers=second_tenant_headers)  # org_apollo_b's first request

    assert r1.status_code == 500
    assert r2.status_code == 429
    assert r3.status_code == 500  # unaffected by org_apollo_a's limit
