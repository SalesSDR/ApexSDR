import time

from jose import jwt as jose_jwt

from app.config import settings
from app.models.schemas import Prospect, ProspectState
from tests.conftest import TEST_JWT_SECRET_KEY, bearer_for

PROTECTED_GET = "/api/v1/prospects"


# --- Authentication: missing / malformed / expired / tampered credentials ---

async def test_missing_authorization_header_is_rejected(client):
    response = await client.get(PROTECTED_GET)
    assert response.status_code == 401


async def test_malformed_bearer_credential_is_rejected(client):
    response = await client.get(
        PROTECTED_GET, headers={"Authorization": "Bearer this-is-not-a-jwt-and-not-a-registered-key"}
    )
    assert response.status_code == 401


async def test_expired_jwt_is_rejected(client):
    expired_token = jose_jwt.encode(
        {"tenant_id": "org_expired", "exp": int(time.time()) - 60},
        TEST_JWT_SECRET_KEY,
        algorithm="HS256",
    )
    response = await client.get(PROTECTED_GET, headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


async def test_jwt_signed_with_wrong_secret_is_rejected(client):
    forged_token = jose_jwt.encode(
        {"tenant_id": "org_forged", "exp": int(time.time()) + 3600},
        "not-the-real-secret",
        algorithm="HS256",
    )
    response = await client.get(PROTECTED_GET, headers={"Authorization": f"Bearer {forged_token}"})
    assert response.status_code == 401


async def test_jwt_without_tenant_id_claim_is_rejected(client):
    token = jose_jwt.encode({"exp": int(time.time()) + 3600}, TEST_JWT_SECRET_KEY, algorithm="HS256")
    response = await client.get(PROTECTED_GET, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_valid_jwt_is_accepted(client):
    response = await client.get(PROTECTED_GET, headers=bearer_for("org_valid_jwt"))
    assert response.status_code == 200


async def test_valid_api_key_is_accepted(client, monkeypatch):
    monkeypatch.setattr(settings, "TENANT_API_KEYS", "sk_test_key_001:org_via_api_key")
    response = await client.get(
        PROTECTED_GET, headers={"Authorization": "Bearer sk_test_key_001"}
    )
    assert response.status_code == 200


async def test_unregistered_api_key_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "TENANT_API_KEYS", "sk_test_key_001:org_via_api_key")
    response = await client.get(
        PROTECTED_GET, headers={"Authorization": "Bearer sk_not_in_registry"}
    )
    assert response.status_code == 401


# --- Tenant isolation: identity comes ONLY from the verified credential ---

async def test_tenant_id_query_param_is_ignored_after_authentication(client, db_session):
    """A caller authenticated as org_a must never be able to read org_b's
    data by simply appending ?tenant_id=org_b - tenant_id is not even a
    declared parameter of the endpoint anymore, so FastAPI has nothing to
    bind it to; this asserts the *data returned* still reflects org_a."""
    db_session.add(Prospect(
        tenant_id="org_a", first_name="A", last_name="Only", email="a-only@example.com",
        linkedin_url="https://linkedin.com/in/org-a-only", status=ProspectState.IDLE,
    ))
    db_session.add(Prospect(
        tenant_id="org_b", first_name="B", last_name="Only", email="b-only@example.com",
        linkedin_url="https://linkedin.com/in/org-b-only", status=ProspectState.IDLE,
    ))
    await db_session.flush()

    response = await client.get(
        f"{PROTECTED_GET}?tenant_id=org_b", headers=bearer_for("org_a")
    )
    assert response.status_code == 200
    names = {p["first_name"] for p in response.json()["data"]}
    assert names == {"A"}  # never leaks org_b's row


async def test_x_tenant_id_header_is_ignored_after_authentication(client, db_session):
    db_session.add(Prospect(
        tenant_id="org_a2", first_name="A2", last_name="Only", email="a2-only@example.com",
        linkedin_url="https://linkedin.com/in/org-a2-only", status=ProspectState.IDLE,
    ))
    db_session.add(Prospect(
        tenant_id="org_b2", first_name="B2", last_name="Only", email="b2-only@example.com",
        linkedin_url="https://linkedin.com/in/org-b2-only", status=ProspectState.IDLE,
    ))
    await db_session.flush()

    headers = bearer_for("org_a2")
    headers["X-Tenant-ID"] = "org_b2"
    response = await client.get(PROTECTED_GET, headers=headers)

    assert response.status_code == 200
    names = {p["first_name"] for p in response.json()["data"]}
    assert names == {"A2"}


async def test_two_tenants_never_see_each_others_data(client, db_session):
    db_session.add(Prospect(
        tenant_id="org_iso_1", first_name="One", last_name="Tenant", email="one-tenant@example.com",
        linkedin_url="https://linkedin.com/in/org-iso-1", status=ProspectState.IDLE,
    ))
    db_session.add(Prospect(
        tenant_id="org_iso_2", first_name="Two", last_name="Tenant", email="two-tenant@example.com",
        linkedin_url="https://linkedin.com/in/org-iso-2", status=ProspectState.IDLE,
    ))
    await db_session.flush()

    resp_1 = await client.get(PROTECTED_GET, headers=bearer_for("org_iso_1"))
    resp_2 = await client.get(PROTECTED_GET, headers=bearer_for("org_iso_2"))

    names_1 = {p["first_name"] for p in resp_1.json()["data"]}
    names_2 = {p["first_name"] for p in resp_2.json()["data"]}
    assert names_1 == {"One"}
    assert names_2 == {"Two"}


# --- compliance.py / voice.py / sequences.py: previously bare tenant_id params ---

async def test_compliance_status_requires_auth_not_a_query_param(client):
    response = await client.get("/api/v1/compliance/status")
    assert response.status_code == 401


async def test_compliance_status_ignores_tenant_id_query_param(client):
    response = await client.get(
        "/api/v1/compliance/status?tenant_id=someone_elses_tenant", headers=bearer_for("org_compliance")
    )
    assert response.status_code == 200


async def test_voice_conversations_requires_auth(client):
    response = await client.get("/api/v1/voice/conversations")
    assert response.status_code == 401


async def test_sequences_current_requires_auth(client):
    response = await client.get("/api/v1/sequences/current")
    assert response.status_code == 401
