
from pydantic import BaseModel, EmailStr, Field, HttpUrl

from app.models.schemas import ProspectState


class ProspectCreateSchema(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    linkedin_url: HttpUrl
    phone_number: str | None = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")
    campaign_id: str | None = None


class ProspectResponseData(BaseModel):
    id: str
    status: ProspectState
    tenant_id: str

    class Config:
        from_attributes = True

class ProspectResponseSchema(BaseModel):
    status: str = "success"
    data: ProspectResponseData

class ProspectListElement(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    linkedin_url: str | None = None
    phone_number: str | None = None
    status: ProspectState
    tenant_id: str

    class Config:
        from_attributes = True

class ProspectListResponseSchema(BaseModel):
    status: str = "success"
    data: list[ProspectListElement]

class BulkActionSchema(BaseModel):
    prospect_ids: list[str]
    action: str

class AdvanceActionSchema(BaseModel):
    target_state: str | None = None

class UnipileProfileSchema(BaseModel):
    provider_id: str
    first_name: str
    last_name: str
    title: str | None = None
    organization_name: str | None = None
    company_domain: str | None = None
    email: str | None = None
    linkedin_url: str | None = None

class UnipileImportSchema(BaseModel):
    profiles: list[UnipileProfileSchema]
    campaign_id: str | None = None
