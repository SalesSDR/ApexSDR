from app.models.schemas import Prospect, ProspectState
from tests.conftest import bearer_for


async def test_create_and_list_memory(client, db_session):
    prospect = Prospect(
        tenant_id="org_memory_api", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-memory-api",
        email="memtest@example.com", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    payload = {
        "memory_type": "OBJECTION",
        "content": "Not interested right now.",
        "importance_score": 8,
        "is_resolved": False,
        "source": "LINKEDIN",
    }
    headers = bearer_for("org_memory_api")

    response = await client.post(f"/api/v1/prospects/{prospect.id}/memory", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["memory_type"] == "OBJECTION"
    assert data["content"] == payload["content"]
    assert data["id"] is not None

    response = await client.get(f"/api/v1/prospects/{prospect.id}/memory", headers=headers)
    assert response.status_code == 200
    list_data = response.json()
    assert list_data["status"] == "success"
    assert len(list_data["data"]) == 1
    assert list_data["data"][0]["memory_type"] == "OBJECTION"


async def test_create_memory_404s_for_a_prospect_outside_the_tenant(client, db_session):
    prospect = Prospect(
        tenant_id="org_memory_other", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-memory-api", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/prospects/{prospect.id}/memory",
        json={"memory_type": "OBJECTION", "content": "x", "source": "SYSTEM"},
        headers=bearer_for("org_memory_api"),
    )
    assert response.status_code == 404
