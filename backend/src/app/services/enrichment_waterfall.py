import asyncio
import logging
from typing import Any

import dns.resolver
import httpx

from app.config import settings
from app.core.cache import cache_get_or_set, make_cache_key
from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.database import redis_client

logger = logging.getLogger(__name__)

_APOLLO_PROVIDER = "APOLLO"

async def check_unipile_profile(provider_id: str, account_id: str) -> tuple[str | None, str | None]:
    """
    Tier 1: Check Unipile's native user profile for public email/phone.
    """
    if not settings.UNIPILE_API_KEY or not account_id:
        return None, None
        
    url = f"{settings.UNIPILE_BASE_URL.rstrip('/')}/users/{provider_id}"
    headers = {
        "X-API-KEY": settings.UNIPILE_API_KEY,
        "Content-Type": "application/json",
        "accept": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"account_id": account_id}, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                emails = data.get("emails", [])
                phones = data.get("phone_numbers", [])
                
                email = emails[0].get("email") if emails else None
                # phone_numbers structure varies, try to extract first string
                phone = None
                if phones:
                    if isinstance(phones[0], dict):
                        phone = phones[0].get("number")
                    else:
                        phone = str(phones[0])
                        
                return email, phone
    except Exception as e:
        logger.warning(f"Failed to check Unipile profile for {provider_id}: {e}")
        
    return None, None


async def enrich_email_waterfall(first_name: str, last_name: str, company_domain: str, linkedin_url: str) -> str | None:
    """
    Tier 2: Waterfall email enrichment. Read-through cached (Sprint 3, item
    6) since the same prospect can be re-enriched (retries, re-runs) and
    the underlying vendor lookups are rate-limited/billed per call.
    """
    cache_key = make_cache_key("cache", "enrichment", "email", first_name, last_name, company_domain, linkedin_url)

    async def _fetch() -> str | None:
        return await _enrich_email_waterfall_uncached(first_name, last_name, company_domain, linkedin_url)

    return await cache_get_or_set(redis_client, cache_key, settings.ENRICHMENT_CACHE_TTL_SECONDS, _fetch)


async def _enrich_email_waterfall_uncached(first_name: str, last_name: str, company_domain: str, linkedin_url: str) -> str | None:
    # 1. Prospeo
    if settings.PROSPEO_API_KEY and linkedin_url:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.prospeo.io/linkedin-email-finder",
                    headers={"X-KEY": settings.PROSPEO_API_KEY},
                    json={"url": linkedin_url},
                    timeout=10.0
                )
                if res.status_code == 200:
                    data = res.json()
                    email = data.get("response", {}).get("email", {}).get("email")
                    if email:
                        logger.info(f"Email found via Prospeo for {linkedin_url}")
                        return email
        except Exception as e:
            logger.warning(f"Prospeo API failed: {e}")

    # 2. Local MX Ping Fallback
    if first_name and last_name and company_domain:
        domain = company_domain.lower().replace(' ', '')
        if not domain.endswith('.com') and '.' not in domain:
            domain += '.com'
            
        permutations = [
            f"{first_name.lower()}@{domain}",
            f"{first_name.lower()}.{last_name.lower()}@{domain}",
            f"{first_name.lower()[0]}{last_name.lower()}@{domain}",
        ]
        
        try:
            # Just do a quick MX check for the domain, actual SMTP ping is too complex for this tier.
            # dns.resolver.resolve() is synchronous/blocking - run it off the
            # event loop thread so it can't stall other coroutines in the
            # embedded worker (Sprint 3, item 5).
            answers = await asyncio.to_thread(dns.resolver.resolve, domain, 'MX')
            if answers:
                # We know the domain receives email. We can optimistically return the most common format.
                logger.info(f"Domain {domain} has valid MX records. Attempting permutation fallback.")
                return permutations[0]
        except Exception as e:
            logger.warning(f"MX lookup failed for {domain}: {e}")

    return None


async def enrich_phone_waterfall(linkedin_url: str) -> str | None:
    """
    Tier 3: Waterfall phone enrichment.
    """
    # 1. Kaspr
    if settings.KASPR_API_KEY and linkedin_url:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.kaspr.io/v1/enrich",
                    headers={"Authorization": f"Bearer {settings.KASPR_API_KEY}"},
                    json={"linkedin_url": linkedin_url},
                    timeout=10.0
                )
                if res.status_code == 200:
                    data = res.json()
                    phones = data.get("phones", [])
                    if phones:
                        logger.info(f"Phone found via Kaspr for {linkedin_url}")
                        return phones[0]
        except Exception as e:
            logger.warning(f"Kaspr API failed: {e}")

    return None


async def enrich_company_waterfall(company_domain: str) -> dict[str, Any]:
    """
    Tier 4 (Module 13): company-level enrichment (industry, employee count,
    revenue bucket, HQ location, company LinkedIn/website, funding, tech
    stack, description) via Apollo's organization-enrich endpoint - feeds
    both qualification scoring and AI personalization. Read-through cached
    and routed through the shared APOLLO circuit breaker, same as the rest
    of the Apollo integration (Sprint 3). Returns {} (never raises) if no
    API key is configured, the domain is empty, or the lookup fails -
    company enrichment is a nice-to-have, not a pipeline-blocking step.
    """
    if not company_domain:
        return {}

    cache_key = make_cache_key("cache", "enrichment", "company", company_domain.lower())

    async def _fetch() -> dict[str, Any]:
        return await _enrich_company_waterfall_uncached(company_domain)

    return await cache_get_or_set(redis_client, cache_key, settings.ENRICHMENT_CACHE_TTL_SECONDS, _fetch)


async def _enrich_company_waterfall_uncached(company_domain: str) -> dict[str, Any]:
    if not settings.APOLLO_API_KEY:
        return {}

    url = "https://api.apollo.io/v1/organizations/enrich"
    headers = {"X-Api-Key": settings.APOLLO_API_KEY, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await CircuitBreaker.call(
                _APOLLO_PROVIDER, client.get, url, headers=headers, params={"domain": company_domain}, timeout=10.0
            )
            if response.status_code != 200:
                logger.warning(f"Apollo organization enrich returned status {response.status_code} for {company_domain}")
                return {}

            org = (response.json() or {}).get("organization") or {}
            if not org:
                return {}

            return {
                "industry": org.get("industry"),
                "employee_count": org.get("estimated_num_employees"),
                "revenue": _bucket_revenue(org.get("annual_revenue")),
                "hq_location": _format_location(org),
                "company_linkedin_url": org.get("linkedin_url"),
                "company_website": org.get("website_url"),
                "funding_stage": org.get("latest_funding_stage"),
                "funding_amount": org.get("total_funding"),
                "tech_stack": org.get("technology_names") or [],
                "company_description": org.get("short_description"),
            }
    except CircuitOpenError:
        logger.warning("Apollo circuit is open; skipping company enrichment.")
    except Exception as e:
        logger.warning(f"Apollo organization enrich failed for {company_domain}: {e}")

    return {}


def _bucket_revenue(annual_revenue: float | None) -> str | None:
    if not annual_revenue:
        return None
    if annual_revenue < 1_000_000:
        return "<$1M"
    if annual_revenue < 10_000_000:
        return "$1M-$10M"
    if annual_revenue < 50_000_000:
        return "$10M-$50M"
    if annual_revenue < 250_000_000:
        return "$50M-$250M"
    return "$250M+"


def _format_location(org: dict[str, Any]) -> str | None:
    parts = [org.get("city"), org.get("state"), org.get("country")]
    joined = ", ".join(p for p in parts if p)
    return joined or None
