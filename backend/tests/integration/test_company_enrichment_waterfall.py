"""Sprint 4, item 5: enrich_company_waterfall (Tier 4 of the enrichment
waterfall) against a mocked Apollo organizations/enrich response."""
import httpx
import pytest

import app.services.enrichment_waterfall as waterfall_module
from app.config import settings
from app.core.circuit_breaker import CircuitBreaker
from app.services.enrichment_waterfall import enrich_company_waterfall


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    CircuitBreaker.reset_all()
    yield
    CircuitBreaker.reset_all()


@pytest.fixture(autouse=True)
def _apollo_key(monkeypatch):
    monkeypatch.setattr(settings, "APOLLO_API_KEY", "a_real_apollo_key")


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


async def test_extracts_company_fields_from_a_successful_response(monkeypatch, redis_test_client):
    monkeypatch.setattr(waterfall_module, "redis_client", redis_test_client)

    async def _fake_get(self, url, headers=None, params=None, timeout=None):
        return _FakeResponse(200, {
            "organization": {
                "industry": "Fintech",
                "estimated_num_employees": 250,
                "annual_revenue": 15_000_000,
                "city": "San Francisco", "state": "CA", "country": "USA",
                "linkedin_url": "https://linkedin.com/company/acme",
                "website_url": "https://acme.io",
                "latest_funding_stage": "SERIES_B",
                "total_funding": 40_000_000,
                "technology_names": ["Python", "AWS"],
                "short_description": "Payments infrastructure for SMBs.",
            }
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    data = await enrich_company_waterfall("acme.io")

    assert data["industry"] == "Fintech"
    assert data["employee_count"] == 250
    assert data["revenue"] == "$10M-$50M"
    assert data["hq_location"] == "San Francisco, CA, USA"
    assert data["company_linkedin_url"] == "https://linkedin.com/company/acme"
    assert data["company_website"] == "https://acme.io"
    assert data["funding_stage"] == "SERIES_B"
    assert data["funding_amount"] == 40_000_000
    assert data["tech_stack"] == ["Python", "AWS"]
    assert data["company_description"] == "Payments infrastructure for SMBs."


async def test_returns_empty_dict_when_no_api_key_configured(monkeypatch, redis_test_client):
    monkeypatch.setattr(settings, "APOLLO_API_KEY", None)
    monkeypatch.setattr(waterfall_module, "redis_client", redis_test_client)

    data = await enrich_company_waterfall("acme.io")
    assert data == {}


async def test_returns_empty_dict_on_a_non_200_response(monkeypatch, redis_test_client):
    monkeypatch.setattr(waterfall_module, "redis_client", redis_test_client)

    async def _fake_get(self, url, headers=None, params=None, timeout=None):
        return _FakeResponse(404, {})

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    data = await enrich_company_waterfall("unknown-domain.io")
    assert data == {}


async def test_returns_empty_dict_and_opens_circuit_on_repeated_failures(monkeypatch, redis_test_client):
    monkeypatch.setattr(waterfall_module, "redis_client", redis_test_client)
    CircuitBreaker.configure("APOLLO", failure_threshold=2, recovery_timeout_seconds=9999)

    async def _fake_get(self, url, headers=None, params=None, timeout=None):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    # Two distinct domains so the cache doesn't short-circuit repeated calls.
    assert await enrich_company_waterfall("fail-one.io") == {}
    assert await enrich_company_waterfall("fail-two.io") == {}
    assert CircuitBreaker.get_status("APOLLO")["state"] == "OPEN"

    # Circuit now open - a third (also distinct) domain still degrades to {}.
    assert await enrich_company_waterfall("fail-three.io") == {}


async def test_empty_domain_short_circuits_without_any_http_call(monkeypatch, redis_test_client):
    monkeypatch.setattr(waterfall_module, "redis_client", redis_test_client)
    calls = []
    monkeypatch.setattr(httpx.AsyncClient, "get", lambda *a, **kw: calls.append(1))

    data = await enrich_company_waterfall("")
    assert data == {}
    assert calls == []


async def test_result_is_cached_for_the_same_domain(monkeypatch, redis_test_client):
    monkeypatch.setattr(waterfall_module, "redis_client", redis_test_client)
    call_count = 0

    async def _fake_get(self, url, headers=None, params=None, timeout=None):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(200, {"organization": {"industry": "SaaS"}})

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    first = await enrich_company_waterfall("cached-domain.io")
    second = await enrich_company_waterfall("cached-domain.io")

    assert first == second == {
        "industry": "SaaS", "employee_count": None, "revenue": None, "hq_location": None,
        "company_linkedin_url": None, "company_website": None, "funding_stage": None,
        "funding_amount": None, "tech_stack": [], "company_description": None,
    }
    assert call_count == 1
