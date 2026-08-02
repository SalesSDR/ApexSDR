"""Sprint 6.1: verify_tenant_sse is verify_tenant's identical authenticator
(same JWTAuthProvider/APIKeyAuthProvider, same failure semantics) with one
extra credential source - a `token` query param - since the browser-native
EventSource it exists for cannot set an Authorization header."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.v1.auth import verify_tenant_sse
from tests.conftest import bearer_for


def _bearer_credentials(tenant_id: str) -> HTTPAuthorizationCredentials:
    token = bearer_for(tenant_id)["Authorization"].removeprefix("Bearer ")
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def test_accepts_credential_via_authorization_header():
    tenant_id = await verify_tenant_sse(credentials=_bearer_credentials("org_sse_header"), token=None)
    assert tenant_id == "org_sse_header"


async def test_accepts_credential_via_token_query_param():
    token = bearer_for("org_sse_query")["Authorization"].removeprefix("Bearer ")
    tenant_id = await verify_tenant_sse(credentials=None, token=token)
    assert tenant_id == "org_sse_query"


async def test_header_takes_precedence_over_query_param_when_both_present():
    header_creds = _bearer_credentials("org_sse_header_wins")
    other_token = bearer_for("org_sse_ignored")["Authorization"].removeprefix("Bearer ")
    tenant_id = await verify_tenant_sse(credentials=header_creds, token=other_token)
    assert tenant_id == "org_sse_header_wins"


async def test_rejects_when_neither_header_nor_query_param_present():
    with pytest.raises(HTTPException) as exc_info:
        await verify_tenant_sse(credentials=None, token=None)
    assert exc_info.value.status_code == 401


async def test_rejects_an_invalid_query_param_token():
    with pytest.raises(HTTPException) as exc_info:
        await verify_tenant_sse(credentials=None, token="not-a-real-credential")
    assert exc_info.value.status_code == 401
