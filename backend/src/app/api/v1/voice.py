import logging
from xml.sax.saxutils import escape as xml_escape

import httpx
import redis.asyncio as aioredis
from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.auth import verify_tenant
from app.api.v1.webhooks import verify_twilio_signature
from app.config import settings
from app.database import get_arq_pool, get_db, get_redis
from app.models.schemas import CallTranscript, DecisionType, Prospect, ProspectState
from app.schemas.voice import MockVoiceCallRequest, TranscriptResponse
from app.services.crm.factory import get_crm_adapter
from app.services.crm.service import CRMService
from app.services.voice_ai import audio_cache
from app.services.voice_ai.orchestrator import TurnResult, VoiceOrchestrator
from app.services.voice_ai.stt.factory import get_stt_provider
from app.services.voice_ai.tts.factory import get_tts_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice"])

# How long Twilio should wait for speech before considering the recording
# done (ConversationManager's silence handling takes over from there).
_RECORD_SILENCE_TIMEOUT_SECONDS = 5
_RECORD_MAX_LENGTH_SECONDS = 30

# Sprint 7.1: statuses in which a prospect can legitimately be mid-call -
# the cross-check _load_prospect_for_call uses to verify "ownership" of a
# Twilio webhook request, since these webhooks carry no tenant JWT to
# check against (see that function's docstring).
_ACTIVE_CALL_STATES = (ProspectState.CALL_QUEUED, ProspectState.CALL_IN_PROGRESS, ProspectState.CALL_CONNECTED)

_REJECT_TWIML = "<Response><Reject/></Response>"


def _digits_only(number: str | None) -> str:
    return "".join(ch for ch in number if ch.isdigit()) if number else ""


def _phone_numbers_match(prospect_number: str | None, twilio_to: str | None) -> bool:
    """Tolerant comparison (ignores +/formatting/leading country code
    differences) - exact string equality is too strict given phone numbers
    are stored and delivered in inconsistent formats elsewhere in this
    codebase (see webhooks.py's own `To.replace("+", "")` handling)."""
    a, b = _digits_only(prospect_number), _digits_only(twilio_to)
    if not a or not b:
        return False
    return a == b or a.endswith(b) or b.endswith(a)


async def _load_prospect_for_call(db: AsyncSession, prospect_id: str, to_number: str | None) -> Prospect | None:
    """Sprint 7.1 (tenant/ownership isolation): a Twilio voice webhook
    carries no tenant JWT, so `prospect_id` alone is never sufficient to
    decide which prospect's state this request is allowed to mutate - a
    valid Twilio signature only proves the request really came from Twilio
    for a call *some* authorized caller set up, not that this specific
    prospect_id is the one that call is actually about. This cross-checks
    the loaded prospect against data Twilio itself supplied for this exact
    call: its own `To` number, and that the prospect is presently in a
    state where a live call is expected at all. A mismatch is treated
    identically to "prospect not found" by every caller."""
    query = select(Prospect).where(Prospect.id == prospect_id)
    prospect = (await db.execute(query)).scalar_one_or_none()
    if not prospect:
        return None
    if prospect.status not in _ACTIVE_CALL_STATES:
        logger.warning(
            f"Voice webhook rejected for prospect {prospect_id}: not in an active call state ({prospect.status.value})."
        )
        return None
    if not _phone_numbers_match(prospect.phone_number, to_number):
        logger.warning(f"Voice webhook rejected for prospect {prospect_id}: To number does not match phone_number on file.")
        return None
    return prospect


def _mock_call_allowed() -> bool:
    """Sprint 7.1: /voice/mock-call must never be reachable against a real
    production deployment unless it's explicitly still running in mock
    mode (USE_MOCK_CLIENTS=true, e.g. a staging environment configured
    with ENVIRONMENT=production for other reasons)."""
    return settings.ENVIRONMENT != "production" or settings.USE_MOCK_CLIENTS


