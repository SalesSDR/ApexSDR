from app.models.schemas import ProspectState
from app.services.analytics.service import (
    CALL_STATES,
    EMAIL_STATES,
    FUNNEL_STAGE_BY_STATUS,
    FUNNEL_STAGE_ORDER,
    LINKEDIN_STATES,
    _pct,
)


def test_every_prospect_state_maps_to_exactly_one_funnel_stage():
    for state in ProspectState:
        assert state in FUNNEL_STAGE_BY_STATUS, f"{state} has no funnel bucket"
        assert FUNNEL_STAGE_BY_STATUS[state] in FUNNEL_STAGE_ORDER


def test_channel_state_groups_do_not_overlap():
    linkedin = set(LINKEDIN_STATES)
    email = set(EMAIL_STATES)
    call = set(CALL_STATES)
    assert linkedin & email == set()
    assert linkedin & call == set()
    assert email & call == set()


def test_pct_helper_handles_zero_denominator():
    assert _pct(5, 0) == 0.0


def test_pct_helper_computes_rounded_percentage():
    assert _pct(1, 3) == 33.3
    assert _pct(2, 2) == 100.0
