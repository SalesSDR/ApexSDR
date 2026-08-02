"""Sprint 5, item 2/5: unit coverage for the priority-rank, delay-multiplier,
and deal-value-estimation helpers in services/qualification/scoring.py."""
from app.models.schemas import Prospect, QualificationLevel
from app.services.qualification.scoring import (
    PRIORITY_ORDER,
    delay_multiplier_for,
    estimate_deal_value,
    priority_rank,
)


def test_priority_order_is_hot_high_medium_low():
    assert PRIORITY_ORDER == [QualificationLevel.HOT, QualificationLevel.HIGH, QualificationLevel.MEDIUM, QualificationLevel.LOW]


def test_priority_rank_increases_from_hot_to_low():
    assert priority_rank(QualificationLevel.HOT) < priority_rank(QualificationLevel.HIGH)
    assert priority_rank(QualificationLevel.HIGH) < priority_rank(QualificationLevel.MEDIUM)
    assert priority_rank(QualificationLevel.MEDIUM) < priority_rank(QualificationLevel.LOW)


def test_priority_rank_sorts_unscored_prospects_last():
    assert priority_rank(None) > priority_rank(QualificationLevel.LOW)


def test_delay_multiplier_speeds_up_hot_and_slows_down_low():
    assert delay_multiplier_for(QualificationLevel.HOT) < 1.0
    assert delay_multiplier_for(QualificationLevel.HIGH) == 1.0
    assert delay_multiplier_for(QualificationLevel.MEDIUM) > 1.0
    assert delay_multiplier_for(QualificationLevel.LOW) > delay_multiplier_for(QualificationLevel.MEDIUM)


def test_delay_multiplier_defaults_to_1_for_unscored():
    assert delay_multiplier_for(None) == 1.0


def _prospect(**overrides) -> Prospect:
    defaults = dict(tenant_id="t1", first_name="Ada", last_name="Lovelace", linkedin_url="https://linkedin.com/in/ada")
    defaults.update(overrides)
    return Prospect(**defaults)


def test_estimate_deal_value_scales_with_employee_count():
    small = estimate_deal_value(_prospect(employee_count=10))
    large = estimate_deal_value(_prospect(employee_count=1000))
    assert large > small


def test_estimate_deal_value_caps_at_a_maximum_company_size():
    at_cap = estimate_deal_value(_prospect(employee_count=5000))
    beyond_cap = estimate_deal_value(_prospect(employee_count=50000))
    assert at_cap == beyond_cap


def test_estimate_deal_value_has_a_sane_default_when_company_size_is_unknown():
    value = estimate_deal_value(_prospect())
    assert value > 0
