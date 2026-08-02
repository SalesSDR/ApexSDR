from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from arq.connections import ArqRedis
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Create async engine with robust pool configuration
engine = create_async_engine(
    settings.DATABASE_ASYNC_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Redis client connection pool
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding db session with error-handling/rollback.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """
    FastAPI dependency yielding Redis client.
    """
    yield redis_client


async def get_arq_pool(request: Request) -> ArqRedis:
    """
    Returns the single shared ARQ Redis pool created once at app startup
    (see app.main's startup handler) instead of opening a new connection
    pool per request/job-enqueue - every route that previously called
    `await create_pool(...)` ad hoc now takes this dependency instead.
    """
    pool = getattr(request.app.state, "arq_redis", None)
    if pool is None:
        raise RuntimeError(
            "ARQ Redis pool is not initialized on app.state.arq_redis. "
            "Ensure the app startup handler has run (or a test fixture has "
            "set app.state.arq_redis) before handling requests."
        )
    return pool

