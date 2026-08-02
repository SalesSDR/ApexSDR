from datetime import UTC, datetime, timedelta

from app.models.schemas import ConversationMemory, DecisionType, MemoryType, Prospect, ProspectState, SequenceStep
from app.services.decision.engine import DecisionEngine


def _step(channel: str, step_number: int) -> SequenceStep:
    return SequenceStep(channel=channel, step_number=step_number, title=channel, delay_minutes=60)


_FULL_SEQUENCE = [
    _step("LINKEDIN", 1),
    _step("LINKEDIN_FOLLOWUP", 2),
    _step("EMAIL_1", 3),
    _step("EMAIL_2", 4),
    _step("CALL", 5),
    _step("VOICEMAIL", 6),
    _step("BREAKUP_EMAIL", 7),
]


def test_decision_engine_obeys_objection_memory():
    engine = DecisionEngine()
    prospect = Prospect(status=ProspectState.IDLE)

    # Normally IDLE goes to SEND_LINKEDIN
    decision = engine.decide(prospect, memories=[], sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SEND_LINKEDIN

    # With unresolved objection, overrides to HUMAN_REVIEW (Sprint 5, item 3:
    # PAUSE/HUMAN_REVIEW replace the old WAIT-for-everything memory rules).
    objection = ConversationMemory(
        memory_type=MemoryType.OBJECTION,
        content="Not interested",
        is_resolved=False,
    )
    decision_with_memory = engine.decide(prospect, memories=[objection], sequence_steps=_FULL_SEQUENCE)
    assert decision_with_memory.decision_type == DecisionType.HUMAN_REVIEW
    assert "Unresolved objection detected" in decision_with_memory.reason

    # If objection is resolved, it ignores it and returns to SEND_LINKEDIN
    resolved_objection = ConversationMemory(
        memory_type=MemoryType.OBJECTION,
        content="Not interested",
        is_resolved=True,
    )
    decision_resolved = engine.decide(prospect, memories=[resolved_objection], sequence_steps=_FULL_SEQUENCE)
    assert decision_resolved.decision_type == DecisionType.SEND_LINKEDIN


def test_decision_engine_obeys_meeting_outcome_memory():
    engine = DecisionEngine()
    # index=4 -> CALL, so the "normal" decision below is SCHEDULE_CALL
    prospect = Prospect(status=ProspectState.EMAIL_SENT, sequence_step_index=4)

    # Normally EMAIL_SENT (at this index) goes to SCHEDULE_CALL
    decision = engine.decide(prospect, memories=[], sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SCHEDULE_CALL

    # If meeting outcome lost, ends sequence
    lost_meeting = ConversationMemory(
        memory_type=MemoryType.MEETING_OUTCOME,
        content="Meeting lost, no budget.",
    )
    decision_with_memory = engine.decide(prospect, memories=[lost_meeting], sequence_steps=_FULL_SEQUENCE)
    assert decision_with_memory.decision_type == DecisionType.END_SEQUENCE
    assert "Meeting outcome logged as lost/declined" in decision_with_memory.reason


def test_decision_engine_obeys_preference_memory():
    engine = DecisionEngine()
    # index=1 -> LINKEDIN_FOLLOWUP (step 0/LINKEDIN already completed)
    prospect = Prospect(status=ProspectState.LI_ACCEPTED_NO_MSG, sequence_step_index=1)

    future_date = datetime.now(UTC) + timedelta(days=7)
    preference = ConversationMemory(
        memory_type=MemoryType.PREFERENCE,
        content="Follow up next week",
        expires_at=future_date
    )
    decision = engine.decide(prospect, memories=[preference], sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.WAIT
    assert "Snoozed until" in decision.reason

    # If expired, it should ignore
    past_date = datetime.now(UTC) - timedelta(days=1)
    expired_preference = ConversationMemory(
        memory_type=MemoryType.PREFERENCE,
        content="Follow up next week",
        expires_at=past_date
    )
    decision_expired = engine.decide(prospect, memories=[expired_preference], sequence_steps=_FULL_SEQUENCE)
    # Should proceed with followup
    assert decision_expired.decision_type == DecisionType.SEND_FOLLOWUP
