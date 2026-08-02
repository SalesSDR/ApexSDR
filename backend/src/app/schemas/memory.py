from datetime import datetime

from pydantic import BaseModel, Field

from app.models.schemas import MemoryType


class ConversationMemoryCreate(BaseModel):
    memory_type: MemoryType
    content: str
    importance_score: int = Field(1, ge=1, le=10)
    is_resolved: bool = False
    source: str
    created_by: str | None = None
    expires_at: datetime | None = None
    metadata_: dict = Field(default_factory=dict)

    class Config:
        from_attributes = True

class ConversationMemoryResponse(BaseModel):
    id: str
    prospect_id: str
    memory_type: MemoryType
    content: str
    importance_score: int
    is_resolved: bool
    source: str
    created_by: str | None
    expires_at: datetime | None
    metadata_: dict
    created_at: datetime
    tenant_id: str

    class Config:
        from_attributes = True

class ConversationMemoryListResponse(BaseModel):
    status: str = "success"
    data: list[ConversationMemoryResponse]
