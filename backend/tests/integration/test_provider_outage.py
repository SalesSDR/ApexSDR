"""Sprint 3, item 3/4: simulated sustained provider outages must open the
circuit and stop hammering the dead provider, while the pipeline degrades
gracefully (a fallback template for Gemini, an empty enrichment dict for
Apollo) rather than raising all the way up."""
import httpx
import pytest

import app.services.ai as ai_module
from app.core.circuit_breaker import CircuitBreaker
from app.services.apollo import ApolloClient


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    CircuitBreaker.reset_all()
    yield
    CircuitBreaker.reset_all()


async def test_gemini_outage_opens_the_circuit_and_falls_back_to_a_template(monkeypatch):
    CircuitBreaker.configure("GEMINI", failure_threshold=2, recovery_timeout_seconds=9999)

    generate_attempts = []

    class _BrokenModel:
        async def generate_content_async(self, *a, **kw):
            generate_attempts.append(1)
            raise RuntimeError("Gemini is down")

    monkeypatch.setattr(ai_module.genai, "configure", lambda **kw: None)
    monkeypatch.setattr(ai_module.genai, "GenerativeModel", lambda *a, **kw: _BrokenModel())

    # First two calls: genuine attempts, both fail and open the circuit.
    msg1 = await ai_module.generate_outreach_message("Ada", "Acme", prompt_type="linkedin")
    msg2 = await ai_module.generate_outreach_message("Ada", "Acme", prompt_type="linkedin")
    assert msg1 and msg2  # fallback template, not an exception
    assert len(generate_attempts) == 2

    assert CircuitBreaker.get_status("GEMINI")["state"] == "OPEN"

    # Third call: circuit is open - generate_content_async must not even be
    # attempted, yet the caller still gets a usable fallback message back.
    msg3 = await ai_module.generate_outreach_message("Ada", "Acme", prompt_type="linkedin")
    assert msg3
    assert len(generate_attempts) == 2  # unchanged - the real call was skipped


async def test_apollo_outage_opens_the_circuit_and_enrich_contact_degrades_to_empty_dict(monkeypatch):
    CircuitBreaker.configure("APOLLO", failure_threshold=2, recovery_timeout_seconds=9999)

    class _BrokenHttpClient:
        async def post(self, *a, **kw):
            raise httpx.ConnectError("connection refused")

    client = ApolloClient(api_key="a_real_apollo_api_key", http_client=_BrokenHttpClient())

    result1 = await client.enrich_contact(email="ada@example.com")
    result2 = await client.enrich_contact(email="ada@example.com")
    assert result1 == {}
    assert result2 == {}
    assert CircuitBreaker.get_status("APOLLO")["state"] == "OPEN"

    # Third call: circuit is open - enrich_contact must still degrade to {}
    # without attempting another HTTP call.
    result3 = await client.enrich_contact(email="ada@example.com")
    assert result3 == {}
