
from pydantic import BaseModel, Field


class WorkspaceSettingUpdateSchema(BaseModel):
    follow_up_delay_hours: int | None = Field(None, ge=1)
    call_delay_hours: int | None = Field(None, ge=1)
    max_follow_ups: int | None = Field(None, ge=0)
    working_hours_start: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    working_hours_end: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    timezone: str | None = Field(None)
    exclude_weekends: bool | None = Field(None)
    dev_mode: bool | None = Field(None)
    # Module 13: per-tenant ICP target profile and qualification-scoring
    # overrides (see services/qualification/scoring.py). Both are free-form
    # dicts validated by the scoring engine itself at read time, not here -
    # an unrecognized key is simply ignored rather than rejected, so the
    # engine can grow new configurable knobs without an API-schema change.
    icp_profile: dict | None = Field(None)
    qualification_config: dict | None = Field(None)

class CampaignCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class CampaignResponseSchema(BaseModel):
    id: str
    tenant_id: str
    name: str

    class Config:
        from_attributes = True
