import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from asgi_correlation_id import correlation_id
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retry import evaluate_retry
from app.core.state_machine import TERMINAL_STATES
from app.models.schemas import (
    ActivityTimeline,
    BuyingSignal,
    ConversationMemory,
    DecisionLog,
    DecisionType,
    LinkedInAccount,
    MemoryType,
    PolicySeverity,
    Prospect,
    ProspectState,
    QualificationLevel,
    SequenceRule,
    SequenceStep,
    SignalStrength,
    SignalType,
    WorkspaceSetting,
)
from app.services.compliance.engine import ComplianceEngine
from app.services.linkedin.service import LinkedInQueueService, resolve_account_id
from app.services.metrics.service import decision_engine_latency
from app.services.qualification.scoring import score_prospect

logger = logging.getLogger(__name__)

# Statuses where sending goes through the LinkedIn queue, so the engine
# needs that account's pause/daily-cap state to decide confidently.
_LINKEDIN_SEND_STATUSES = (ProspectState.IDLE, ProspectState.LI_ACCEPTED_NO_MSG)

# Sequence Engine: statuses where "what's the next autonomous action" is
# answered purely by looking up the tenant's configured SequenceStep list at
# prospect.sequence_step_index - never by a fixed per-status chain. Every
# channel (LinkedIn, LinkedIn Follow-up, Email 1, Email 2, Call, Voicemail,
# Breakup Email) dispatches through the same task, execute_sequence_step_task
# (see workers/tasks.py); the ORDER prospects move through them comes
# entirely from SequenceStep.step_number, configured per tenant via
# /api/v1/sequences/steps.
_SEQUENCE_PROGRESSION_STATUSES = {
    ProspectState.IDLE,
    ProspectState.LI_REQ_SENT,
    ProspectState.LI_ACCEPTED_NO_MSG,
    ProspectState.LI_MSG_SENT,
    ProspectState.EMAIL_SENT,
    ProspectState.EMAIL_2_SENT,
    ProspectState.VOICEMAIL_LEFT,
    ProspectState.CALL_QUEUED,
    ProspectState.CALL_NO_ANSWER_1,
    ProspectState.CALL_NO_ANSWER_2,
}

# Maps a SequenceStep.channel value to the DecisionType logged for it -
# purely for audit/analytics readability, never used to pick the channel
# itself (that's entirely step_number order).
_CHANNEL_TO_DECISION_TYPE = {
    "LINKEDIN": DecisionType.SEND_LINKEDIN,
    "LINKEDIN_FOLLOWUP": DecisionType.SEND_FOLLOWUP,
    "EMAIL_1": DecisionType.SEND_EMAIL,
    "EMAIL_2": DecisionType.SEND_EMAIL,
    "CALL": DecisionType.SCHEDULE_CALL,
    "VOICEMAIL": DecisionType.SCHEDULE_CALL,
    "BREAKUP_EMAIL": DecisionType.SEND_EMAIL,
}
_LINKEDIN_CHANNELS = {"LINKEDIN", "LINKEDIN_FOLLOWUP"}
SEQUENCE_STEP_TASK_NAME = "execute_sequence_step_task"

# Sprint 5, item 3: only these are genuine "send now" outcomes eligible for
# the qualification-score/buying-signal overlay below - WAIT/END_SEQUENCE/
# BOOK_MEETING/etc. from _base_decision or the memory rules already
# represent a non-send outcome and must not be second-guessed again.
_SEND_DECISION_TYPES = {
    DecisionType.SEND_LINKEDIN, DecisionType.SEND_FOLLOWUP,
    DecisionType.SEND_EMAIL, DecisionType.SCHEDULE_CALL,
}
_STRONG_POSITIVE_SIGNAL_TYPES = {SignalType.COMPANY_HIRING, SignalType.FUNDING_EVENT, SignalType.HIGH_INTENT_REPLY}


@dataclass
class Decision:
    """A structured next-action recommendation. task_to_enqueue is the ARQ
    task name the caller should enqueue to execute this decision, or None
    for decisions with nothing to enqueue (WAIT, END_SEQUENCE, and the
    qualification calls, which the caller executes via transition_prospect()
    directly rather than a separate task)."""
    decision_type: DecisionType
    reason: str
    confidence: float
    task_to_enqueue: str | None = None
    # Module 13 (Lead Qualification): populated only by decide_qualification()
    # - the caller (run_waterfall_enrichment_task) persists these onto the
    # Prospect itself, since the engine never mutates prospect state.
    qualification_score: float | None = None
    qualification_reason: str | None = None
    qualification_level: QualificationLevel | None = None


