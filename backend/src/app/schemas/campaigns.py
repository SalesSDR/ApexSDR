from typing import Optional
from pydantic import BaseModel, Field

class WorkspaceSettingUpdateSchema(BaseModel):
    follow_up_delay_hours: Optional[int] = Field(None, ge=1)
    call_delay_hours: Optional[int] = Field(None, ge=1)
    max_follow_ups: Optional[int] = Field(None, ge=0)
    working_hours_start: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    working_hours_end: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    timezone: Optional[str] = Field(None)
    exclude_weekends: Optional[bool] = Field(None)

class CampaignCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class CampaignResponseSchema(BaseModel):
    id: str
    tenant_id: str
    name: str

    class Config:
        from_attributes = True
