from datetime import UTC, datetime, timedelta

from app.core.state_machine import TERMINAL_STATES
from app.models.schemas import DecisionType, LinkedInAccount, Prospect, ProspectState, SequenceStep
from app.services.decision.engine import SEQUENCE_STEP_TASK_NAME, DecisionEngine

ENGINE = DecisionEngine()


def _step(channel: str, step_number: int = 1, title: str = None) -> SequenceStep:
    return SequenceStep(channel=channel, step_number=step_number, title=title or channel, delay_minutes=60)


# The Sequence Engine's default 7-step order (see api/v1/sequences.py's
# _DEFAULT_SEQUENCE_STEPS) - used by tests below that exercise a prospect
# mid-sequence, so decide() has something to look up at
# prospect.sequence_step_index instead of "no further step configured".
_FULL_SEQUENCE = [
    _step("LINKEDIN", 1),
    _step("LINKEDIN_FOLLOWUP", 2),
    _step("EMAIL_1", 3),
    _step("EMAIL_2", 4),
    _step("CALL", 5),
    _step("VOICEMAIL", 6),
    _step("BREAKUP_EMAIL", 7),
]


def _prospect(status: ProspectState, **overrides) -> Prospect:
    defaults = dict(
        tenant_id="test-tenant",
        first_name="Grace",
        last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace",
        status=status,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


def _account(**overrides) -> LinkedInAccount:
    from datetime import date
    defaults = dict(
        tenant_id="test-tenant", account_id="acc_1", daily_send_count=0, daily_limit=20,
        daily_count_date=date.today(), is_paused=False,
    )
    defaults.update(overrides)
    return LinkedInAccount(**defaults)


# --- Every state is handled without raising ("invalid state" coverage) ---

def test_decide_never_raises_for_any_prospect_state():
    for state in ProspectState:
        prospect = _prospect(state)
        decision = ENGINE.decide(prospect)
        assert isinstance(decision.decision_type, DecisionType)
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.reason


def test_every_terminal_state_yields_end_sequence():
    for state in TERMINAL_STATES:
        decision = ENGINE.decide(_prospect(state))
        assert decision.decision_type == DecisionType.END_SEQUENCE
        assert decision.task_to_enqueue is None


def test_terminal_check_takes_priority_over_retry_count():
    # A terminal-state prospect that also happens to carry a stale
    # retry_count must still be END_SEQUENCE, not RETRY_LATER.
    prospect = _prospect(ProspectState.DISQUALIFIED, retry_count=2)
    decision = ENGINE.decide(prospect)
    assert decision.decision_type == DecisionType.END_SEQUENCE


# --- Qualification phase entry points ---

def test_new_prospect_waits_for_enrichment():
    decision = ENGINE.decide(_prospect(ProspectState.NEW))
    assert decision.decision_type == DecisionType.WAIT
    assert decision.task_to_enqueue == "run_waterfall_enrichment_task"


def test_enriching_prospect_also_waits_for_enrichment_task_via_decide():
    # decide()/_base_decision() answers "what task should run next" - it must
    # NOT itself qualify/disqualify (see decide_qualification for that).
    decision = ENGINE.decide(_prospect(ProspectState.ENRICHING, email="x@example.com"))
    assert decision.decision_type == DecisionType.WAIT
    assert decision.task_to_enqueue == "run_waterfall_enrichment_task"


def test_decide_qualification_marks_qualified_with_a_strong_enough_score():
    # Module 13: qualification is no longer binary "has email or phone" -
    # it's the weighted score across 12 factors (services/qualification/
    # scoring.py). A corporate-looking email domain lifts the
    # email_quality factor enough to cross the default MEDIUM threshold on
    # an otherwise bare profile.
    prospect = _prospect(ProspectState.ENRICHING, email="x@example.com")
    decision = ENGINE.decide_qualification(prospect)
    assert decision.decision_type == DecisionType.MARK_QUALIFIED
    assert decision.qualification_level is not None
    assert decision.qualification_score is not None


def test_decide_qualification_a_bare_profile_with_only_a_phone_number_is_still_disqualified():
    # Phone presence alone isn't one of the 12 scored factors - LinkedIn is
    # always present (a DB NOT NULL constraint) and is already a valid
    # standalone outreach channel, so mere contactability no longer
    # auto-qualifies the way the old binary email-or-phone gate did.
    prospect = _prospect(ProspectState.ENRICHING, phone_number="+15551234567")
    decision = ENGINE.decide_qualification(prospect)
    assert decision.decision_type == DecisionType.MARK_DISQUALIFIED


def test_decide_qualification_marks_disqualified_with_a_bare_profile():
    prospect = _prospect(ProspectState.ENRICHING)
    decision = ENGINE.decide_qualification(prospect)
    assert decision.decision_type == DecisionType.MARK_DISQUALIFIED
    assert decision.qualification_level is not None


# --- Outreach escalation chain ---

def test_idle_prospect_sends_linkedin():
    decision = ENGINE.decide(_prospect(ProspectState.IDLE), sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SEND_LINKEDIN
    assert decision.task_to_enqueue == SEQUENCE_STEP_TASK_NAME


def test_li_req_sent_escalates_to_email():
    # index=2 -> sequence_steps[2] is EMAIL_1 (LinkedIn Follow-up already skipped/done)
    prospect = _prospect(ProspectState.LI_REQ_SENT, sequence_step_index=2)
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SEND_EMAIL
    assert decision.task_to_enqueue == SEQUENCE_STEP_TASK_NAME


def test_li_accepted_recently_waits_before_followup():
    prospect = _prospect(
        ProspectState.LI_ACCEPTED_NO_MSG,
        last_status_change_at=datetime.now(UTC) - timedelta(hours=1),
    )
    decision = ENGINE.decide(prospect)
    assert decision.decision_type == DecisionType.WAIT
    assert decision.task_to_enqueue is None


def test_li_accepted_24h_ago_sends_followup():
    # index=1 -> sequence_steps[1] is LINKEDIN_FOLLOWUP (step 0/LINKEDIN
    # already completed, hence the LI_ACCEPTED_NO_MSG status).
    prospect = _prospect(
        ProspectState.LI_ACCEPTED_NO_MSG,
        last_status_change_at=datetime.now(UTC) - timedelta(hours=25),
        sequence_step_index=1,
    )
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SEND_FOLLOWUP
    assert decision.task_to_enqueue == SEQUENCE_STEP_TASK_NAME


def test_li_msg_sent_escalates_to_email():
    # index=2 -> EMAIL_1
    prospect = _prospect(ProspectState.LI_MSG_SENT, sequence_step_index=2)
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SEND_EMAIL


def test_email_sent_escalates_to_call():
    # index=4 -> CALL
    prospect = _prospect(ProspectState.EMAIL_SENT, sequence_step_index=4)
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SCHEDULE_CALL
    assert decision.task_to_enqueue == SEQUENCE_STEP_TASK_NAME


def test_call_no_answer_retries_call():
    # index=5 -> VOICEMAIL (the CALL step at index 4 already ran and
    # advanced the index when the call was first placed - see
    # workers/tasks.py's _run_call_channel_step).
    prospect = _prospect(ProspectState.CALL_NO_ANSWER_1, sequence_step_index=5)
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SCHEDULE_CALL


def test_states_with_no_autonomous_step_wait():
    for state in (ProspectState.PAUSED_NUDGED, ProspectState.EMAIL_OPENED, ProspectState.ENGAGED_ON_WEBSITE, ProspectState.ERROR_NEEDS_HUMAN):
        decision = ENGINE.decide(_prospect(state))
        assert decision.decision_type == DecisionType.WAIT
        assert decision.task_to_enqueue is None


# --- Retry engine reuse ---

def test_retry_count_downgrades_action_to_retry_later():
    prospect = _prospect(ProspectState.EMAIL_SENT, retry_count=1, sequence_step_index=4)
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.RETRY_LATER
    assert decision.task_to_enqueue == SEQUENCE_STEP_TASK_NAME  # same target task, just framed as a retry


def test_retry_exhausted_ends_sequence_instead_of_retrying():
    # matches evaluate_retry's default max_retries (Sprint 3, item 2: the
    # 5-tier [1, 2, 4, 8, 16]-hour exponential backoff table moved this
    # from 3 to 5)
    prospect = _prospect(ProspectState.EMAIL_SENT, retry_count=5, sequence_step_index=4)
    decision = ENGINE.decide(prospect, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.END_SEQUENCE
    assert decision.task_to_enqueue is None


def test_retry_count_on_a_wait_decision_does_not_trigger_retry_later():
    # NEW/ENRICHING's decision is WAIT even with a nonzero retry_count -
    # retry framing only applies to decisions that actually dispatch an action.
    prospect = _prospect(ProspectState.NEW, retry_count=1)
    decision = ENGINE.decide(prospect)
    assert decision.decision_type == DecisionType.WAIT


# --- LinkedIn queue awareness ---

def test_send_linkedin_deferred_when_account_paused():
    account = _account(is_paused=True, paused_until=datetime.now(UTC) + timedelta(hours=1))
    decision = ENGINE.decide(_prospect(ProspectState.IDLE), linkedin_account=account, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.WAIT
    assert decision.task_to_enqueue is None
    assert "paused" in decision.reason


def test_send_linkedin_deferred_when_daily_limit_reached():
    account = _account(daily_send_count=20, daily_limit=20)
    decision = ENGINE.decide(_prospect(ProspectState.IDLE), linkedin_account=account, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.WAIT
    assert "daily send limit" in decision.reason


def test_send_linkedin_proceeds_when_account_has_capacity():
    account = _account(daily_send_count=5, daily_limit=20)
    decision = ENGINE.decide(_prospect(ProspectState.IDLE), linkedin_account=account, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SEND_LINKEDIN


def test_send_linkedin_proceeds_when_no_account_known_yet():
    # A brand-new tenant with no LinkedInAccount row yet has no known
    # constraint - must not be blocked by its absence.
    decision = ENGINE.decide(_prospect(ProspectState.IDLE), linkedin_account=None, sequence_steps=_FULL_SEQUENCE)
    assert decision.decision_type == DecisionType.SEND_LINKEDIN
