import logging
import re
from typing import Any

import httpx

from app.services.linkedin.base import LinkedInAdapter, LinkedInRateLimitError

logger = logging.getLogger(__name__)


class ProductionLinkedInAdapter(LinkedInAdapter):
    """Sends real LinkedIn connection requests/messages via the Unipile API."""

    def __init__(self, api_key: str, base_url: str, http_client: httpx.AsyncClient):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = http_client

    def _headers(self) -> dict[str, str]:
        return {"X-API-KEY": self.api_key, "Content-Type": "application/json", "accept": "application/json"}

    async def _resolve_provider_id(self, identifier: str, account_id: str) -> str:
        try:
            res = await self.client.get(
                f"{self.base_url}/users/{identifier}",
                params={"account_id": account_id},
                headers=self._headers(),
                timeout=10.0,
            )
            if res.status_code == 200:
                return res.json().get("provider_id", identifier)
            logger.warning(f"Failed to resolve Unipile provider_id for {identifier}: {res.status_code}")
        except Exception as e:
            logger.warning(f"Exception resolving Unipile provider_id: {e}")
        return identifier

    async def send_connection_request(self, linkedin_url: str, account_id: str, message: str | None = None) -> dict[str, Any]:
        match = re.search(r"in/([^/]+)", linkedin_url)
        identifier = match.group(1) if match else linkedin_url
        provider_id = await self._resolve_provider_id(identifier, account_id)

        payload = {"account_id": account_id, "provider_id": provider_id, "message": message}
        logger.info(f"Unipile connection dispatch: {identifier} (provider_id: {provider_id}) from account {account_id}")
        response = await self.client.post(f"{self.base_url}/users/invite", json=payload, headers=self._headers(), timeout=60.0)

        if response.status_code in (200, 201):
            return response.json()
        if response.status_code == 429:
            raise LinkedInRateLimitError(f"Unipile rate-limited connection request: {response.text}")
        error_msg = f"Unipile invitation failed with status {response.status_code}: {response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)

    async def send_message(self, account_id: str, provider_id: str, text: str) -> dict[str, Any]:
        resolved_id = await self._resolve_provider_id(provider_id, account_id)
        payload = {"account_id": account_id, "attendees_ids": [resolved_id], "text": text}
        logger.info(f"Unipile dispatching direct chat message to: {resolved_id} (original: {provider_id})")
        response = await self.client.post(f"{self.base_url}/chats", json=payload, headers=self._headers(), timeout=10.0)

        if response.status_code in (200, 201):
            return response.json()
        if response.status_code == 429:
            raise LinkedInRateLimitError(f"Unipile rate-limited message send: {response.text}")
        error_msg = f"Unipile messaging failed with status {response.status_code}: {response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)
