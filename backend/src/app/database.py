import redis.asyncio as aioredis
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
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

