from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import CallTranscript, CallTranscriptLine, MemoryType, Prospect
from app.services.memory.service import ConversationMemoryService
from app.services.voice_ai.conversation import VoiceResponse

# Sprint 7, item 5: which intents get persisted as a durable ConversationMemory
# (not just a transcript line) and how, so the objection/preference/meeting-
# request/outcome record survives independent of the call transcript itself
# and feeds the Decision Engine's table-driven MEMORY_RULES on future turns
# (services/decision/engine.py).
_PREFERENCE_SNOOZE = timedelta(days=7)


class TranscriptService:
    @staticmethod
    async def get_or_create_transcript(db: AsyncSession, call_sid: str, prospect: Prospect) -> CallTranscript:
        query = select(CallTranscript).where(CallTranscript.call_sid == call_sid)
        transcript = (await db.execute(query)).scalar_one_or_none()

        if not transcript:
            transcript = CallTranscript(
                prospect_id=prospect.id,
                tenant_id=prospect.tenant_id,
                call_sid=call_sid,
                total_turns=0,
                status="IN_PROGRESS",
            )
            db.add(transcript)
            await db.flush()
        return transcript

    @staticmethod
    async def get_recent_history(db: AsyncSession, transcript_id: str, limit: int = 5) -> list[dict]:
        query = (
            select(CallTranscriptLine)
            .where(CallTranscriptLine.transcript_id == transcript_id)
            .order_by(CallTranscriptLine.turn_index.desc())
            .limit(limit)
        )
        lines = list((await db.execute(query)).scalars().all())
        lines.reverse()  # chronological order
        return [{"speaker": line.speaker, "text": line.text} for line in lines]

    @staticmethod
    async def add_turn(
        db: AsyncSession,
        transcript: CallTranscript,
        user_speech: str,
        ai_response: VoiceResponse,
    ):
        """Persists both sides of a turn (Sprint 7, item 5: transcript) and,
        for intents that matter beyond this single call, a durable
        ConversationMemory row (objections, preferences, meeting requests,
        outcomes)."""
        # Prospect turn (skipped for silent turns - nothing was said).
        if user_speech and user_speech.strip():
            transcript.total_turns += 1
            db.add(CallTranscriptLine(
                tenant_id=transcript.tenant_id,
                transcript_id=transcript.id,
                turn_index=transcript.total_turns,
                speaker="PROSPECT",
                text=user_speech,
            ))

        # Assistant turn
        transcript.total_turns += 1
        db.add(CallTranscriptLine(
            tenant_id=transcript.tenant_id,
            transcript_id=transcript.id,
            turn_index=transcript.total_turns,
            speaker="ASSISTANT",
            text=ai_response.spoken_response,
            intent=ai_response.intent,
            confidence=ai_response.confidence,
        ))

        # Running summary (Sprint 7, item 5: summary) - a cheap, always-on
        # incremental log; the final `summary` field is set once the call
        # ends (see summarize_voice_conversation_task).
        transcript.incremental_summary = (
            f"{transcript.incremental_summary or ''} [{ai_response.intent}] {ai_response.summary}".strip()
        )

        await TranscriptService._persist_memory_for_intent(db, transcript, user_speech, ai_response)
        await db.flush()

    @staticmethod
    async def _persist_memory_for_intent(
        db: AsyncSession, transcript: CallTranscript, user_speech: str, ai_response: VoiceResponse,
    ) -> None:
        memory_type: MemoryType | None = None
        metadata: dict = {"call_sid": transcript.call_sid, "intent": ai_response.intent}
        is_resolved = False
        expires_at = None

        if ai_response.intent == "OBJECTION":
            memory_type = MemoryType.OBJECTION
        elif ai_response.intent in ("MEETING_REQUEST",) or ai_response.next_action == "BOOK_MEETING":
            memory_type = MemoryType.BUYING_SIGNAL
            metadata["signal_type"] = "MEETING_REQUEST"
            is_resolved = True  # acted on immediately by the Decision Engine, not a standing rule to re-fire
        elif ai_response.intent == "PREFERENCE" or ai_response.next_action == "PAUSE":
            memory_type = MemoryType.PREFERENCE
            expires_at = datetime.now(UTC) + _PREFERENCE_SNOOZE
        elif ai_response.intent == "NOT_INTERESTED" or ai_response.next_action == "CLOSE":
            memory_type = MemoryType.MEETING_OUTCOME
            is_resolved = True

        if memory_type is None:
            return

        await ConversationMemoryService.add_memory(
            db=db,
            tenant_id=transcript.tenant_id,
            prospect_id=transcript.prospect_id,
            memory_type=memory_type,
            content=f"{ai_response.summary} (intent: {ai_response.intent}. Prospect said: \"{user_speech}\")",
            source="VOICE_CALL",
            importance_score=8,
            is_resolved=is_resolved,
            expires_at=expires_at,
            metadata_=metadata,
        )