async def _apply_turn_side_effects(db: AsyncSession, prospect: Prospect, turn: TurnResult, arq_pool: ArqRedis) -> None:
    """The only side effects a voice turn can trigger beyond the state
    transition VoiceOrchestrator already applied: enqueueing calendar
    booking (mirrors webhooks.py's queue_calendar_booking) and a best-effort
    CRM status sync (mirrors webhooks.py's sync_crm_after_reply) - CRM/
    Calendar modules themselves are untouched, this only calls them."""
    if turn.decision.decision_type == DecisionType.BOOK_MEETING:
        prospect.retry_count = 0
        try:
            await arq_pool.enqueue_job("book_calendar_meeting_task", prospect.id)
        except Exception as e:
            logger.error(f"Failed to enqueue calendar booking for prospect {prospect.id}: {e}")

    if turn.call_ended:
        try:
            async with httpx.AsyncClient() as http_client:
                crm_service = CRMService(get_crm_adapter(http_client))
                await crm_service.sync_status(prospect, db=db)
                if turn.decision.decision_type == DecisionType.BOOK_MEETING:
                    await crm_service.log_meeting_booked(prospect, db=db)
        except Exception as e:
            logger.warning(f"CRM sync failed for prospect {prospect.id} after voice call: {e}")


async def _render_twiml(voice_response, prospect_id: str, call_sid: str, call_ended: bool, redis: aioredis.Redis) -> str:
    """Synthesizes `voice_response.spoken_response` via the TTS provider and
    renders the corresponding TwiML - `<Play>` for real synthesized audio,
    `<Say>` as the fallback when the provider produced none (mock mode)."""
    say_or_play = await _synthesize_to_twiml_verb(voice_response.spoken_response, redis)

    if call_ended:
        return f"<Response>{say_or_play}<Hangup/></Response>"

    record_action = f"/api/v1/voice/webhook/recording?prospect_id={prospect_id}&call_sid={call_sid}"
    return (
        "<Response>"
        f"{say_or_play}"
        f'<Record action="{record_action}" method="POST" '
        f'timeout="{_RECORD_SILENCE_TIMEOUT_SECONDS}" maxLength="{_RECORD_MAX_LENGTH_SECONDS}" '
        'playBeep="false" trim="trim-silence"/>'
        "<Say>We didn't receive any input. Goodbye.</Say>"
        "<Hangup/>"
        "</Response>"
    )


async def _synthesize_to_twiml_verb(text: str, redis: aioredis.Redis) -> str:
    try:
        async with httpx.AsyncClient() as http_client:
            tts_provider = get_tts_provider(http_client)
            audio = await tts_provider.synthesize(text)
    except Exception as e:
        logger.error(f"TTS synthesis failed, falling back to <Say>: {e}")
        audio = None

    if audio is not None and audio.audio_bytes:
        audio_id = await audio_cache.store_audio(redis, audio.audio_bytes, audio.content_type)
        audio_url = f"{settings.PUBLIC_BASE_URL}/api/v1/voice/tts-audio/{audio_id}"
        return f"<Play>{xml_escape(audio_url)}</Play>"

    return f"<Say>{xml_escape(text)}</Say>"


