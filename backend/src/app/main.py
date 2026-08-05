import asyncio
import logging
import os
import sys

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from asgi_correlation_id import CorrelationIdMiddleware, correlation_id
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.analytics import router as analytics_router
from app.api.v1.apollo import router as apollo_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.health import router as health_router
from app.api.v1.icp import router as icp_router
from app.api.v1.linkedin import router as linkedin_router
from app.api.v1.memory import router as memory_router
from app.api.v1.prospects import router as prospects_router
from app.api.v1.sequences import router as sequences_router
from app.api.v1.signals import router as signals_router
from app.api.v1.voice import router as voice_router
from app.api.v1.webhooks import router as webhooks_router
from app.config import settings
from app.workers.main import WorkerSettings

# Fixed, arbitrary key: any process applying migrations coordinates through
# this single Postgres advisory lock so concurrent instances can't race
# running the same migration on boot.
_MIGRATION_ADVISORY_LOCK_KEY = 727401

def _run_alembic_upgrade_head():
    """Blocking; must run off the event loop thread (see run_in_executor
    below), since Alembic's own env.py drives its async engine via
    asyncio.run(), which cannot be called from a thread with a running loop."""
    from alembic.config import Config

    from alembic import command
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

async def apply_pending_migrations():
    """Applies any pending Alembic migrations, guarded by a Postgres
    advisory lock."""
    import asyncpg
    dsn = settings.DATABASE_ASYNC_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", _MIGRATION_ADVISORY_LOCK_KEY)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run_alembic_upgrade_head)
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_ADVISORY_LOCK_KEY)
        await conn.close()

# Configure Structlog
def setup_logging():
    # structlog.stdlib.LoggerFactory() (below) routes every structlog call
    # through Python's stdlib logging module - which, unconfigured, has no
    # handler on the root logger and defaults to WARNING, so every .info()
    # call in the app is silently dropped. basicConfig gives it a stdout
    # handler at INFO; format is the bare message only, since structlog's own
    # processors (below) already render level/timestamp/logger name into
    # that message - stdlib's default format would duplicate them.
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")

    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
        # Add correlation ID to logs
        lambda logger, log_method, event_dict: {**event_dict, "correlation_id": correlation_id.get()}
    ]

    if settings.ENVIRONMENT == "production":
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

setup_logging()
logger = structlog.get_logger(__name__)

app = FastAPI(
    title="ApexSDR Backend Workflow Engine",
    description="Multi-tenant, idempotent asynchronous sales outreach state machine.",
    version="1.0.0"
)

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

# Add correlation ID middleware
app.add_middleware(CorrelationIdMiddleware)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Baseline OWASP-recommended response headers - this app is an API
    (no server-rendered HTML), so CSP is locked to default-src 'none'."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

# Initialize Prometheus Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.on_event("startup")
async def startup_db_initialization():
    """
    Applies pending database migrations upon application startup.
    """
    logger.info("Applying pending database migrations...")
    retries = 5
    for attempt in range(retries):
        try:
            await apply_pending_migrations()
            logger.info("Database migrations applied successfully.")
            break
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                logger.error("Could not connect to database after maximum retries.")
                raise
            await asyncio.sleep(2)

    logger.info("Creating shared ARQ Redis pool...")
    app.state.arq_redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))

    logger.info("Starting embedded background worker for AI Pipeline...")
    worker = Worker(
        functions=WorkerSettings.functions,
        cron_jobs=WorkerSettings.cron_jobs,
        redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown
    )
    # Save a strong reference to prevent Python's garbage collector from destroying the worker
    app.state.worker_task = asyncio.create_task(worker.main())

    # Start a background task to update queue depth metric
    async def poll_queue_depth():
        from app.database import redis_client
        from app.services.metrics.service import queue_depth
        while True:
            try:
                # ARQ's queue is a sorted set (job_id -> score), not a list -
                # llen() would raise WRONGTYPE on it (silently swallowed by
                # the except below, which is why this metric was previously
                # always stuck at its initial value).
                length = await redis_client.zcard('arq:queue')
                queue_depth.set(length)
            except Exception:
                pass
            await asyncio.sleep(10)
            
    app.state.queue_depth_task = asyncio.create_task(poll_queue_depth())

@app.on_event("shutdown")
async def shutdown_shared_resources():
    """Closes the shared ARQ Redis pool created at startup."""
    pool = getattr(app.state, "arq_redis", None)
    if pool is not None:
        await pool.close()

# Register routing paths under Version 1 scope
app.include_router(health_router, prefix="/api/v1")
app.include_router(prospects_router, prefix="/api/v1")
app.include_router(campaigns_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(icp_router, prefix="/api/v1")
app.include_router(sequences_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(apollo_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")
app.include_router(linkedin_router, prefix="/api/v1")
app.include_router(decisions_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(signals_router, prefix="/api/v1")
