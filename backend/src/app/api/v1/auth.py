from typing import Optional
from fastapi import Header, Query, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import set_current_tenant

security_bearer = HTTPBearer(auto_error=False)

async def verify_tenant(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    query_tenant_id: Optional[str] = Query(None, alias="tenant_id")
) -> str:
    """
    Extracts tenant context from either JWT credentials, header parameter, or query param.
    Injects it into the request context lifecycle.
    """
    tenant_id = x_tenant_id or query_tenant_id
    
    if credentials:
        token = credentials.credentials
        # Check if the token acts as a dummy/mock organization tenant ID
        if token.startswith("org_"):
            tenant_id = token

    if not tenant_id:
        # Fallback for local development if no auth headers are provided
        tenant_id = "tenant_1"

    # Set current tenant ID in ContextVar for RLS-like logic
    set_current_tenant(tenant_id)
    return tenant_id
