import asyncio
import logging
import random
import uuid
from urllib.parse import parse_qs, urlparse

from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.services.voice.base import CallResult, VoiceAdapter

logger = logging.getLogger(__name__)

# Real Twilio delivers "answered" only once the callee's phone actually
# picks up, an unpredictable delay - 2-5s keeps the simulated pipeline
# observably async without slowing local/CI runs down.
_MOCK_ANSWER_DELAY_RANGE_SECONDS = (2.0, 5.0)

# Deterministically drives MockVoiceAIProvider's keyword match for
# next_action="BOOK_MEETING" (see services/voice_ai/mock.py), so a simulated
# call reaches the same MEETING_BOOKED/calendar/CRM outcome a real positive
# reply would - RC-1 validation needs the full pipeline to complete, not a
# hand-picked outcome invented here.
_MOCK_PROSPECT_REPLY = "Yes, I'd love to book a demo."


def _extract_prospect_id(twimlet_url: str) -> str | None:
    values = parse_qs(urlparse(twimlet_url).query).get("prospect_id")
    return values[0] if values else None


class MockTwilioAdapter(VoiceAdapter):
    """Simulates placing a call. Used whenever Twilio credentials are absent
    so the outbound pipeline can run end-to-end without a real Twilio account.

    Real Twilio delivers two independent event streams once initiate_call()
    places a call: status callbacks (queued -> answered -> completed, posted
    to /webhooks/twilio/call-status) and the TwiML conversation itself
    (posted to twimlet_url, then to <Record action>). Neither exists without
    real telephony, so CALL_IN_PROGRESS stalls forever unless something
    simulates them. This schedules a delayed background simulation of both,
    invoking the exact same application handlers a real Twilio webhook would
    hit - it never calls transition_prospect() or invents an outcome itself.
    """

    async def initiate_call(self, to_number: str, twimlet_url: str) -> CallResult:
        logger.info(f"MOCK ADAPTER ACTIVE: simulating Twilio call to {to_number}")
        call_sid = f"CA{uuid.uuid4().hex}"

        prospect_id = _extract_prospect_id(twimlet_url)
        if prospect_id:
            asyncio.create_task(_simulate_call_progress(prospect_id, to_number, call_sid))
        else:
            logger.error(
                f"MockTwilioAdapter: could not extract prospect_id from twimlet_url {twimlet_url!r}; "
                "skipping simulated callback."
            )

        return CallResult(sid=call_sid, status="queued")


async def _simulate_call_progress(prospect_id: str, to_number: str, call_sid: str) -> None:
    """Runs detached from the request/job that called initiate_call() - by
    the time this fires, that caller's own db session/arq context may
    already be gone, so this opens its own session and its own short-lived
    ARQ pool rather than depending on either.

    Imports are deferred to avoid making this low-level adapter module
    (loaded unconditionally by services/voice/factory.py) depend on the API
    router modules at import time."""
    from app.api.v1.voice import _apply_turn_side_effects, _load_prospect_for_call
    from app.api.v1.webhooks import apply_twilio_call_status
    from app.database import AsyncSessionLocal
    from app.services.voice_ai.orchestrator import VoiceOrchestrator

    await asyncio.sleep(random.uniform(*_MOCK_ANSWER_DELAY_RANGE_SECONDS))

    arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        # 1. Simulate Twilio's "answered" status callback - the same
        #    handler the real /webhooks/twilio/call-status route uses.
        async with AsyncSessionLocal() as db:
            await apply_twilio_call_status(db, arq_pool, to_number, "answered", call_sid)

        # 2. Simulate Twilio requesting the initial TwiML (the greeting
        #    turn) - the same handler /voice/webhook/incoming uses.
        call_ended = False
        async with AsyncSessionLocal() as db:
            prospect = await _load_prospect_for_call(db, prospect_id, to_number)
            if not prospect:
                logger.warning(
                    f"MockTwilioAdapter: prospect {prospect_id} not in an active call state "
                    "after simulated answer; aborting call simulation."
                )
                return
            turn = await VoiceOrchestrator.process_turn(db, prospect, call_sid, "")
            await _apply_turn_side_effects(db, prospect, turn, arq_pool)
            await db.commit()
            call_ended = turn.call_ended

        # 3. Simulate the prospect's recorded reply (one <Record> turn) -
        #    the same handler /voice/webhook/recording uses. MockSTTProvider
        #    passes this text straight through as the "transcribed" speech.
        if not call_ended:
            async with AsyncSessionLocal() as db:
                prospect = await _load_prospect_for_call(db, prospect_id, to_number)
                if prospect:
                    turn = await VoiceOrchestrator.process_turn(db, prospect, call_sid, _MOCK_PROSPECT_REPLY)
                    await _apply_turn_side_effects(db, prospect, turn, arq_pool)
                    await db.commit()

        # 4. Simulate Twilio's final "completed" status callback.
        async with AsyncSessionLocal() as db:
            await apply_twilio_call_status(db, arq_pool, to_number, "completed", call_sid)
    except Exception:
        logger.exception(f"MockTwilioAdapter: simulated call progress failed for prospect {prospect_id}")
    finally:
        await arq_pool.close()
