import logging

from app.models.schemas import Prospect, ProspectState

logger = logging.getLogger(__name__)


class IllegalStateTransitionError(Exception):
    """Raised when a transition isn't in ALLOWED_TRANSITIONS for the
    prospect's current status. This is the single validated choke point for
    every status change in the codebase - every task/webhook/route that
    moves a prospect between states must go through transition_prospect()
    rather than assigning `prospect.status` directly, so there is exactly
    one place illegal transitions are rejected."""


# Reachable from any non-terminal state: a website visit, an inbound reply,
# or an unrecoverable pipeline error can all legitimately happen regardless
# of where a prospect currently sits in the outreach flow (e.g. a LinkedIn
# reply can arrive well after the pipeline has already escalated to email).
ALWAYS_ALLOWED_TARGETS = {
    ProspectState.ERROR_NEEDS_HUMAN,
    ProspectState.ENGAGED_ON_WEBSITE,
    ProspectState.LINKEDIN_REPLIED,
    ProspectState.EMAIL_REPLIED,
}

# Terminal states: no outbound transition is legal from here (other than the
# always-allowed targets above, still permitted below via ALWAYS_ALLOWED_TARGETS).
TERMINAL_STATES = {
    ProspectState.DISQUALIFIED,
    ProspectState.COMPLETED_DECLINED,
    ProspectState.UNRESPONSIVE_DEAD,
    ProspectState.LOST,
    ProspectState.CLOSED_WON,
}

ALLOWED_TRANSITIONS: dict[ProspectState, set[ProspectState]] = {
    # Pre-outreach qualification phase
    ProspectState.NEW: {ProspectState.ENRICHING},
    ProspectState.ENRICHING: {ProspectState.QUALIFIED, ProspectState.DISQUALIFIED},
    ProspectState.QUALIFIED: {ProspectState.IDLE},
    ProspectState.DISQUALIFIED: set(),

    # Outreach entry point
    ProspectState.IDLE: {ProspectState.LI_REQ_SENT},

    # LinkedIn channel
    ProspectState.LI_REQ_SENT: {
        ProspectState.LI_ACCEPTED_NO_MSG, ProspectState.LINKEDIN_NO_RESPONSE, ProspectState.EMAIL_SENT,
    },
    ProspectState.LI_ACCEPTED_NO_MSG: {ProspectState.LI_MSG_SENT},
    ProspectState.LI_MSG_SENT: {ProspectState.EMAIL_SENT},
    ProspectState.LINKEDIN_NO_RESPONSE: {ProspectState.EMAIL_SENT},
    ProspectState.LINKEDIN_REPLIED: {
        ProspectState.MEETING_BOOKED, ProspectState.PAUSED_NUDGED, ProspectState.COMPLETED_DECLINED,
    },

    # Email channel
    ProspectState.EMAIL_SENT: {
        ProspectState.EMAIL_OPENED, ProspectState.EMAIL_CLICKED, ProspectState.EMAIL_FAILED,
        ProspectState.EMAIL_2_SENT, ProspectState.CALL_QUEUED, ProspectState.CALL_IN_PROGRESS,
        ProspectState.UNRESPONSIVE_DEAD,  # no phone number on record - execute_call_task can reach this directly
    },
    ProspectState.EMAIL_OPENED: {
        ProspectState.EMAIL_CLICKED, ProspectState.EMAIL_2_SENT, ProspectState.CALL_QUEUED, ProspectState.CALL_IN_PROGRESS,
    },
    ProspectState.EMAIL_CLICKED: {ProspectState.EMAIL_2_SENT, ProspectState.CALL_QUEUED, ProspectState.CALL_IN_PROGRESS},
    ProspectState.EMAIL_FAILED: {ProspectState.EMAIL_2_SENT, ProspectState.CALL_QUEUED, ProspectState.CALL_IN_PROGRESS},
    ProspectState.EMAIL_REPLIED: {
        ProspectState.MEETING_BOOKED, ProspectState.PAUSED_NUDGED, ProspectState.COMPLETED_DECLINED,
    },
    # Email 2 (Sequence Engine step 4) - same shape as EMAIL_SENT above, one
    # step further down whatever order the tenant's SequenceStep list uses.
    ProspectState.EMAIL_2_SENT: {
        ProspectState.EMAIL_OPENED, ProspectState.EMAIL_CLICKED, ProspectState.EMAIL_FAILED,
        ProspectState.CALL_QUEUED, ProspectState.CALL_IN_PROGRESS, ProspectState.UNRESPONSIVE_DEAD,
    },

    # Call channel
    ProspectState.CALL_QUEUED: {ProspectState.CALL_IN_PROGRESS, ProspectState.UNRESPONSIVE_DEAD},
    ProspectState.CALL_IN_PROGRESS: {
        ProspectState.CALL_CONNECTED, ProspectState.CALL_NO_ANSWER_1, ProspectState.CALL_FAILED, ProspectState.UNRESPONSIVE_DEAD,
        ProspectState.MEETING_BOOKED,  # some Twilio integrations never emit a distinct "answered" event
    },
    # CALL_QUEUED (Sprint 7): a live voice conversation can end with a
    # "call me back" outcome (Decision Engine's RETRY_LATER for a voice
    # turn) - re-queues the call rather than leaving the prospect stranded
    # in CALL_CONNECTED with no legal way forward.
    ProspectState.CALL_CONNECTED: {ProspectState.MEETING_BOOKED, ProspectState.COMPLETED_DECLINED, ProspectState.CALL_QUEUED},
    ProspectState.CALL_NO_ANSWER_1: {
        ProspectState.CALL_IN_PROGRESS, ProspectState.CALL_NO_ANSWER_2, ProspectState.CALL_RETRY,
        ProspectState.UNRESPONSIVE_DEAD,  # no phone number on record - execute_call_task can reach this directly
    },
    ProspectState.CALL_NO_ANSWER_2: {
        ProspectState.CALL_IN_PROGRESS, ProspectState.CALL_RETRY, ProspectState.UNRESPONSIVE_DEAD,
        ProspectState.VOICEMAIL_LEFT,  # call retries exhausted - Sequence Engine moves on to the Voicemail step
    },
    ProspectState.CALL_RETRY: {ProspectState.CALL_IN_PROGRESS},
    ProspectState.CALL_FAILED: {ProspectState.UNRESPONSIVE_DEAD, ProspectState.VOICEMAIL_LEFT},

    # Voicemail (Sequence Engine step 6) and Breakup Email (step 7) - the
    # final two configurable steps after Call.
    ProspectState.VOICEMAIL_LEFT: {ProspectState.BREAKUP_EMAIL_SENT, ProspectState.UNRESPONSIVE_DEAD},
    ProspectState.BREAKUP_EMAIL_SENT: {ProspectState.UNRESPONSIVE_DEAD, ProspectState.COMPLETED_DECLINED},

    # Post-engagement outcomes
    ProspectState.MEETING_BOOKED: {ProspectState.CLOSED_WON, ProspectState.COMPLETED_DECLINED, ProspectState.LOST},
    ProspectState.PAUSED_NUDGED: {
        ProspectState.MEETING_BOOKED, ProspectState.COMPLETED_DECLINED, ProspectState.LOST,
        ProspectState.EMAIL_SENT, ProspectState.LI_MSG_SENT, ProspectState.CALL_IN_PROGRESS,
    },

    # Terminal states
    ProspectState.COMPLETED_DECLINED: set(),
    ProspectState.UNRESPONSIVE_DEAD: set(),
    ProspectState.LOST: set(),
    ProspectState.CLOSED_WON: set(),

    # Escape-hatch states can recover back into the pipeline
    ProspectState.ERROR_NEEDS_HUMAN: {ProspectState.IDLE},
    ProspectState.ENGAGED_ON_WEBSITE: {ProspectState.MEETING_BOOKED, ProspectState.COMPLETED_DECLINED},
}

