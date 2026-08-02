import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_tenant
from app.core.circuit_breaker import CircuitBreaker
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])

@router.get("", status_code=status.HTTP_200_OK)
async def check_health_status():
    """Standard deployment load balancer health check."""
    return {"status": "healthy", "service": "api_gateway"}

@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness():
    """K8s liveness probe."""
    return {"status": "alive"}

@router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness(request: Request, db: AsyncSession = Depends(get_db)):
    """K8s readiness probe. Checks database and redis (via the single
    shared ARQ pool on app.state, rather than opening a new connection pool
    just to ping it)."""
    readiness_status = {"db": "down", "redis": "down"}

    # Check Postgres
    try:
        await db.execute(text("SELECT 1"))
        readiness_status["db"] = "up"
    except Exception as e:
        logger.error(f"Readiness check DB failed: {e}")

    # Check Redis
    try:
        pool = getattr(request.app.state, "arq_redis", None)
        if pool is None:
            raise RuntimeError("ARQ Redis pool not initialized on app.state.arq_redis")
        await pool.ping()
        readiness_status["redis"] = "up"
    except Exception as e:
        logger.error(f"Readiness check Redis failed: {e}")

    if readiness_status["db"] == "up" and readiness_status["redis"] == "up":
        return {"status": "ready", "dependencies": readiness_status}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"status": "not_ready", "dependencies": readiness_status})

@router.get("/providers", status_code=status.HTTP_200_OK)
async def provider_health(tenant_id: str = Depends(verify_tenant)):
    """Module 12 (Provider Health): exposes each provider's circuit-breaker
    state and consecutive-failure count. Authenticated (unlike the plain
    liveness/readiness probes above) since this is operational detail about
    third-party integrations, not a load-balancer check."""
    return {"providers": CircuitBreaker.get_all_status()}
