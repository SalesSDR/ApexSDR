from datetime import datetime

from pydantic import BaseModel, Field

from app.models.schemas import SignalStrength, SignalType


class BuyingSignalCreate(BaseModel):
    signal_type: SignalType
    signal_source: str
    signal_strength: SignalStrength
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    summary: str
    metadata_: dict = Field(default_factory=dict)
    expires_at: datetime | None = None

class BuyingSignalResponse(BaseModel):
    id: str
    prospect_id: str
    signal_type: SignalType
    signal_source: str
    signal_strength: SignalStrength
    confidence: float
    summary: str
    metadata_: dict
    is_active: bool
    created_at: datetime
    expires_at: datetime | None
    processed_at: datetime | None

    class Config:
        from_attributes = True

class BuyingSignalListResponse(BaseModel):
    status: str = "success"
    data: list[BuyingSignalResponse]

class BuyingSignalSummaryResponse(BaseModel):
    status: str = "success"
    data: dict  # Will hold aggregate metrics
