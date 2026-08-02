"""Sprint 4, item 1 ("Implement configurable scoring"): PUT
/campaigns/settings lets a tenant configure its ICP profile and
qualification-scoring weights/thresholds, which score_prospect() then
actually reads (see tests/unit/test_qualification_scoring.py)."""
from tests.conftest import bearer_for


async def test_update_workspace_settings_persists_icp_profile_and_qualification_config(client):
    payload = {
        "icp_profile": {"target_industries": ["Fintech"], "target_job_titles": ["VP", "Director"]},
        "qualification_config": {"thresholds": {"medium": 20.0}},
    }
    response = await client.put(
        "/api/v1/campaigns/settings", json=payload, headers=bearer_for("org_qual_config")
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["icp_profile"] == payload["icp_profile"]
    assert data["qualification_config"] == payload["qualification_config"]


async def test_update_workspace_settings_without_qualification_fields_leaves_them_at_defaults(client):
    response = await client.put(
        "/api/v1/campaigns/settings", json={"timezone": "America/New_York"}, headers=bearer_for("org_qual_config_2")
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["icp_profile"] == {}
    assert data["qualification_config"] == {}
