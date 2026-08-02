from datetime import datetime

from pydantic import BaseModel, Field

from app.models.schemas import CompliancePolicyType, PolicySeverity


class DoNotContactCreate(BaseModel):
    value: str
    type: str = Field(..., description="EMAIL, DOMAIN, or PHONE")
    reason: str | None = None
    source: str = "USER_MANUAL"

class DoNotContactResponse(DoNotContactCreate):
    id: str
    tenant_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class ComplianceLogResponse(BaseModel):
    id: str
    prospect_id: str | None
    policy_type: CompliancePolicyType
    severity: PolicySeverity
    channel: str | None
    reason: str
    metadata_: dict
    created_at: datetime

    class Config:
        from_attributes = True

class ComplianceStatusResponse(BaseModel):
    status: str = "success"
    data: dict

class ComplianceLogListResponse(BaseModel):
    status: str = "success"
    data: list[ComplianceLogResponse]