@dataclass
class MemoryRule:
    """Table-driven rule mapping a memory condition to a Decision."""
    memory_type: MemoryType
    condition: Callable[[ConversationMemory], bool]
    decision_type: DecisionType
    reason_template: str
    confidence: float
    task_to_enqueue: str | None = None

# A deterministic table-driven rule system. First matching rule takes precedence.
MEMORY_RULES = [
    MemoryRule(
        memory_type=MemoryType.MEETING_OUTCOME,
        condition=lambda m: "lost" in m.content.lower() or "declined" in m.content.lower(),
        decision_type=DecisionType.END_SEQUENCE,
        reason_template="Meeting outcome logged as lost/declined: {content}",
        confidence=1.0
    ),
    MemoryRule(
        memory_type=MemoryType.OBJECTION,
        condition=lambda m: not m.is_resolved,
        decision_type=DecisionType.HUMAN_REVIEW,
        reason_template="Unresolved objection detected: {content}. Escalating for human review.",
        confidence=1.0
    ),
    MemoryRule(
        memory_type=MemoryType.PREFERENCE,
        condition=lambda m: m.expires_at is not None and m.expires_at > datetime.now(UTC),
        decision_type=DecisionType.WAIT,
        reason_template="Prospect asked to wait. Snoozed until {expires_at}.",
        confidence=1.0
    ),
    MemoryRule(
        memory_type=MemoryType.BUYING_SIGNAL,
        condition=lambda m: m.metadata_.get("signal_type") == "NEGATIVE_REPLY",
        decision_type=DecisionType.PAUSE,
        reason_template="Negative reply signal detected: {content}. Pausing outreach pending reassessment.",
        confidence=1.0
    ),
    MemoryRule(
        memory_type=MemoryType.BUYING_SIGNAL,
        condition=lambda m: m.metadata_.get("signal_type") == "MEETING_REQUEST",
        decision_type=DecisionType.BOOK_MEETING,
        reason_template="Meeting request signal detected: {content}. Handing over to SDR.",
        confidence=1.0
    ),
    MemoryRule(
        memory_type=MemoryType.BUYING_SIGNAL,
        condition=lambda m: m.metadata_.get("signal_type") == "JOB_CHANGE",
        decision_type=DecisionType.PAUSE,
        reason_template="Job change signal detected: {content}. Pausing outreach - recommend restarting for the new role.",
        confidence=0.9
    )
]


