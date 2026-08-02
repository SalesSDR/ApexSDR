"""Sprint 6.1: /prospects/stream authenticates via verify_tenant_sse instead
of verify_tenant, because the browser-native EventSource powering it cannot
set an Authorization header - the credential falls back to a `token` query
param for this one endpoint.

The 401 paths below use a plain (non-streaming) request: FastAPI evaluates
the Depends() and raises before the route body - and therefore before the
StreamingResponse - ever runs, so these return an ordinary JSON error and
complete immediately. The accept paths are covered directly against
verify_tenant_sse itself (tests/unit/test_verify_tenant_sse.py) rather than
through the live endpoint, since the endpoint's generator runs forever and
has nothing to do with credential extraction."""

STREAM_URL = "/api/v1/prospects/stream"


async def test_stream_requires_a_credential(client):
    response = await client.get(STREAM_URL)
    assert response.status_code == 401


async def test_stream_rejects_an_invalid_token_query_param(client):
    response = await client.get(f"{STREAM_URL}?token=not-a-real-credential")
    assert response.status_code == 401
