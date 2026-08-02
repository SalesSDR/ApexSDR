from app.models.schemas import ProspectState
from app.workers.tasks import get_force_advance_plan


def test_idle_advances_via_start_outbound_sequence_with_tenant_id():
    target_status, task, needs_tenant_id = get_force_advance_plan(ProspectState.IDLE)
    assert target_status is None
    assert task == "start_outbound_sequence"
    assert needs_tenant_id is True


def test_li_req_sent_sets_accepted_status_before_followup_task():
    target_status, task, needs_tenant_id = get_force_advance_plan(ProspectState.LI_REQ_SENT)
    assert target_status == ProspectState.LI_ACCEPTED_NO_MSG
    assert task == "send_linkedin_followup_task"
    assert needs_tenant_id is False


def test_call_no_answer_states_retry_via_execute_call_task():
    for state in (ProspectState.CALL_NO_ANSWER_1, ProspectState.CALL_NO_ANSWER_2):
        target_status, task, needs_tenant_id = get_force_advance_plan(state)
        assert target_status is None
        assert task == "execute_call_task"


def test_terminal_states_have_no_advance_plan():
    for state in (
        ProspectState.MEETING_BOOKED,
        ProspectState.UNRESPONSIVE_DEAD,
        ProspectState.ERROR_NEEDS_HUMAN,
    ):
        target_status, task, needs_tenant_id = get_force_advance_plan(state)
        assert task is None
