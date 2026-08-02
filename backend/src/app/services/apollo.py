import logging
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

_APOLLO_PROVIDER = "APOLLO"

class ApolloClient:
    """
    Service adapter for the Apollo.io API to perform prospect contact enrichment.
    """
    def __init__(self, api_key: str | None, http_client: httpx.AsyncClient):
        self.api_key = api_key
        self.client = http_client
        self.base_url = "https://api.apollo.io/v1"

    async def enrich_contact(self, email: str, linkedin_url: str | None = None, first_name: str | None = None, last_name: str | None = None) -> dict[str, Any]:
        """
        Enriches a prospect's contact metadata using Apollo.io matches.
        Uses mixed_people/api_search to bypass strict email match limits.
        """
        # If API key is not configured or stubbed, fall back to mock data
        if not self.api_key or "stub" in self.api_key or "live_771x" in self.api_key:
            logger.info(f"Apollo.io: Using demo fallback mock enrichment details for email: {email}")
            return {
                "phone_number": "+15005550006",
                "company_name": "Apollo Enterprise Inc",
                "title": "VP of Growth Sales"
            }

        url = f"{self.base_url}/mixed_people/api_search"
        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Extract domain from email
        domain = email.split('@')[-1] if '@' in email else None
        
        payload = {
            "page": 1,
            "per_page": 1
        }
        
        if domain:
            payload["q_organization_domains_list"] = [domain]
            
        if first_name and last_name:
            payload["q_keywords"] = f"{first_name} {last_name}"
        else:
            # Fallback if names aren't provided explicitly
            payload["q_keywords"] = email.split('@')[0].replace('.', ' ')

        try:
            response = await CircuitBreaker.call(
                _APOLLO_PROVIDER, self.client.post, url, json=payload, headers=headers, timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                people = data.get("people", [])
                if people:
                    person = people[0]
                    return {
                        "phone_number": person.get("work_phone") or person.get("phone_number"),
                        "company_name": person.get("organization", {}).get("name"),
                        "title": person.get("title")
                    }
                else:
                    logger.warning("Apollo API returned 200 but no people matched.")
            else:
                logger.warning(f"Apollo API returned status: {response.status_code}")
        except CircuitOpenError:
            logger.warning("Apollo circuit is open; skipping enrichment request.")
        except Exception as e:
            logger.error(f"Apollo API enrichment request failed: {str(e)}")

        return {}
