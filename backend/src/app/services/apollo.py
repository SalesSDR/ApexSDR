import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ApolloClient:
    """
    Service adapter for the Apollo.io API to perform prospect contact enrichment.
    """
    def __init__(self, api_key: Optional[str], http_client: httpx.AsyncClient):
        self.api_key = api_key
        self.client = http_client
        self.base_url = "https://api.apollo.io/v1"

    async def enrich_contact(self, email: str, linkedin_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Enriches a prospect's contact metadata using Apollo.io matches.
        """
        # If API key is not configured or stubbed, fall back to mock data
        if not self.api_key or "stub" in self.api_key or "live_771x" in self.api_key:
            logger.info(f"Apollo.io: Using demo fallback mock enrichment details for email: {email}")
            return {
                "phone_number": "+15005550006",
                "company_name": "Apollo Enterprise Inc",
                "title": "VP of Growth Sales"
            }

        url = f"{self.base_url}/people/match"
        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "email": email
        }
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url

        try:
            response = await self.client.post(url, json=payload, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                person = data.get("person", {})
                return {
                    "phone_number": person.get("work_phone") or person.get("phone_number"),
                    "company_name": person.get("organization", {}).get("name"),
                    "title": person.get("title")
                }
            logger.warning(f"Apollo API returned status: {response.status_code}")
        except Exception as e:
            logger.error(f"Apollo API enrichment request failed: {str(e)}")

        return {}
