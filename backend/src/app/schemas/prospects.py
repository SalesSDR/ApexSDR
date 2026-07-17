from typing import Optional
from pydantic import BaseModel, Field, EmailStr, HttpUrl

class ProspectCreateSchema(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    linkedin_url: HttpUrl
    phone_number: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")
    campaign_id: Optional[str] = None

class ProspectResponseData(BaseModel):
    id: str
    current_state: str
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
