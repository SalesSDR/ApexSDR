
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import (
    AuthenticationError,
    build_default_authenticator,
    set_current_tenant,
)

security_bearer = HTTPBearer(auto_error=False)


async def verify_tenant(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> str:
    """
    Verifies the caller's bearer credential (JWT or API key) and returns the
    tenant_id it resolves to.

    Tenant identity comes ONLY from a successfully verified credential -
    never from a header, query parameter, or request body - and there is no
    default/fallback tenant. Any missing, malformed, unsigned, or expired
    credential is rejected with 401.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        identity = build_default_authenticator().authenticate(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    set_current_tenant(identity.tenant_id)
    return identity.tenant_id


async def verify_tenant_sse(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    token: str | None = None,
) -> str:
    """
    Same verification as verify_tenant() - the identical JWT/API-key
    authenticator, no separate mechanism - but also accepts the credential
    via a `token` query parameter as a fallback.

    This exists only for the SSE endpoint: the browser-native EventSource
    API cannot set an Authorization header, so the credential has nowhere
    else to travel for that one transport. Every other endpoint must keep
    using verify_tenant (header-only).
    """
    credential = credentials.credentials if credentials is not None else token
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        identity = build_default_authenticator().authenticate(credential)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    set_current_tenant(identity.tenant_id)
    return identity.tenant_id
