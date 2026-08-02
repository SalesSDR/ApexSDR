"""Sprint 5, item 3: the qualification score and active buying signals -
not a binary QUALIFIED/DISQUALIFIED flag - decide whether a would-be send
proceeds, is paused, or is escalated for human review."""
from app.models.schemas import (
    BuyingSignal,
    DecisionType,
    Prospect,
    ProspectState,
    QualificationLevel,
    SequenceStep,
    SignalStrength,
    SignalType,
)
from app.services.decision.engine import DecisionEngine

ENGINE = DecisionEngine()

_FULL_SEQUENCE = [
    SequenceStep(channel="LINKEDIN", step_number=1, title="LinkedIn", delay_minutes=60),
]


def _prospect(**overrides) -> Prospect:
    defaults = dict(
        tenant_id="t1", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada", status=ProspectState.IDLE,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


def _signal(signal_type: SignalType, strength: SignalStrength) -> BuyingSignal:
    return BuyingSignal(
        tenant_id="t1", prospect_id="p1", signal_type=signal_type,
        signal_source="test", signal_strength=strength, summary="test signal",
    )


def test_a_low_qualification_level_escalates_a_send_to_human_review():
    prospect = _prospect(qualification_level=QualificationLevel.LOW, qualification_score=10.0)
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.HUMAN_REVIEW
    assert decision.task_to_enqueue is None
    assert "LOW" in decision.reason


def test_hot_qualification_level_sends_normally():
    prospect = _prospect(qualification_level=QualificationLevel.HOT, qualification_score=90.0)
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SEND_LINKEDIN
    assert decision.task_to_enqueue is not None


def test_an_active_negative_reply_signal_pauses_outreach_instead_of_sending():
    prospect = _prospect(qualification_level=QualificationLevel.HIGH, qualification_score=70.0)
    signals = [_signal(SignalType.NEGATIVE_REPLY, SignalStrength.MEDIUM)]
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE, buying_signals=signals)
    assert decision.decision_type == DecisionType.PAUSE
    assert decision.task_to_enqueue is None


def test_a_strong_positive_signal_boosts_confidence_on_a_send_decision():
    prospect = _prospect(qualification_level=QualificationLevel.HIGH, qualification_score=70.0)
    baseline = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE, buying_signals=[])
    boosted = ENGINE.decide(
        prospect, sequence_steps=_FULL_SEQUENCE,
        buying_signals=[_signal(SignalType.COMPANY_HIRING, SignalStrength.HIGH)],
    )
    assert boosted.decision_type == baseline.decision_type
    assert boosted.confidence > baseline.confidence
    assert "confidence boosted" in boosted.reason.lower()


def test_a_weak_positive_signal_does_not_boost_confidence():
    prospect = _prospect(qualification_level=QualificationLevel.HIGH, qualification_score=70.0)
    baseline = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE, buying_signals=[])
    with_weak_signal = ENGINE.decide(
        prospect, sequence_steps=_FULL_SEQUENCE,
        buying_signals=[_signal(SignalType.COMPANY_HIRING, SignalStrength.LOW)],
    )
    assert with_weak_signal.confidence == baseline.confidence


def test_the_policy_never_applies_to_non_send_decisions():
    # A terminal-state prospect's END_SEQUENCE must not be reinterpreted,
    # even if it happens to carry a LOW qualification level.
    prospect = _prospect(status=ProspectState.LOST, qualification_level=QualificationLevel.LOW)
    decision = ENGINE.decide(prospect)
    assert decision.decision_type == DecisionType.END_SEQUENCE


def test_negative_signal_takes_priority_over_qualification_level_check_order():
    # Both conditions present: LOW level (-> HUMAN_REVIEW) is checked before
    # buying signals, so LOW wins even with a negative signal also present.
    prospect = _prospect(qualification_level=QualificationLevel.LOW, qualification_score=5.0)
    decision = ENGINE.decide(
        prospect, sequence_steps=_FULL_SEQUENCE,
        buying_signals=[_signal(SignalType.NEGATIVE_REPLY, SignalStrength.HIGH)],
    )
    assert decision.decision_type == DecisionType.HUMAN_REVIEW
