"""Sprint 4, item 1/2: unit coverage for the configurable weighted
qualification scoring engine that replaces the old binary "has an email or
phone number" gate."""
from app.models.schemas import BuyingSignal, Prospect, QualificationLevel, SignalStrength, SignalType, WorkspaceSetting
from app.services.qualification.scoring import DEFAULT_THRESHOLDS, FACTOR_NAMES, score_prospect


def _prospect(**overrides) -> Prospect:
    defaults = dict(
        tenant_id="t1", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada",
    )
    defaults.update(overrides)
    return Prospect(**defaults)


def _signal(signal_type: SignalType, strength: SignalStrength, active: bool = True) -> BuyingSignal:
    return BuyingSignal(
        tenant_id="t1", prospect_id="p1", signal_type=signal_type, signal_source="test",
        signal_strength=strength, summary="test signal", is_active=active,
    )


def test_a_fully_bare_prospect_scores_low_and_is_low_tier():
    breakdown = score_prospect(_prospect())
    assert breakdown.level == QualificationLevel.LOW
    assert set(breakdown.factor_scores.keys()) == set(FACTOR_NAMES)


def test_a_richly_enriched_decision_maker_scores_hot():
    prospect = _prospect(
        job_title="VP of Engineering",
        email="ada@techcorp.com",
        industry="SaaS",
        employee_count=200,
        company_website="https://techcorp.com",
        funding_stage="SERIES_B",
        funding_amount=40_000_000,
        tech_stack=["Python", "AWS", "Kubernetes"],
    )
    signals = [
        _signal(SignalType.COMPANY_HIRING, SignalStrength.HIGH),
        _signal(SignalType.FUNDING_EVENT, SignalStrength.VERY_HIGH),
    ]
    breakdown = score_prospect(prospect, buying_signals=signals)
    assert breakdown.level in (QualificationLevel.HOT, QualificationLevel.HIGH)
    assert breakdown.score > 60


def test_email_quality_penalizes_free_mail_domains():
    corporate = score_prospect(_prospect(email="ada@techcorp.com"))
    free_mail = score_prospect(_prospect(email="ada@gmail.com"))
    no_email = score_prospect(_prospect())
    assert corporate.factor_scores["email_quality"] > free_mail.factor_scores["email_quality"]
    assert free_mail.factor_scores["email_quality"] > no_email.factor_scores["email_quality"]


def test_seniority_ranks_c_level_above_manager_above_individual_contributor():
    c_level = score_prospect(_prospect(job_title="Chief Technology Officer"))
    manager = score_prospect(_prospect(job_title="Engineering Manager"))
    ic = score_prospect(_prospect(job_title="Software Engineer"))
    assert c_level.factor_scores["seniority"] > manager.factor_scores["seniority"]
    assert manager.factor_scores["seniority"] > ic.factor_scores["seniority"]


def test_hiring_signal_boosts_the_hiring_factor():
    without = score_prospect(_prospect())
    with_hiring = score_prospect(_prospect(), buying_signals=[_signal(SignalType.COMPANY_HIRING, SignalStrength.HIGH)])
    assert with_hiring.factor_scores["hiring"] > without.factor_scores["hiring"]


def test_icp_fit_is_neutral_when_no_icp_profile_is_configured():
    breakdown = score_prospect(_prospect(industry="Fintech"))
    assert breakdown.factor_scores["icp_fit"] == 50.0


def test_icp_fit_rewards_matching_a_configured_target_industry():
    ws = WorkspaceSetting(tenant_id="t1", icp_profile={"target_industries": ["Fintech", "SaaS"]})
    matching = score_prospect(_prospect(industry="Fintech"), workspace_setting=ws)
    non_matching = score_prospect(_prospect(industry="Retail"), workspace_setting=ws)
    assert matching.factor_scores["icp_fit"] == 100.0
    assert non_matching.factor_scores["icp_fit"] == 0.0


def test_company_size_rewards_being_within_the_configured_range():
    ws = WorkspaceSetting(tenant_id="t1", icp_profile={"company_size_min": 50, "company_size_max": 500})
    in_range = score_prospect(_prospect(employee_count=200), workspace_setting=ws)
    out_of_range = score_prospect(_prospect(employee_count=5), workspace_setting=ws)
    assert in_range.factor_scores["company_size"] == 100.0
    assert out_of_range.factor_scores["company_size"] < 100.0


def test_funding_stage_scores_increase_with_maturity():
    seed = score_prospect(_prospect(funding_stage="SEED"))
    series_b = score_prospect(_prospect(funding_stage="SERIES_B"))
    public = score_prospect(_prospect(funding_stage="PUBLIC"))
    assert seed.factor_scores["funding"] < series_b.factor_scores["funding"] < public.factor_scores["funding"]


def test_custom_weights_shift_the_final_score():
    prospect = _prospect(job_title="Chief Executive Officer")
    ws_default = WorkspaceSetting(tenant_id="t1")
    ws_seniority_heavy = WorkspaceSetting(
        tenant_id="t1",
        qualification_config={"weights": {name: (10.0 if name == "seniority" else 0.1) for name in FACTOR_NAMES}},
    )
    default_score = score_prospect(prospect, workspace_setting=ws_default).score
    seniority_weighted_score = score_prospect(prospect, workspace_setting=ws_seniority_heavy).score
    assert seniority_weighted_score > default_score


def test_custom_thresholds_change_the_resulting_level():
    prospect = _prospect(email="ada@techcorp.com")  # scores exactly 35.0 under defaults -> MEDIUM
    lenient = WorkspaceSetting(tenant_id="t1", qualification_config={"thresholds": {"medium": 10.0}})
    strict = WorkspaceSetting(tenant_id="t1", qualification_config={"thresholds": {"medium": 90.0}})
    assert score_prospect(prospect, workspace_setting=lenient).level != QualificationLevel.LOW
    assert score_prospect(prospect, workspace_setting=strict).level == QualificationLevel.LOW


def test_reason_mentions_strongest_and_weakest_factors():
    breakdown = score_prospect(_prospect(job_title="CEO"))
    assert "Strongest factors" in breakdown.reason
    assert "Weakest factors" in breakdown.reason
    assert str(breakdown.score) in breakdown.reason


def test_default_thresholds_are_exposed_and_ordered():
    assert DEFAULT_THRESHOLDS["hot"] > DEFAULT_THRESHOLDS["high"] > DEFAULT_THRESHOLDS["medium"]
