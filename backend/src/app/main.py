import logging
import asyncio
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.prospects import router as prospects_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.n8n_webhooks import router as n8n_router
from app.api.v1.icp import router as icp_router
from app.api.v1.sequences import router as sequences_router
from app.api.v1.apollo import router as apollo_router
from app.api.v1.twilio_webhooks import router as twilio_router
from app.api.v1.analytics import router as analytics_router
from app.database import engine
from app.models.base import Base
from arq.worker import Worker
from app.workers.main import WorkerSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ApexSDR Backend Workflow Engine",
    description="Multi-tenant, idempotent asynchronous sales outreach state machine.",
    version="1.0.0"
)

import os

allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://apex-sdr-i9xg.vercel.app")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
# If wildcard is used, some browsers reject allow_credentials=True. 
# We explicitly allow the vercel app.
if "*" in allowed_origins:
    allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "https://apex-sdr-i9xg.vercel.app"]

# Enable CORS for standard frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
    retries = 5
    for attempt in range(retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schemas creation completed successfully.")
            break
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                logger.error("Could not connect to database after maximum retries.")
                raise
            await asyncio.sleep(2)
            
    logger.info("Starting embedded background worker for AI Pipeline...")
    worker = Worker(
        functions=WorkerSettings.functions,
        cron_jobs=WorkerSettings.cron_jobs,
        redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        on_job_error=WorkerSettings.on_job_error
    )
    asyncio.create_task(worker.main())

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
app.include_router(sequences_router, prefix="/api/v1")
app.include_router(apollo_router, prefix="/api/v1")
app.include_router(n8n_router, prefix="/api/v1/webhooks")
app.include_router(twilio_router, prefix="/api/v1/webhooks")
app.include_router(analytics_router, prefix="/api/v1")