# Sequence-step "completed" states, in the tenant-configurable order the
# Sequence Engine may run them (LinkedIn, LinkedIn Follow-up, Email 1,
# Email 2, Call, Voicemail, Breakup Email - see workers/tasks.py's
# execute_sequence_step_task). A tenant's SequenceStep rows can put these
# channels in ANY order or skip some entirely, so the state machine allows
# jumping from any one of these states directly to any LATER one in this
# reference list - it only guards against moving *backward* or skipping
# into an unrelated state, never against which specific channel is next.
# ALLOWED_TRANSITIONS above still governs every other kind of transition
# (event-driven replies, call sub-state retries, terminal states) unchanged.
_SEQUENCE_STEP_STATE_ORDER = [
    ProspectState.IDLE,
    ProspectState.LI_REQ_SENT,
    ProspectState.LI_ACCEPTED_NO_MSG,
    ProspectState.LI_MSG_SENT,
    ProspectState.EMAIL_SENT,
    ProspectState.EMAIL_2_SENT,
    ProspectState.CALL_IN_PROGRESS,
    ProspectState.VOICEMAIL_LEFT,
    ProspectState.BREAKUP_EMAIL_SENT,
]
_SEQUENCE_STEP_STATE_INDEX = {state: i for i, state in enumerate(_SEQUENCE_STEP_STATE_ORDER)}


def _is_forward_sequence_progression(current: ProspectState, new: ProspectState) -> bool:
    current_idx = _SEQUENCE_STEP_STATE_INDEX.get(current)
    new_idx = _SEQUENCE_STEP_STATE_INDEX.get(new)
    if current_idx is None or new_idx is None:
        return False
    return new_idx > current_idx


def validate_transition(current: ProspectState, new: ProspectState) -> None:
    """Raises IllegalStateTransitionError if `current -> new` isn't allowed.
    A transition to the same state is always a no-op allowed (idempotent
    retries/re-affirmations shouldn't need special-casing at every call site).
    Terminal states reject every transition, even the always-allowed targets -
    once closed, a prospect only re-enters the pipeline through deliberate
    business logic (e.g. a new campaign), never a raw status transition."""
    if current == new:
        return
    if current in TERMINAL_STATES:
        raise IllegalStateTransitionError(f"Illegal state transition: {current.value} -> {new.value} (terminal state)")
    if new in ALWAYS_ALLOWED_TARGETS:
        return
    if _is_forward_sequence_progression(current, new):
        return
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise IllegalStateTransitionError(f"Illegal state transition: {current.value} -> {new.value}")


def transition_prospect(prospect: Prospect, new_state: ProspectState) -> None:
    """The single validated choke point for changing prospect.status."""
    validate_transition(prospect.status, new_state)
    if prospect.status != new_state:
        logger.info(f"Prospect {prospect.id} transitioning {prospect.status.value} -> {new_state.value}")
    prospect.status = new_state
