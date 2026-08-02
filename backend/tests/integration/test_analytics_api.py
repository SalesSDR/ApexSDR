from app.models.schemas import Prospect, ProspectState
from tests.conftest import bearer_for

ENDPOINTS = [
    "/api/v1/analytics/metrics/funnel",
    "/api/v1/analytics/metrics/prospects-by-state",
    "/api/v1/analytics/metrics/outreach",
    "/api/v1/analytics/metrics/linkedin",
    "/api/v1/analytics/metrics/email",
    "/api/v1/analytics/metrics/calls",
    "/api/v1/analytics/metrics/crm-sync",
    "/api/v1/analytics/metrics/calendar",
    "/api/v1/analytics/metrics/queue",
    "/api/v1/analytics/metrics/retry",
    "/api/v1/analytics/metrics/activity",
    "/api/v1/analytics/metrics/failed-jobs",
    "/api/v1/analytics/metrics/conversion",
    "/api/v1/analytics/metrics/response-times",
]


async def test_every_metrics_endpoint_returns_success_envelope(client):
    for path in ENDPOINTS:
        response = await client.get(path, headers=bearer_for("org_api_test"))
        assert response.status_code == 200, f"{path} returned {response.status_code}: {response.text}"
        body = response.json()
        assert body["status"] == "success"
        assert "data" in body


async def test_activity_endpoint_accepts_period_and_days_params(client):
    response = await client.get(
        "/api/v1/analytics/metrics/activity",
        params={"period": "weekly", "days": "7"},
        headers=bearer_for("org_api_test"),
    )
    assert response.status_code == 200
    assert response.json()["data"]["period"] == "weekly"


async def test_activity_endpoint_rejects_invalid_period(client):
    response = await client.get(
        "/api/v1/analytics/metrics/activity",
        params={"period": "monthly"},
        headers=bearer_for("org_api_test"),
    )
    assert response.status_code == 422  # FastAPI Query pattern validation


async def test_metrics_are_scoped_per_tenant(client, db_session):
    db_session.add(Prospect(
        tenant_id="org_tenant_x", first_name="X", last_name="Only",
        linkedin_url="https://linkedin.com/in/tenant-x", status=ProspectState.MEETING_BOOKED,
    ))
    await db_session.flush()

    response_x = await client.get(
        "/api/v1/analytics/metrics/prospects-by-state", headers=bearer_for("org_tenant_x")
    )
    response_y = await client.get(
        "/api/v1/analytics/metrics/prospects-by-state", headers=bearer_for("org_tenant_y")
    )

    assert response_x.json()["data"]["by_state"][ProspectState.MEETING_BOOKED.value] == 1
    assert response_y.json()["data"]["by_state"][ProspectState.MEETING_BOOKED.value] == 0
