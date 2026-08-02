import pytest

from app.core.state_machine import (
    ALWAYS_ALLOWED_TARGETS,
    TERMINAL_STATES,
    IllegalStateTransitionError,
    transition_prospect,
    validate_transition,
)
from app.models.schemas import Prospect, ProspectState


def _prospect(status: ProspectState) -> Prospect:
    return Prospect(
        tenant_id="test-tenant",
        first_name="Grace",
        last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace",
        status=status,
    )


# --- Qualification phase (Module 3) ---

def test_qualification_chain_new_to_idle_is_legal():
    validate_transition(ProspectState.NEW, ProspectState.ENRICHING)
    validate_transition(ProspectState.ENRICHING, ProspectState.QUALIFIED)
    validate_transition(ProspectState.QUALIFIED, ProspectState.IDLE)


def test_enriching_can_disqualify():
    validate_transition(ProspectState.ENRICHING, ProspectState.DISQUALIFIED)


def test_disqualified_is_terminal():
    assert ProspectState.DISQUALIFIED in TERMINAL_STATES
    with pytest.raises(IllegalStateTransitionError):
        validate_transition(ProspectState.DISQUALIFIED, ProspectState.IDLE)


def test_new_cannot_skip_straight_to_qualified():
    with pytest.raises(IllegalStateTransitionError):
        validate_transition(ProspectState.NEW, ProspectState.QUALIFIED)


# --- General graph correctness ---

def test_same_state_transition_is_a_noop():
    # Idempotent retries/re-affirmations shouldn't need special-casing.
    validate_transition(ProspectState.IDLE, ProspectState.IDLE)
    validate_transition(ProspectState.DISQUALIFIED, ProspectState.DISQUALIFIED)


def test_illegal_transition_raises():
    with pytest.raises(IllegalStateTransitionError):
        validate_transition(ProspectState.NEW, ProspectState.MEETING_BOOKED)


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATES, key=lambda s: s.value))
def test_terminal_states_reject_every_outbound_transition_including_always_allowed(terminal):
    # Terminal states must reject everything, even ALWAYS_ALLOWED_TARGETS -
    # once closed, a prospect never re-enters the pipeline via a raw transition.
    for target in ALWAYS_ALLOWED_TARGETS:
        if target == terminal:
            continue
        with pytest.raises(IllegalStateTransitionError):
            validate_transition(terminal, target)


@pytest.mark.parametrize("target", sorted(ALWAYS_ALLOWED_TARGETS, key=lambda s: s.value))
def test_always_allowed_targets_reachable_from_any_non_terminal_state(target):
    for state in ProspectState:
        if state in TERMINAL_STATES or state == target:
            continue
        validate_transition(state, target)  # must not raise


def test_call_connected_reachable_from_call_in_progress_only():
    validate_transition(ProspectState.CALL_IN_PROGRESS, ProspectState.CALL_CONNECTED)
    with pytest.raises(IllegalStateTransitionError):
        validate_transition(ProspectState.CALL_QUEUED, ProspectState.CALL_CONNECTED)


# --- transition_prospect() mutation behavior ---

def test_transition_prospect_mutates_status_on_success():
    prospect = _prospect(ProspectState.IDLE)
    transition_prospect(prospect, ProspectState.LI_REQ_SENT)
    assert prospect.status == ProspectState.LI_REQ_SENT


def test_transition_prospect_does_not_mutate_status_on_illegal_transition():
    prospect = _prospect(ProspectState.NEW)
    with pytest.raises(IllegalStateTransitionError):
        transition_prospect(prospect, ProspectState.MEETING_BOOKED)
    assert prospect.status == ProspectState.NEW


def test_transition_prospect_from_terminal_state_raises_and_does_not_mutate():
    prospect = _prospect(ProspectState.DISQUALIFIED)
    with pytest.raises(IllegalStateTransitionError):
        transition_prospect(prospect, ProspectState.ENGAGED_ON_WEBSITE)
    assert prospect.status == ProspectState.DISQUALIFIED
