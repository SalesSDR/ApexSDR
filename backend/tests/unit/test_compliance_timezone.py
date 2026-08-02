"""Timezone-aware business hours + configurable policy loading (Sprint 2,
item 4): ProductionComplianceProvider must differ from MockComplianceProvider
without duplicating its validate() logic."""
from datetime import UTC, datetime

from app.config import settings
from app.services.compliance.base import BaseComplianceProvider
from app.services.compliance.mock import MockComplianceProvider
from app.services.compliance.policy import check_business_hours, check_do_not_contact, is_within_business_hours
from app.services.compliance.production import ProductionComplianceProvider

# --- Timezone-aware business hours ---

def test_business_hours_true_at_10am_local_on_a_weekday():
    # 2026-08-03 is a Monday. 14:00 UTC = 10:00 in America/New_York (EDT, UTC-4).
    now_utc = datetime(2026, 8, 3, 14, 0, tzinfo=UTC)
    assert is_within_business_hours(now_utc, "America/New_York") is True


def test_business_hours_false_before_9am_local():
    # 11:00 UTC = 7:00 in America/New_York - before the 9am start.
    now_utc = datetime(2026, 8, 3, 11, 0, tzinfo=UTC)
    assert is_within_business_hours(now_utc, "America/New_York") is False


def test_business_hours_false_after_5pm_local():
    # 22:00 UTC = 18:00 in America/New_York - after the 5pm end.
    now_utc = datetime(2026, 8, 3, 22, 0, tzinfo=UTC)
    assert is_within_business_hours(now_utc, "America/New_York") is False


def test_business_hours_false_on_weekend():
    # 2026-08-08 is a Saturday, 14:00 UTC (10am EDT).
    now_utc = datetime(2026, 8, 8, 14, 0, tzinfo=UTC)
    assert is_within_business_hours(now_utc, "America/New_York") is False


def test_business_hours_differs_by_prospect_timezone_for_the_same_instant():
    """The exact instant that's mid-morning in New York is already
    after-hours in Tokyo - proves the check genuinely uses the prospect's
    own timezone rather than a single hardcoded one."""
    now_utc = datetime(2026, 8, 3, 14, 0, tzinfo=UTC)  # 10am America/New_York
    assert is_within_business_hours(now_utc, "America/New_York") is True
    assert is_within_business_hours(now_utc, "Asia/Tokyo") is False  # 23:00 in Tokyo


def test_business_hours_falls_back_to_utc_for_unknown_timezone():
    now_utc = datetime(2026, 8, 3, 14, 0, tzinfo=UTC)  # within 9-5 UTC
    assert is_within_business_hours(now_utc, "Not/ARealTimezone") is True


async def test_check_business_hours_reports_the_prospect_timezone_in_the_reason():
    from app.models.schemas import DecisionType, Prospect
    prospect = Prospect(tenant_id="t", first_name="A", last_name="B", linkedin_url="https://x", email="a@b.com")
    # 2am America/Los_Angeles is clearly outside business hours regardless
    # of what UTC wall-clock time the test happens to run at.
    import app.services.compliance.policy as policy_module
    original_datetime = policy_module.datetime

    class _FrozenDatetime(original_datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 8, 3, 9, 0, tzinfo=UTC)  # 2am Los Angeles (PDT, UTC-7)

    policy_module.datetime = _FrozenDatetime
    try:
        check = await check_business_hours(None, prospect, DecisionType.SEND_EMAIL, "America/Los_Angeles")
    finally:
        policy_module.datetime = original_datetime

    assert not check.is_allowed
    assert "America/Los_Angeles" in check.reason


# --- Configurable policy loading / Mock vs Production must differ ---

def test_mock_provider_uses_a_fixed_policy_set_regardless_of_settings(monkeypatch):
    monkeypatch.setattr(settings, "COMPLIANCE_ENABLED_POLICIES", "BUSINESS_HOURS")  # DNC deliberately excluded
    provider = MockComplianceProvider(tenant_id="t")
    assert provider.policies == [check_do_not_contact, check_business_hours]


def test_production_provider_loads_policies_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "COMPLIANCE_ENABLED_POLICIES", "BUSINESS_HOURS")
    provider = ProductionComplianceProvider(tenant_id="t")
    assert provider.policies == [check_business_hours]  # DNC excluded, unlike Mock


def test_production_provider_respects_configured_policy_order(monkeypatch):
    monkeypatch.setattr(settings, "COMPLIANCE_ENABLED_POLICIES", "BUSINESS_HOURS,DO_NOT_CONTACT")
    provider = ProductionComplianceProvider(tenant_id="t")
    assert provider.policies == [check_business_hours, check_do_not_contact]


def test_production_provider_falls_back_to_default_set_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "COMPLIANCE_ENABLED_POLICIES", "")
    provider = ProductionComplianceProvider(tenant_id="t")
    assert provider.policies == [check_do_not_contact, check_business_hours]


def test_production_provider_ignores_unknown_policy_names(monkeypatch):
    monkeypatch.setattr(settings, "COMPLIANCE_ENABLED_POLICIES", "BUSINESS_HOURS,NOT_A_REAL_POLICY")
    provider = ProductionComplianceProvider(tenant_id="t")
    assert provider.policies == [check_business_hours]


def test_mock_and_production_share_validate_implementation():
    """Neither subclass may re-implement the policy-loop control flow -
    only _default_policies() may differ between them."""
    assert MockComplianceProvider.validate is BaseComplianceProvider.validate
    assert ProductionComplianceProvider.validate is BaseComplianceProvider.validate
    assert MockComplianceProvider._default_policies is not ProductionComplianceProvider._default_policies


async def test_validate_loop_short_circuits_on_first_failing_policy():
    calls = []

    async def _pass(db, prospect, action, tz):
        calls.append("pass")
        from app.services.compliance.base import ComplianceCheck
        return ComplianceCheck(is_allowed=True)

    async def _fail(db, prospect, action, tz):
        calls.append("fail")
        from app.models.schemas import CompliancePolicyType, PolicySeverity
        from app.services.compliance.base import ComplianceCheck
        return ComplianceCheck(is_allowed=False, policy_type=CompliancePolicyType.BUSINESS_HOURS, severity=PolicySeverity.TEMPORARY_BLOCK, reason="blocked")

    async def _never_called(db, prospect, action, tz):
        calls.append("never_called")
        from app.services.compliance.base import ComplianceCheck
        return ComplianceCheck(is_allowed=True)

    provider = MockComplianceProvider(tenant_id="t", policies=[_pass, _fail, _never_called])
    from app.models.schemas import DecisionType, Prospect
    prospect = Prospect(tenant_id="t", first_name="A", last_name="B", linkedin_url="https://x")

    check = await provider.validate(None, prospect, DecisionType.SEND_EMAIL, "UTC")

    assert not check.is_allowed
    assert calls == ["pass", "fail"]  # never_called never runs
