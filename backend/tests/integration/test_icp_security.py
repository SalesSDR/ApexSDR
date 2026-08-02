from app.config import settings
from tests.conftest import bearer_for

ICP_PARSE = "/api/v1/icp/parse"
ICP_PREVIEW = "/api/v1/icp/preview"


async def test_icp_parse_requires_authentication(client):
    response = await client.post(ICP_PARSE, json={"query": "VP of Engineering in London"})
    assert response.status_code == 401


async def test_icp_preview_requires_authentication(client):
    response = await client.post(ICP_PREVIEW, json={"prompt": "find CTOs at fintech startups"})
    assert response.status_code == 401


async def test_icp_parse_authenticated_request_succeeds(client):
    """parse_icp_query has a graceful fallback path, so an authenticated
    request succeeds (200) even without a real Gemini key configured -
    what this test proves is that auth is not the blocker."""
    response = await client.post(
        ICP_PARSE, json={"query": "VP of Engineering in London"}, headers=bearer_for("org_icp_1")
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


async def test_icp_preview_authenticated_request_is_not_rejected_by_auth(client, monkeypatch):
    """Unlike parse, preview fails closed on missing config (no fallback) -
    with no UNIPILE_API_KEY configured, an authenticated request still
    fails, but with 500 from the missing-key check, not 401."""
    monkeypatch.setattr(settings, "UNIPILE_API_KEY", None)
    response = await client.post(
        ICP_PREVIEW, json={"prompt": "find CTOs at fintech startups"}, headers=bearer_for("org_icp_2")
    )
    assert response.status_code == 500
    assert response.status_code != 401


async def test_icp_preview_is_rate_limited_per_tenant(client, monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_API_KEY", None)
    monkeypatch.setattr(settings, "ICP_RATE_LIMIT_PER_MINUTE", 2)
    headers = bearer_for("org_icp_rate_limited")

    statuses = []
    for _ in range(4):
        response = await client.post(ICP_PREVIEW, json={"prompt": "find CTOs"}, headers=headers)
        statuses.append(response.status_code)

    assert statuses[:2] == [500, 500]
    assert statuses[2:] == [429, 429]


async def test_icp_rate_limit_is_scoped_per_tenant(client, monkeypatch):
    monkeypatch.setattr(settings, "UNIPILE_API_KEY", None)
    monkeypatch.setattr(settings, "ICP_RATE_LIMIT_PER_MINUTE", 1)

    tenant_a_headers = bearer_for("org_icp_a")
    tenant_b_headers = bearer_for("org_icp_b")

    r1 = await client.post(ICP_PREVIEW, json={"prompt": "x"}, headers=tenant_a_headers)
    r2 = await client.post(ICP_PREVIEW, json={"prompt": "x"}, headers=tenant_a_headers)  # exceeds org_icp_a's limit
    r3 = await client.post(ICP_PREVIEW, json={"prompt": "x"}, headers=tenant_b_headers)  # org_icp_b's first request

    assert r1.status_code == 500
    assert r2.status_code == 429
    assert r3.status_code == 500  # unaffected by org_icp_a's limit
