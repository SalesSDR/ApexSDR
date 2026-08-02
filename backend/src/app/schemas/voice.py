from datetime import datetime

from pydantic import BaseModel


class TranscriptLineResponse(BaseModel):
    turn_index: int
    speaker: str
    text: str
    intent: str | None
    confidence: float | None

    class Config:
        from_attributes = True

class TranscriptResponse(BaseModel):
    id: str
    call_sid: str
    duration_seconds: int
    total_turns: int
    status: str
    summary: str | None
    incremental_summary: str | None
    lines: list[TranscriptLineResponse]
    created_at: datetime

    class Config:
        from_attributes = True

class VoiceWebhookRequest(BaseModel):
    call_sid: str
    speech_result: str | None
    call_status: str | None
    
class MockVoiceCallRequest(BaseModel):
    prospect_id: str
    text: str
