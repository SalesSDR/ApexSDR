import os

# The test database/redis targets must be set BEFORE any `app.*` module is
# imported, since app.config.settings and app.database.engine/redis_client
# are constructed at import time from environment variables.
TEST_DATABASE_ASYNC_URL = os.environ.setdefault(
    "TEST_DATABASE_ASYNC_URL",
    "postgresql+asyncpg://sdr_admin:SECURE_VAULT_PW@localhost:5433/apex_sdr_test",
)
TEST_REDIS_URL = os.environ.setdefault(
    "TEST_REDIS_URL",
    "redis://:STRONG_AUTH_TOKEN@localhost:6380/15",
)

# Safety guards: refuse to run against anything that looks like production.
_test_db_name = TEST_DATABASE_ASYNC_URL.rsplit("/", 1)[-1].split("?", 1)[0].lower()
if "test" not in _test_db_name:
    raise RuntimeError(
        "TEST_DATABASE_ASYNC_URL must point at a database with 'test' in its name "
        f"to avoid running destructive schema operations against real data. Got: "
        f"{TEST_DATABASE_ASYNC_URL!r}"
    )
_test_redis_db_index = TEST_REDIS_URL.rsplit("/", 1)[-1]
if _test_redis_db_index in ("0", ""):
    raise RuntimeError(
        "TEST_REDIS_URL must use a Redis db index other than 0 (the app's default) "
        f"to avoid flushing real data. Got: {TEST_REDIS_URL!r}"
    )

os.environ["DATABASE_ASYNC_URL"] = TEST_DATABASE_ASYNC_URL
os.environ["REDIS_URL"] = TEST_REDIS_URL
os.environ.setdefault("ENVIRONMENT", "test")

# Auth/webhook secrets must also be set before any `app.*` import, since
# app.config.settings is a module-level singleton constructed at import
# time. These are test-only values - never used outside this suite.
TEST_JWT_SECRET_KEY = os.environ.setdefault("SECRET_KEY", "test-only-jwt-secret-do-not-use-in-production")
TEST_UNIPILE_WEBHOOK_SECRET = os.environ.setdefault("UNIPILE_WEBHOOK_SECRET", "test-only-unipile-webhook-secret")
TEST_TWILIO_AUTH_TOKEN = os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-only-twilio-auth-token")

import asyncio  # noqa: E402
import time  # noqa: E402

import pytest_asyncio  # noqa: E402
import redis.asyncio as aioredis  # noqa: E402
from arq import create_pool  # noqa: E402
from arq.connections import RedisSettings  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from jose import jwt as jose_jwt  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.database import get_db, get_redis  # noqa: E402
from app.main import app  # noqa: E402


def bearer_for(tenant_id: str, **extra_claims) -> dict:
    """Mints a real, signed JWT for `tenant_id` (1 hour expiry) and returns
    it as an Authorization header dict - the test-suite equivalent of
    whatever a login/token-issuance service would hand out in production.
    Replaces the old insecure convention of sending a raw "Bearer org_xxx"
    string and having the server trust it verbatim."""
    payload = {"tenant_id": tenant_id, "iat": int(time.time()), "exp": int(time.time()) + 3600, **extra_claims}
    token = jose_jwt.encode(payload, TEST_JWT_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

_ALEMBIC_INI_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")


def _alembic_upgrade_head():
    from alembic.config import Config

    from alembic import command
    command.upgrade(Config(_ALEMBIC_INI_PATH), "head")


def _alembic_downgrade_base():
    from alembic.config import Config

    from alembic import command
    command.downgrade(Config(_ALEMBIC_INI_PATH), "base")


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Session-scoped engine against the isolated test database. Runs the
    real Alembic migration chain once (so the suite validates the migration
    path itself, not just the current model definitions), tears it down at
    the end of the run."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _alembic_upgrade_head)
    engine = create_async_engine(TEST_DATABASE_ASYNC_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()
    await loop.run_in_executor(None, _alembic_downgrade_base)


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Each test runs inside its own connection + transaction, rolled back
    at teardown so tests never see each other's data."""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(bind=connection, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def redis_test_client():
    client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def arq_test_pool():
    """A single, real ARQ pool against the isolated test Redis - the test
    equivalent of the one shared app.state.arq_redis pool created at
    startup in app.main (see app.database.get_arq_pool)."""
    pool = await create_pool(RedisSettings.from_dsn(TEST_REDIS_URL))
    try:
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture
async def client(db_session, redis_test_client, arq_test_pool):
    """Async HTTP client against the FastAPI app with DB/Redis dependencies
    swapped for the isolated test fixtures above. Uses a bare ASGITransport
    (no lifespan), so the app's startup event - which would create schema via
    create_all and spin up the embedded ARQ worker - never runs here. The
    shared ARQ pool is set directly on app.state, matching how the real
    startup handler wires it, since app.database.get_arq_pool reads it from
    there rather than via an overridable dependency."""

    async def _get_db_override():
        yield db_session

    async def _get_redis_override():
        yield redis_test_client

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_redis] = _get_redis_override
    app.state.arq_redis = arq_test_pool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    app.state.arq_redis = None
