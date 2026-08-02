"""Integration coverage for the generic read-through cache helper
(app.core.cache) against a real Redis instance - Sprint 3, item 6."""
from app.core.cache import cache_get_or_set, make_cache_key


async def test_cache_miss_calls_fetch_fn_and_stores_the_result(redis_test_client):
    calls = []

    async def _fetch():
        calls.append(1)
        return {"value": 42}

    result = await cache_get_or_set(redis_test_client, "k1", 60, _fetch)
    assert result == {"value": 42}
    assert len(calls) == 1


async def test_cache_hit_does_not_call_fetch_fn_again(redis_test_client):
    calls = []

    async def _fetch():
        calls.append(1)
        return {"value": 42}

    await cache_get_or_set(redis_test_client, "k2", 60, _fetch)
    result = await cache_get_or_set(redis_test_client, "k2", 60, _fetch)

    assert result == {"value": 42}
    assert len(calls) == 1  # second call was served from cache


async def test_different_keys_do_not_collide(redis_test_client):
    async def _fetch_a():
        return "a"

    async def _fetch_b():
        return "b"

    assert await cache_get_or_set(redis_test_client, "k3a", 60, _fetch_a) == "a"
    assert await cache_get_or_set(redis_test_client, "k3b", 60, _fetch_b) == "b"


async def test_a_null_result_is_cached_and_still_distinguishable_from_a_miss(redis_test_client):
    calls = []

    async def _fetch_none():
        calls.append(1)
        return None

    first = await cache_get_or_set(redis_test_client, "k4", 60, _fetch_none)
    second = await cache_get_or_set(redis_test_client, "k4", 60, _fetch_none)
    assert first is None
    assert second is None
    assert len(calls) == 1  # the cached None was reused, not re-fetched


async def test_a_cache_read_failure_degrades_to_calling_fetch_fn(redis_test_client, monkeypatch):
    async def _broken_get(*a, **kw):
        raise ConnectionError("redis down")

    monkeypatch.setattr(redis_test_client, "get", _broken_get)

    async def _fetch():
        return "computed anyway"

    result = await cache_get_or_set(redis_test_client, "k5", 60, _fetch)
    assert result == "computed anyway"


def test_make_cache_key_joins_parts_and_normalizes_missing_ones():
    assert make_cache_key("a", "b", "c") == "a:b:c"
    assert make_cache_key("a", None, "") == "a:_:_"