class DecisionEngine:
    """The single component responsible for deciding a prospect's next
    action. Consumes Prospect state (including its already-synced CRM
    hubspot_contact_id/hubspot_deal_id and Calendar google_calendar_event_id
    columns - no separate CRM/Calendar query needed, they live on the same
    row) and LinkedIn queue state (via LinkedInAccount), and returns a
    structured Decision. Never mutates prospect state and never calls an
    adapter directly - callers (ARQ workers) act on the decision by
    enqueueing task_to_enqueue or applying a transition via
    core/state_machine.py's transition_prospect(). Stateless - one instance
    is shared across all requests/tasks via ctx, same as the CRM/Calendar
    services."""

    def decide(
        self,
        prospect: Prospect,
        linkedin_account: LinkedInAccount | None = None,
        memories: list[ConversationMemory] | None = None,
        sequence_steps: list[SequenceStep] | None = None,
        buying_signals: list[BuyingSignal] | None = None,
    ) -> Decision:
        """Pure - no I/O. Callers that already have the relevant
        LinkedInAccount loaded (or know it doesn't apply) can call this
        directly; decide_for_prospect() below is the DB-aware convenience
        wrapper used by the live pipeline. sequence_steps is the tenant's
        SequenceStep rows ordered by step_number - required to decide
        anything for a prospect currently mid-sequence (see
        _SEQUENCE_PROGRESSION_STATUSES); omit it only for states that don't
        need it (qualification phase, terminal, event-driven-only states).
        buying_signals (Sprint 5, item 3) is the prospect's active
        BuyingSignal rows, consulted alongside qualification_score/level to
        decide whether a would-be send should actually proceed, be paused,
        or be escalated for human review - see
        _apply_qualification_and_signal_policy."""
        if prospect.status in TERMINAL_STATES:
            return Decision(
                DecisionType.END_SEQUENCE,
                f"{prospect.status.value} is a terminal state - no further action.",
                1.0,
            )

        # 1. Evaluate table-driven memory rules
        if memories:
            for memory in memories:
                for rule in MEMORY_RULES:
                    if memory.memory_type == rule.memory_type and rule.condition(memory):
                        return Decision(
                            decision_type=rule.decision_type,
                            reason=rule.reason_template.format(
                                content=memory.content,
                                expires_at=memory.expires_at.isoformat() if memory.expires_at else "unknown"
                            ),
                            confidence=rule.confidence,
                            task_to_enqueue=rule.task_to_enqueue
                        )

        # 2. Base Pipeline Decision
        base = self._base_decision(prospect, linkedin_account, sequence_steps or [])
        
        # 3. Apply Signal Confidence Boost
        if memories:
            boost = 0.0
            for m in memories:
                if m.memory_type == MemoryType.BUYING_SIGNAL:
                    sig_type = m.metadata_.get("signal_type")
                    if sig_type in ("HIGH_INTENT_REPLY", "COMPANY_HIRING"):
                        boost += 0.15
                    elif sig_type in ("WEBSITE_VISIT", "EMAIL_CLICK", "EMAIL_OPEN"):
                        boost += 0.05
            if boost > 0:
                base.confidence = min(1.0, round(base.confidence + boost, 2))
                base.reason += " (Confidence boosted by positive buying signals)."

        # 4. Qualification score + buying signal policy (Sprint 5, item 3):
        # may override a "send now" base decision into PAUSE or
        # HUMAN_REVIEW - no more binary QUALIFIED/DISQUALIFIED logic being
        # the only lever on live pipeline sends.
        base = self._apply_qualification_and_signal_policy(prospect, base, buying_signals or [])

        # Reuse core/retry.py's centralized retry engine: a pending retry
        # (retry_count > 0) on an action-producing decision means this is a
        # retry of a prior failure, not a fresh dispatch.
        # retry_count's ORM default only applies at flush/INSERT time, so a
        # freshly-constructed, never-persisted Prospect can have it as None
        # in memory - treat that the same as 0 rather than raising.
        retry_count = prospect.retry_count or 0
        if retry_count > 0 and base.task_to_enqueue and base.decision_type != DecisionType.WAIT:
            outcome = evaluate_retry(prospect)
            if not outcome.should_retry:
                target = outcome.new_status.value if outcome.new_status else ProspectState.ERROR_NEEDS_HUMAN.value
                return Decision(
                    DecisionType.END_SEQUENCE,
                    f"Retry budget exhausted after {prospect.retry_count} attempts - escalating to {target}.",
                    0.9,
                )
            return Decision(
                DecisionType.RETRY_LATER,
                f"{base.reason} (retry attempt {prospect.retry_count} after a prior failure).",
                round(base.confidence * 0.8, 2),
                task_to_enqueue=base.task_to_enqueue,
            )

        return base

    def decide_qualification(
        self,
        prospect: Prospect,
        workspace_setting: WorkspaceSetting | None = None,
        buying_signals: list[BuyingSignal] | None = None,
    ) -> Decision:
        """Narrower, explicit decision point called only from within
        run_waterfall_enrichment_task once it has fetched contact/company
        data. Deliberately separate from decide()/_base_decision(): both
        look at a prospect whose status is ENRICHING, but decide() (used by
        the supervisor) asks "what task should run next for a prospect stuck
        here" while this asks "given the data just fetched, qualify or
        disqualify" - conflating them under one status-keyed branch would be
        ambiguous about which question is being answered.

        Module 13: replaces the old binary "has an email or phone number"
        gate with the configurable weighted scoring engine
        (services/qualification/scoring.py). Every prospect already has a
        linkedin_url (a DB-level NOT NULL constraint) so LinkedIn is always
        a viable first channel regardless of email/phone - "contactability"
        is no longer the qualifying question; overall fit is. Only the
        bottom LOW tier is disqualified; MEDIUM/HIGH/HOT all proceed, with
        qualification_level doubling as the lead's priority tier."""
        breakdown = score_prospect(prospect, workspace_setting, buying_signals)
        decision_type = (
            DecisionType.MARK_DISQUALIFIED if breakdown.level == QualificationLevel.LOW
            else DecisionType.MARK_QUALIFIED
        )
        return Decision(
            decision_type,
            breakdown.reason,
            round(breakdown.score / 100.0, 2),
            qualification_score=breakdown.score,
            qualification_reason=breakdown.reason,
            qualification_level=breakdown.level,
        )

    # Sprint 7: maps a voice turn's suggested next_action to the DecisionType
    # this engine actually authorizes. An unrecognized/malformed next_action
    # (a bad LLM output) falls back to WAIT ("Continue") rather than raising -
    # never let a malformed LLM field crash the call or force a state change.
    _VOICE_NEXT_ACTION_TO_DECISION_TYPE = {
        "CONTINUE": DecisionType.WAIT,
        "RETRY": DecisionType.RETRY_LATER,
        "BOOK_MEETING": DecisionType.BOOK_MEETING,
        "HUMAN_REVIEW": DecisionType.HUMAN_REVIEW,
        "PAUSE": DecisionType.PAUSE,
        "CLOSE": DecisionType.END_SEQUENCE,
    }
    # Sprint 7: BOOK_MEETING actually changes the prospect's outcome
    # (MEETING_BOOKED -> calendar booking), so it needs a higher confidence
    # bar than just "the LLM said so" - a low-confidence meeting-request
    # detection is escalated to a human instead of auto-booking on a guess.
    _VOICE_BOOK_MEETING_MIN_CONFIDENCE = 0.6

    def decide_for_voice_turn(self, prospect: Prospect, next_action: str, intent: str, confidence: float) -> Decision:
        """Sprint 7: the single authority for what a live voice conversation
        turn actually does to the prospect. Voice AI (the LLM) only suggests
        `next_action` as part of its structured output - it never calls
        transition_prospect() or enqueues anything itself. This mirrors
        decide_qualification(): a narrow, explicit decision point separate
        from decide()/_base_decision(), since a mid-call turn asks a
        different question ("what does this turn mean for the prospect")
        than the autonomous supervisor's "what task should run next".

        Pure - no I/O, never mutates prospect. The caller (VoiceOrchestrator)
        applies the resulting Decision as a state transition/task-enqueue,
        exactly like every other DecisionEngine caller does."""
        decision_type = self._VOICE_NEXT_ACTION_TO_DECISION_TYPE.get(next_action, DecisionType.WAIT)

        if decision_type == DecisionType.BOOK_MEETING and confidence < self._VOICE_BOOK_MEETING_MIN_CONFIDENCE:
            return Decision(
                DecisionType.HUMAN_REVIEW,
                f"Voice AI suggested BOOK_MEETING at low confidence ({confidence}) for intent '{intent}' - "
                "escalating to a human instead of auto-booking on an uncertain signal.",
                confidence,
            )

        return Decision(
            decision_type,
            f"Voice AI turn: intent='{intent}', next_action='{next_action}'.",
            confidence,
            task_to_enqueue="book_calendar_meeting_task" if decision_type == DecisionType.BOOK_MEETING else None,
        )

    def _apply_qualification_and_signal_policy(
        self, prospect: Prospect, base: Decision, buying_signals: list[BuyingSignal],
    ) -> Decision:
        """Sprint 5, item 3: the qualification score and any active buying
        signals get the final say on whether a would-be "send now" decision
        actually proceeds, is paused, or is escalated for human review - no
        binary QUALIFIED/DISQUALIFIED logic gating live pipeline sends.
        Only applies to genuine send decisions (SEND_LINKEDIN/SEND_FOLLOWUP/
        SEND_EMAIL/SCHEDULE_CALL with a task to enqueue); WAIT/END_SEQUENCE/
        PAUSE/HUMAN_REVIEW/BOOK_MEETING from _base_decision or the memory
        rules already represent a non-send (or already-overridden) outcome
        and must not be second-guessed again."""
        if base.decision_type not in _SEND_DECISION_TYPES or not base.task_to_enqueue:
            return base

        if prospect.qualification_level == QualificationLevel.LOW:
            return Decision(
                DecisionType.HUMAN_REVIEW,
                f"Qualification score has fallen to LOW ({prospect.qualification_score}) - "
                "escalating to human review before further autonomous outreach.",
                0.9,
            )

        if any(s.signal_type == SignalType.NEGATIVE_REPLY for s in buying_signals):
            return Decision(
                DecisionType.PAUSE,
                "Active negative-reply buying signal detected - pausing outreach pending reassessment.",
                0.85,
            )

        strong_positive_signals = [
            s for s in buying_signals
            if s.signal_type in _STRONG_POSITIVE_SIGNAL_TYPES
            and s.signal_strength in (SignalStrength.HIGH, SignalStrength.VERY_HIGH)
        ]
        if strong_positive_signals:
            base.confidence = min(1.0, round(base.confidence + 0.1, 2))
            base.reason += f" Send-now confidence boosted by {len(strong_positive_signals)} strong active buying signal(s)."

        return base

    def _base_decision(self, prospect: Prospect, linkedin_account: LinkedInAccount | None, sequence_steps: list[SequenceStep]) -> Decision:
        status = prospect.status

        if status in (ProspectState.NEW, ProspectState.ENRICHING):
            return Decision(
                DecisionType.WAIT,
                "Not yet qualified - the enrichment task will fetch contact data and qualify or disqualify.",
                1.0, task_to_enqueue="run_waterfall_enrichment_task",
            )

        if status == ProspectState.LI_ACCEPTED_NO_MSG:
            if prospect.last_status_change_at and datetime.now(UTC) < prospect.last_status_change_at + timedelta(hours=24):
                return Decision(DecisionType.WAIT, "Connection accepted less than 24h ago - waiting before following up.", 0.7)
            # 24h+ with no message - falls through to the generic sequence
            # lookup below, same as every other mid-sequence status.

        if status in _SEQUENCE_PROGRESSION_STATUSES:
            return self._next_sequence_step_decision(prospect, linkedin_account, sequence_steps)

        # Everything else (PAUSED_NUDGED, EMAIL_OPENED/CLICKED, reply/booking
        # states, ENGAGED_ON_WEBSITE, ERROR_NEEDS_HUMAN) has no autonomous
        # timer-driven next step - those are event-driven (an inbound
        # webhook reply, a human resolving ERROR_NEEDS_HUMAN), not something
        # a polling decision should re-trigger on its own.
        return Decision(
            DecisionType.WAIT,
            f"{status.value} has no autonomous next step - awaiting an external event or human review.",
            0.5,
        )

    def _next_sequence_step_decision(
        self, prospect: Prospect, linkedin_account: LinkedInAccount | None, sequence_steps: list[SequenceStep],
    ) -> Decision:
        """The single place that decides "what channel comes next" for a
        prospect mid-sequence - purely by reading sequence_steps[index],
        never a hardcoded per-status chain. Every channel enqueues the same
        task (execute_sequence_step_task); only the DecisionType/reason
        differ, for audit-log readability."""
        index = prospect.sequence_step_index or 0
        if index >= len(sequence_steps):
            return Decision(
                DecisionType.WAIT,
                f"{prospect.status.value}: no further sequence step configured (index {index} of {len(sequence_steps)}).",
                0.5,
            )

        step = sequence_steps[index]
        decision_type = _CHANNEL_TO_DECISION_TYPE.get(step.channel, DecisionType.WAIT)
        reason = f"Advancing sequence from {prospect.status.value}: next configured step is '{step.title}' ({step.channel})."

        if step.channel in _LINKEDIN_CHANNELS:
            return self._linkedin_send_decision(decision_type, SEQUENCE_STEP_TASK_NAME, reason, 0.9, linkedin_account)

        return Decision(decision_type, reason, 0.85, task_to_enqueue=SEQUENCE_STEP_TASK_NAME)

    def _linkedin_send_decision(
        self, decision_type: DecisionType, task_name: str, reason: str, confidence: float,
        linkedin_account: LinkedInAccount | None,
    ) -> Decision:
        if linkedin_account is not None:
            allowed, block_reason = LinkedInQueueService.can_send(linkedin_account)
            if not allowed:
                detail = "daily send limit reached" if block_reason == "daily_limit_reached" else "account is currently paused"
                return Decision(DecisionType.WAIT, f"LinkedIn queue unavailable ({detail}) - deferring {task_name}.", 0.6)
        return Decision(decision_type, reason, confidence, task_to_enqueue=task_name)

    async def decide_for_prospect(self, db: AsyncSession, prospect: Prospect) -> Decision:
        """DB-aware convenience wrapper: resolves the relevant LinkedInAccount
        (if this decision would depend on one), fetches active memory
        context, the tenant's ordered SequenceStep list, and active buying
        signals (Sprint 5, item 3), then calls the pure decide()."""
        from app.services.memory.service import ConversationMemoryService

        active_memories = await ConversationMemoryService.get_active_context(db, prospect.tenant_id, prospect.id)

        signals_res = await db.execute(
            select(BuyingSignal).where(
                BuyingSignal.tenant_id == prospect.tenant_id,
                BuyingSignal.prospect_id == prospect.id,
                BuyingSignal.is_active == True,
            )
        )
        active_signals = list(signals_res.scalars().all())

        sequence_steps: list[SequenceStep] = []
        if prospect.status in _SEQUENCE_PROGRESSION_STATUSES:
            rule_res = await db.execute(select(SequenceRule).where(SequenceRule.tenant_id == prospect.tenant_id))
            rule_obj = rule_res.scalar_one_or_none()
            if rule_obj:
                steps_res = await db.execute(
                    select(SequenceStep).where(SequenceStep.sequence_rule_id == rule_obj.id).order_by(SequenceStep.step_number)
                )
                sequence_steps = list(steps_res.scalars().all())

        linkedin_account = None
        if prospect.status in _LINKEDIN_SEND_STATUSES:
            account_id = resolve_account_id(prospect.tenant_id)
            res = await db.execute(
                select(LinkedInAccount).where(
                    LinkedInAccount.tenant_id == prospect.tenant_id,
                    LinkedInAccount.account_id == account_id,
                )
            )
            linkedin_account = res.scalar_one_or_none()

        return self.decide(
            prospect, linkedin_account=linkedin_account, memories=active_memories,
            sequence_steps=sequence_steps, buying_signals=active_signals,
        )

    async def record_decision(self, db: AsyncSession, prospect: Prospect, decision: Decision, cid: str | None = None):
        """Persist the AI's decision to the audit log. Sprint 6, item 4:
        also snapshots the prospect's qualification_level/score AT THIS
        MOMENT - read directly off `prospect`, not `decision`, since by the
        time record_decision runs the prospect already carries the correct
        value either way: for decide_qualification's own decision, the
        caller (run_waterfall_enrichment_task) sets
        prospect.qualification_level/score from the decision *before*
        calling record_decision; for every other decision, qualification
        already happened in an earlier pass and hasn't changed since. This
        is what makes analytics queries able to use a true historical
        snapshot instead of joining to Prospect's current value."""
        log = DecisionLog(
            tenant_id=prospect.tenant_id,
            prospect_id=prospect.id,
            decision_type=decision.decision_type,
            reason=decision.reason,
            confidence=decision.confidence,
            prospect_status_at_decision=prospect.current_state,
            qualification_level_at_decision=prospect.qualification_level,
            qualification_score_at_decision=prospect.qualification_score,
            correlation_id=cid
        )
        db.add(log)
        await db.flush()
        logger.info(f"Decision for prospect {prospect.id}: {decision.decision_type.value} ({decision.confidence}) - {decision.reason}")
        return log

    async def apply_compliance_gate(
        self, db: AsyncSession, prospect: Prospect, decision: Decision, cid: str | None = None,
    ) -> Decision:
        """Sprint 7.1: extracted from decide_and_record so every caller that
        turns a Decision into a real action - the autonomous supervisor via
        decide_and_record below, and VoiceOrchestrator for live voice turns
        (services/voice_ai/orchestrator.py) - runs it through the same
        compliance gate, rather than the autonomous pipeline being the only
        path compliance ever sees. Returns `decision` unchanged if allowed,
        or an overriding END_SEQUENCE/WAIT decision (and logs the
        violation) if not."""
        compliance_engine = ComplianceEngine()
        check = await compliance_engine.validate(db, prospect, decision.decision_type)

        if check.is_allowed:
            return decision

        await compliance_engine.record_violation(db, prospect, decision.decision_type, check, cid)

        if check.severity == PolicySeverity.PERMANENT_BLOCK:
            decision = Decision(
                decision_type=DecisionType.END_SEQUENCE,
                reason=f"Permanently blocked by compliance: {check.reason}",
                confidence=1.0
            )
        else:  # TEMPORARY_BLOCK
            decision = Decision(
                decision_type=DecisionType.WAIT,
                reason=f"Temporarily blocked by compliance: {check.reason}",
                confidence=1.0
            )

        timeline_event = ActivityTimeline(
            tenant_id=prospect.tenant_id,
            prospect_id=prospect.id,
            channel="SYSTEM",
            event_type="COMPLIANCE_BLOCK",
            description=f"Action {decision.decision_type.value} blocked by {check.policy_type.value}: {check.reason}",
            correlation_id=cid
        )
        db.add(timeline_event)
        await db.flush()
        return decision

    async def decide_and_record(self, db: AsyncSession, prospect: Prospect) -> Decision:
        start_time = time.time()
        decision = await self.decide_for_prospect(db, prospect)
        decision_engine_latency.observe(time.time() - start_time)

        current_cid = correlation_id.get() or str(uuid.uuid4())

        decision = await self.apply_compliance_gate(db, prospect, decision, current_cid)

        await self.record_decision(db, prospect, decision, current_cid)
        return decision
