from typing import Optional
from pydantic import BaseModel, Field, EmailStr, HttpUrl

class ProspectCreateSchema(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    linkedin_url: HttpUrl
    phone_number: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")
    campaign_id: Optional[str] = None

from app.models.schemas import ProspectStatus

class ProspectResponseData(BaseModel):
    id: str
    current_state: str
    status: ProspectStatus
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
    linkedin_url: Optional[str] = None
    phone_number: Optional[str] = None
    current_state: str
    status: ProspectStatus
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
    target_state: Optional[str] = None

class UnipileProfileSchema(BaseModel):
    provider_id: str
    first_name: str
    last_name: str
    title: Optional[str] = None
    organization_name: Optional[str] = None
    company_domain: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None

class UnipileImportSchema(BaseModel):
    profiles: list[UnipileProfileSchema]
    campaign_id: Optional[str] = None
