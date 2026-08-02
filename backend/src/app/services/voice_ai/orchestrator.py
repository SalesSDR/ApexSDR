import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompt_security import flag_suspicious
from app.core.state_machine import transition_prospect
from app.models.schemas import DecisionType, Prospect, ProspectState
from app.services.decision.engine import Decision, DecisionEngine
from app.services.metrics.service import voice_latency
from app.services.personalization import PersonalizationService
from app.services.voice_ai.conversation import (
    ConversationContext,
    ConversationManager,
    VoiceResponse,
)
from app.services.voice_ai.factory import get_voice_ai_provider
from app.services.voice_ai.transcript import TranscriptService

logger = logging.getLogger(__name__)

# A "retry" (call-back-later) outcome re-queues the call rather than ending
# the sequence entirely - a short delay so the retry doesn't relaunch
# mid-conversation-loop, but still same-day.
_RETRY_CALL_BACK_DELAY = timedelta(hours=1)


@dataclass
class TurnResult:
    """What the API layer needs to render TwiML and decide whether to place
    follow-up tasks (calendar booking, CRM sync) - those side effects belong
    to the caller (which already holds the request-scoped arq_pool/http
    client), not this service module. See VoiceOrchestrator docstring."""

    voice_response: VoiceResponse
    decision: Decision
    call_ended: bool


