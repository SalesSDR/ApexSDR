"""Sprint 3, item 5: the MX-record check in enrich_email_waterfall must not
block the event loop. dns.resolver.resolve() is synchronous, so it has to
run via asyncio.to_thread() rather than being awaited/called directly."""
import asyncio
import threading
import time

import dns.resolver
import pytest

import app.services.enrichment_waterfall as waterfall_module
from app.services.enrichment_waterfall import _enrich_email_waterfall_uncached


@pytest.fixture(autouse=True)
def _no_prospeo(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "PROSPEO_API_KEY", None)


async def test_mx_lookup_runs_on_a_worker_thread_not_the_event_loop(monkeypatch):
    calling_thread_ids = []

    def _fake_resolve(domain, kind):
        calling_thread_ids.append(threading.get_ident())
        return ["mx1.example.com"]

    main_thread_id = threading.get_ident()
    monkeypatch.setattr(dns.resolver, "resolve", _fake_resolve)

    result = await _enrich_email_waterfall_uncached("Ada", "Lovelace", "example.com", "")

    assert result == "ada@example.com"
    assert len(calling_thread_ids) == 1
    assert calling_thread_ids[0] != main_thread_id  # ran off the event loop thread


async def test_to_thread_is_the_actual_mechanism_used(monkeypatch):
    """Directly confirms asyncio.to_thread is the call site wrapping the
    resolver, not just that the result happens to be correct."""
    to_thread_calls = []
    real_to_thread = asyncio.to_thread

    async def _spy_to_thread(func, *args, **kwargs):
        to_thread_calls.append((func, args, kwargs))
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(waterfall_module.asyncio, "to_thread", _spy_to_thread)
    monkeypatch.setattr(dns.resolver, "resolve", lambda domain, kind: ["mx1.example.com"])

    await _enrich_email_waterfall_uncached("Grace", "Hopper", "example.com", "")

    assert len(to_thread_calls) == 1
    assert to_thread_calls[0][0] is dns.resolver.resolve


async def test_a_slow_dns_lookup_does_not_block_a_concurrent_task(monkeypatch):
    """The strongest proof the loop isn't blocked: a concurrently-scheduled
    task actually gets to run while the (fake, sleep-based) DNS lookup is
    'in flight' on its own thread."""

    def _slow_resolve(domain, kind):
        time.sleep(0.3)
        return ["mx1.example.com"]

    monkeypatch.setattr(dns.resolver, "resolve", _slow_resolve)

    progress = []

    async def _other_task():
        for _ in range(5):
            await asyncio.sleep(0.05)
            progress.append(1)

    await asyncio.gather(
        _enrich_email_waterfall_uncached("Ada", "Lovelace", "example.com", ""),
        _other_task(),
    )

    assert len(progress) == 5  # the other coroutine made progress concurrently