@router.post("/webhook/incoming")
async def voice_webhook_incoming(
    request: Request,
    prospect_id: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    First-turn Twilio webhook: the call has just connected, nothing has been
    said yet. Greets the prospect (via VoiceOrchestrator with empty
    user_speech) and starts the <Record>-based turn loop - every subsequent
    turn is handled by /webhook/recording, since STT (Deepgram) needs actual
    recorded audio, not Twilio's own built-in speech recognition.

    Requires a valid Twilio signature (Sprint 7.1) - never processes an
    unauthenticated request, matching webhooks.py's other Twilio handler.
    """
    await verify_twilio_signature(request)
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "mock-call-sid")
    to_number = form_data.get("To")

    prospect = await _load_prospect_for_call(db, prospect_id, to_number)
    if not prospect:
        return Response(content=_REJECT_TWIML, media_type="application/xml")

    turn = await VoiceOrchestrator.process_turn(db, prospect, call_sid, "")
    await _apply_turn_side_effects(db, prospect, turn, arq_pool)
    await db.commit()

    twiml = await _render_twiml(turn.voice_response, prospect_id, call_sid, turn.call_ended, redis)
    return Response(content=twiml, media_type="application/xml")


@router.post("/webhook/recording")
async def voice_webhook_recording(
    request: Request,
    prospect_id: str,
    call_sid: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Fires once per turn after Twilio finishes recording the prospect's
    reply (silence-terminated or maxLength-terminated). Pipeline: STT ->
    VoiceOrchestrator (Conversation Manager -> LLM -> Memory -> Decision
    Engine -> State Machine) -> CRM/Calendar side effects -> TTS -> TwiML
    for the next turn (or Hangup).

    Requires a valid Twilio signature (Sprint 7.1) - never processes an
    unauthenticated request.
    """
    await verify_twilio_signature(request)
    form_data = await request.form()
    recording_url = form_data.get("RecordingUrl", "")
    to_number = form_data.get("To")

    prospect = await _load_prospect_for_call(db, prospect_id, to_number)
    if not prospect:
        return Response(content=_REJECT_TWIML, media_type="application/xml")

    user_speech = ""
    if recording_url:
        try:
            async with httpx.AsyncClient() as http_client:
                stt_provider = get_stt_provider(http_client)
                user_speech = await stt_provider.transcribe(recording_url)
        except Exception as e:
            logger.error(f"STT transcription failed for call {call_sid}: {e}")
            user_speech = ""  # treated as silence by ConversationManager

    turn = await VoiceOrchestrator.process_turn(db, prospect, call_sid, user_speech)
    await _apply_turn_side_effects(db, prospect, turn, arq_pool)
    await db.commit()

    twiml = await _render_twiml(turn.voice_response, prospect_id, call_sid, turn.call_ended, redis)
    return Response(content=twiml, media_type="application/xml")


@router.get("/tts-audio/{audio_id}")
async def get_tts_audio(audio_id: str, redis: aioredis.Redis = Depends(get_redis)):
    """Serves ephemerally-cached TTS audio for Twilio's `<Play>` verb to
    fetch (see services/voice_ai/audio_cache.py - ElevenLabs returns raw
    bytes, not a hosted URL, so this is the file Twilio actually plays)."""
    cached = await audio_cache.get_audio(redis, audio_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Audio not found or expired")
    audio_bytes, content_type = cached
    return Response(content=audio_bytes, media_type=content_type)


@router.post("/mock-call")
async def mock_call(
    req: MockVoiceCallRequest,
    tenant_id: str = Depends(verify_tenant),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """Drives a single voice turn without Twilio/Deepgram/ElevenLabs - the
    full pipeline (Conversation Manager -> LLM -> Memory -> Decision Engine
    -> State Machine -> CRM/Calendar) still runs, just with the prospect's
    speech supplied directly instead of transcribed from a phone call.

    Sprint 7.1: disabled outside development/mock mode (returns 404, the
    same response an unrecognized route gets, rather than revealing this
    endpoint exists) and scoped to the caller's own tenant - this is a
    testing tool, not something a real production caller should ever
    reach, authenticated or not.
    """
    if not _mock_call_allowed():
        raise HTTPException(status_code=404, detail="Not found")

    query = select(Prospect).where(Prospect.id == req.prospect_id, Prospect.tenant_id == tenant_id)
    prospect = (await db.execute(query)).scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    turn = await VoiceOrchestrator.process_turn(db, prospect, f"mock-{prospect.id}", req.text)
    await _apply_turn_side_effects(db, prospect, turn, arq_pool)
    await db.commit()

    return {
        "status": "success",
        "response": turn.voice_response.model_dump(),
        "decision": turn.decision.decision_type.value,
        "call_ended": turn.call_ended,
        "prospect_status": prospect.status.value,
    }


@router.get("/conversations", response_model=list[TranscriptResponse])
async def get_conversations(tenant_id: str = Depends(verify_tenant), db: AsyncSession = Depends(get_db)):
    """Returns all conversations for a tenant."""
    query = (
        select(CallTranscript)
        .where(CallTranscript.tenant_id == tenant_id)
        .order_by(CallTranscript.created_at.desc())
        .options(selectinload(CallTranscript.lines))
    )
    transcripts = (await db.execute(query)).scalars().unique().all()
    return transcripts


@router.get("/status")
async def get_voice_status():
    return {"status": "success", "engine": "active"}
