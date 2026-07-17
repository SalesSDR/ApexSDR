from contextvars import ContextVar
from typing import Optional

# Global context tracking for multi-tenant isolation
tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)

def get_current_tenant() -> Optional[str]:
    """
    Get the currently active tenant ID from context.
    """
    return tenant_context.get()

def set_current_tenant(tenant_id: str):
    """
    Set the currently active tenant ID in context.
    """
    return tenant_context.set(tenant_id)
