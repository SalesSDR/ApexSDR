import logging
from datetime import UTC, datetime

import httpx

from app.services.crm.base import CompanyData, ContactData, CRMAdapter

logger = logging.getLogger(__name__)


class ProductionHubSpotAdapter(CRMAdapter):
    """Syncs prospect data to a real HubSpot account via the CRM v3 API,
    authenticated with a Private App access token."""

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, api_key: str, http_client: httpx.AsyncClient):
        self.api_key = api_key
        self.client = http_client

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _associate(self, object_type: str, object_id: str, contact_id: str) -> None:
        url = f"{self.BASE_URL}/crm/v3/objects/{object_type}/{object_id}/associations/default/contacts/{contact_id}"
        response = await self.client.put(url, headers=self._headers(), timeout=10.0)
        if response.status_code not in (200, 201, 204):
            raise Exception(f"HubSpot association failed ({object_type}->contact): {response.status_code}: {response.text}")

    async def upsert_contact(self, contact: ContactData, external_id: str | None) -> str:
        properties = {
            "firstname": contact.first_name,
            "lastname": contact.last_name,
            "phone": contact.phone_number,
            "company": contact.company_name,
            "website": contact.linkedin_url,
        }
        properties = {k: v for k, v in properties.items() if v}

        if contact.email:
            url = f"{self.BASE_URL}/crm/v3/objects/contacts/batch/upsert"
            payload = {
                "inputs": [
                    {
                        "idProperty": "email",
                        "id": contact.email,
                        "properties": {**properties, "email": contact.email},
                    }
                ]
            }
            response = await self.client.post(url, json=payload, headers=self._headers(), timeout=10.0)
            if response.status_code not in (200, 201):
                raise Exception(f"HubSpot contact upsert failed: {response.status_code}: {response.text}")
            return response.json()["results"][0]["id"]

        if external_id:
            url = f"{self.BASE_URL}/crm/v3/objects/contacts/{external_id}"
            response = await self.client.patch(url, json={"properties": properties}, headers=self._headers(), timeout=10.0)
            if response.status_code not in (200, 201):
                raise Exception(f"HubSpot contact update failed: {response.status_code}: {response.text}")
            return response.json()["id"]

        url = f"{self.BASE_URL}/crm/v3/objects/contacts"
        response = await self.client.post(url, json={"properties": properties}, headers=self._headers(), timeout=10.0)
        if response.status_code not in (200, 201):
            raise Exception(f"HubSpot contact create failed: {response.status_code}: {response.text}")
        return response.json()["id"]

    async def upsert_company(self, company: CompanyData, external_id: str | None) -> str:
        properties = {"name": company.name}
        if company.domain:
            properties["domain"] = company.domain

        if company.domain:
            url = f"{self.BASE_URL}/crm/v3/objects/companies/batch/upsert"
            payload = {
                "inputs": [
                    {"idProperty": "domain", "id": company.domain, "properties": properties}
                ]
            }
            response = await self.client.post(url, json=payload, headers=self._headers(), timeout=10.0)
            if response.status_code not in (200, 201):
                raise Exception(f"HubSpot company upsert failed: {response.status_code}: {response.text}")
            return response.json()["results"][0]["id"]

        if external_id:
            url = f"{self.BASE_URL}/crm/v3/objects/companies/{external_id}"
            response = await self.client.patch(url, json={"properties": properties}, headers=self._headers(), timeout=10.0)
            if response.status_code not in (200, 201):
                raise Exception(f"HubSpot company update failed: {response.status_code}: {response.text}")
            return response.json()["id"]

        url = f"{self.BASE_URL}/crm/v3/objects/companies"
        response = await self.client.post(url, json={"properties": properties}, headers=self._headers(), timeout=10.0)
        if response.status_code not in (200, 201):
            raise Exception(f"HubSpot company create failed: {response.status_code}: {response.text}")
        return response.json()["id"]

    async def associate_contact_company(self, contact_id: str, company_id: str) -> None:
        # Same default-association endpoint shape as notes/deals/meetings
        # below (_associate), just from the companies object type.
        await self._associate("companies", company_id, contact_id)

    async def log_note(self, contact_id: str, text: str) -> str:
        url = f"{self.BASE_URL}/crm/v3/objects/notes"
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        payload = {"properties": {"hs_note_body": text, "hs_timestamp": now_ms}}
        response = await self.client.post(url, json=payload, headers=self._headers(), timeout=10.0)
        if response.status_code not in (200, 201):
            raise Exception(f"HubSpot note create failed: {response.status_code}: {response.text}")
        note_id = response.json()["id"]
        await self._associate("notes", note_id, contact_id)
        return note_id

    async def upsert_deal(self, contact_id: str, deal_id: str | None, deal_name: str, stage: str) -> str:
        properties = {"dealname": deal_name, "dealstage": stage}
        if deal_id:
            url = f"{self.BASE_URL}/crm/v3/objects/deals/{deal_id}"
            response = await self.client.patch(url, json={"properties": properties}, headers=self._headers(), timeout=10.0)
            if response.status_code not in (200, 201):
                raise Exception(f"HubSpot deal update failed: {response.status_code}: {response.text}")
            return response.json()["id"]

        url = f"{self.BASE_URL}/crm/v3/objects/deals"
        response = await self.client.post(url, json={"properties": properties}, headers=self._headers(), timeout=10.0)
        if response.status_code not in (200, 201):
            raise Exception(f"HubSpot deal create failed: {response.status_code}: {response.text}")
        new_deal_id = response.json()["id"]
        await self._associate("deals", new_deal_id, contact_id)
        return new_deal_id

    async def log_meeting(self, contact_id: str, title: str, meeting_time: datetime) -> str:
        url = f"{self.BASE_URL}/crm/v3/objects/meetings"
        start_ms = int(meeting_time.timestamp() * 1000)
        payload = {"properties": {"hs_meeting_title": title, "hs_meeting_start_time": start_ms}}
        response = await self.client.post(url, json=payload, headers=self._headers(), timeout=10.0)
        if response.status_code not in (200, 201):
            raise Exception(f"HubSpot meeting create failed: {response.status_code}: {response.text}")
        meeting_id = response.json()["id"]
        await self._associate("meetings", meeting_id, contact_id)
        return meeting_id
