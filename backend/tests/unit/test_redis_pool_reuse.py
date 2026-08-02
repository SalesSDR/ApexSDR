import pytest

import app.services.analytics.service as analytics_service
from app.database import get_arq_pool
from app.services.analytics.service import AnalyticsService


class _FakeAppState:
    def __init__(self, arq_redis=None):
        self.arq_redis = arq_redis


class _FakeApp:
    def __init__(self, arq_redis=None):
        self.state = _FakeAppState(arq_redis)


class _FakeRequest:
    def __init__(self, app):
        self.app = app


class _FakePool:
    """Stands in for an ArqRedis instance - identity (`is`) is what these
    tests check, not behavior."""


async def test_get_arq_pool_returns_the_same_shared_instance_across_calls():
    pool = _FakePool()
    request = _FakeRequest(_FakeApp(arq_redis=pool))

    first = await get_arq_pool(request)
    second = await get_arq_pool(request)

    assert first is pool
    assert second is pool
    assert first is second  # same object, not a fresh one per call


async def test_get_arq_pool_raises_clearly_when_app_state_never_initialized():
    request = _FakeRequest(_FakeApp(arq_redis=None))
    with pytest.raises(RuntimeError, match="not initialized"):
        await get_arq_pool(request)


async def test_analytics_service_reuses_injected_pool_instead_of_opening_a_new_one(monkeypatch):
    """Regression test for the ad hoc `create_pool()` call this service used
    to make on every /metrics/queue request - when a shared pool is
    injected, create_pool must never be called."""
    calls = []

    async def _fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("create_pool() should not be called when a shared arq_pool was injected")

    monkeypatch.setattr(analytics_service, "create_pool", _fail_if_called)

    class _FakePoolWithQueuedJobs:
        async def queued_jobs(self):
            return []

    class _FakeDB:
        async def execute(self, *args, **kwargs):
            class _Result:
                def scalars(self_inner):
                    class _S:
                        def all(self_inner2):
                            return []
                    return _S()
            return _Result()

    service = AnalyticsService(db=_FakeDB(), tenant_id="tenant_reuse", arq_pool=_FakePoolWithQueuedJobs())
    result = await service.queue_metrics()

    assert calls == []  # create_pool never invoked
    assert result["arq_pending_jobs_total"] == 0


async def test_analytics_service_falls_back_to_ad_hoc_pool_when_none_injected(monkeypatch):
    """Backward-compatibility check: existing callers that don't pass
    arq_pool (e.g. other unit tests constructing AnalyticsService(db, tenant))
    keep working exactly as before."""
    created = []

    class _FakeAdHocPool:
        async def queued_jobs(self):
            return []

        async def close(self):
            created.append("closed")

    async def _fake_create_pool(*args, **kwargs):
        created.append("created")
        return _FakeAdHocPool()

    monkeypatch.setattr(analytics_service, "create_pool", _fake_create_pool)

    class _FakeDB:
        async def execute(self, *args, **kwargs):
            class _Result:
                def scalars(self_inner):
                    class _S:
                        def all(self_inner2):
                            return []
                    return _S()
            return _Result()

    service = AnalyticsService(db=_FakeDB(), tenant_id="tenant_fallback")  # no arq_pool
    await service.queue_metrics()

    assert created == ["created", "closed"]
