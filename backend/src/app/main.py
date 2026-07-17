import logging
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.prospects import router as prospects_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.icp import router as icp_router
from app.database import engine
from app.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ApexSDR Backend Workflow Engine",
    description="Multi-tenant, idempotent asynchronous sales outreach state machine.",
    version="1.0.0"
)

# Enable CORS for standard frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_initialization():
    """
    Ensures relational schemas exist upon application startup.
    """
    logger.info("Initializing relational database models...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schemas creation completed successfully.")

@app.get("/health", status_code=status.HTTP_200_OK)
async def check_health_status():
    """
    Standard deployment load balancer health check.
    """
    return {"status": "healthy", "service": "api_gateway"}

# Register routing paths under Version 1 scope
app.include_router(prospects_router, prefix="/api/v1")
app.include_router(campaigns_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(icp_router, prefix="/api/v1")