class VoiceOrchestrator:
    """Sprint 7: the full per-turn pipeline - Conversation Manager limits,
    the LLM call, transcript/memory persistence, and hand-off to the
    Decision Engine, which is the ONLY thing that changes Prospect state
    (via _apply_decision below, which does nothing but translate a Decision
    into transition_prospect() - it never invents an outcome the Decision
    Engine didn't return). Voice AI itself (the LLM provider) never touches
    Prospect state or the database - it only returns a VoiceResponse."""

    @staticmethod
    async def process_turn(db: AsyncSession, prospect: Prospect, call_sid: str, user_speech: str) -> TurnResult:
        transcript = await TranscriptService.get_or_create_transcript(db, call_sid, prospect)

        if ConversationManager.should_terminate_for_turns(transcript.total_turns):
            return await VoiceOrchestrator._terminate(db, prospect, transcript, user_speech, "max_turns")
        if ConversationManager.should_terminate_for_duration(transcript.created_at):
            return await VoiceOrchestrator._terminate(db, prospect, transcript, user_speech, "max_duration")

        # An empty user_speech on the very first turn means the call just
        # connected and nothing has been said yet (there's no prior turn to
        # have gone silent after) - that's a greeting prompt, not silence.
        if transcript.total_turns > 0 and ConversationManager.is_silence(user_speech):
            return await VoiceOrchestrator._handle_silence(db, prospect, transcript, user_speech)

        if flag_suspicious(user_speech):
            logger.warning(f"Voice turn for call {call_sid} matches a known prompt-injection pattern.")

        if transcript.metadata_.get("consecutive_silences"):
            transcript.metadata_ = {**transcript.metadata_, "consecutive_silences": 0}

        context = await VoiceOrchestrator._build_context(db, prospect, transcript)

        start_time = time.perf_counter()
        provider = get_voice_ai_provider()
        response: VoiceResponse = await provider.generate_response(context, user_speech)
        voice_latency.observe(time.perf_counter() - start_time)

        await TranscriptService.add_turn(db, transcript, user_speech, response)

        decision = DecisionEngine().decide_for_voice_turn(
            prospect, response.next_action, response.intent, response.confidence,
        )
        # Sprint 7.1: every Decision Engine action - voice turns included -
        # passes through the same compliance gate the autonomous pipeline
        # uses, before it's recorded or applied.
        decision = await DecisionEngine().apply_compliance_gate(db, prospect, decision, cid=call_sid)
        await DecisionEngine().record_decision(db, prospect, decision, cid=call_sid)
        call_ended = VoiceOrchestrator._apply_decision(prospect, transcript, decision)

        return TurnResult(voice_response=response, decision=decision, call_ended=call_ended)

    @staticmethod
    async def _handle_silence(db: AsyncSession, prospect: Prospect, transcript, user_speech: str) -> TurnResult:
        silences = transcript.metadata_.get("consecutive_silences", 0) + 1
        transcript.metadata_ = {**transcript.metadata_, "consecutive_silences": silences}

        if ConversationManager.should_terminate_for_silence(silences):
            return await VoiceOrchestrator._terminate(db, prospect, transcript, user_speech, "silence")

        response = ConversationManager.get_reprompt_response()
        await TranscriptService.add_turn(db, transcript, user_speech, response)
        decision = Decision(DecisionType.WAIT, "Silent turn - reprompting.", 1.0)
        return TurnResult(voice_response=response, decision=decision, call_ended=False)

    @staticmethod
    async def _terminate(db: AsyncSession, prospect: Prospect, transcript, user_speech: str, reason: str) -> TurnResult:
        response = ConversationManager.get_fallback_response(reason)
        await TranscriptService.add_turn(db, transcript, user_speech, response)

        decision = DecisionEngine().decide_for_voice_turn(
            prospect, response.next_action, response.intent, response.confidence,
        )
        decision = await DecisionEngine().apply_compliance_gate(db, prospect, decision, cid=transcript.call_sid)
        await DecisionEngine().record_decision(db, prospect, decision, cid=transcript.call_sid)
        VoiceOrchestrator._apply_decision(prospect, transcript, decision)
        transcript.status = "COMPLETED"
        await db.flush()
        return TurnResult(voice_response=response, decision=decision, call_ended=True)

    @staticmethod
    async def _build_context(db: AsyncSession, prospect: Prospect, transcript) -> ConversationContext:
        history = await TranscriptService.get_recent_history(db, transcript.id)
        # Sprint 7, item 4: the same rich context every other outbound
        # channel gets (services/personalization.py) - qualification,
        # buying signals, company enrichment, conversation memory.
        personalization = await PersonalizationService.build_context(db, prospect)
        return ConversationContext(
            prospect_name=prospect.first_name or "there",
            company_name=prospect.company_name,
            current_state="QUALIFYING" if transcript.total_turns < 4 else "PITCHING",
            recent_history=history,
            qualification_summary=personalization.get("qualification_summary"),
            buying_signals=personalization.get("buying_signals"),
            company_description=personalization.get("company_description"),
            industry=personalization.get("industry"),
            recent_news=personalization.get("recent_news"),
            conversation_memory=personalization.get("conversation_memory"),
        )

    @staticmethod
    def _apply_decision(prospect: Prospect, transcript, decision: Decision) -> bool:
        """The ONLY place a voice conversation changes Prospect state -
        translates the Decision Engine's Decision into transition_prospect(),
        exactly like autonomous_pipeline_supervisor_task does for the
        autonomous pipeline. Never reads response.intent/next_action
        directly - only ever the already-decided Decision. Returns whether
        the call should end now."""
        call_ended = False

        if decision.decision_type == DecisionType.BOOK_MEETING:
            transition_prospect(prospect, ProspectState.MEETING_BOOKED)
            prospect.next_action_at = None
            call_ended = True
        elif decision.decision_type == DecisionType.HUMAN_REVIEW:
            transition_prospect(prospect, ProspectState.ERROR_NEEDS_HUMAN)
            prospect.next_action_at = None
            call_ended = True
        elif decision.decision_type == DecisionType.END_SEQUENCE:
            transition_prospect(prospect, ProspectState.COMPLETED_DECLINED)
            prospect.next_action_at = None
            call_ended = True
        elif decision.decision_type == DecisionType.RETRY_LATER:
            transition_prospect(prospect, ProspectState.CALL_QUEUED)
            prospect.next_action_at = datetime.now(UTC) + _RETRY_CALL_BACK_DELAY
            call_ended = True
        elif decision.decision_type == DecisionType.PAUSE:
            # Deliberately no transition - matches the autonomous
            # supervisor's PAUSE handling: parked, not failed.
            call_ended = True
        # WAIT ("Continue"): no transition, call_ended stays False.

        if call_ended:
            transcript.status = "COMPLETED"
        return call_ended
