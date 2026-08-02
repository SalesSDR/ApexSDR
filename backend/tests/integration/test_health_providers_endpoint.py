"""Sprint 3, item 4: provider health must be exposed, not just tracked
internally. GET /api/v1/health/providers is authenticated (unlike the plain
liveness/readiness probes) since it's operational detail about third-party
integrations."""
import pytest

from app.core.circuit_breaker import CircuitBreaker
from tests.conftest import bearer_for


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    CircuitBreaker.reset_all()
    yield
    CircuitBreaker.reset_all()


async def test_requires_authentication(client):
    response = await client.get("/api/v1/health/providers")
    assert response.status_code in (401, 403)


async def test_lists_every_named_provider(client):
    response = await client.get("/api/v1/health/providers", headers=bearer_for("org_health_check"))
    assert response.status_code == 200
    providers = {row["provider"] for row in response.json()["providers"]}
    for expected in ("HUBSPOT", "GOOGLE", "RESEND", "LINKEDIN", "GEMINI", "APOLLO"):
        assert expected in providers


async def test_reflects_an_open_circuit(client):
    CircuitBreaker.configure("HUBSPOT", failure_threshold=1)
    CircuitBreaker.record_failure("HUBSPOT")

    response = await client.get("/api/v1/health/providers", headers=bearer_for("org_health_check"))
    rows = {row["provider"]: row for row in response.json()["providers"]}
    assert rows["HUBSPOT"]["state"] == "OPEN"
    assert rows["HUBSPOT"]["consecutive_failures"] == 1
