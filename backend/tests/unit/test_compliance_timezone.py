"""Timezone-aware business hours + configurable policy loading (Sprint 2,
item 4): ProductionComplianceProvider must differ from MockComplianceProvider
without duplicating its validate() logic."""
from datetime import UTC, datetime

import pytest

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


# --- check_business_hours reads WorkspaceSetting.exclude_weekends (Sprint RC-1 fix) ---
# Previously this setting was stored/returned correctly but never read by the
# compliance engine, which always hardcoded weekend-blocking regardless of it.

class _FrozenAt:
    """Context manager freezing app.services.compliance.policy's `datetime.now()`
    to a fixed UTC instant, restoring the original class afterward."""

    def __init__(self, year, month, day, hour, minute=0):
        self._target = datetime(year, month, day, hour, minute, tzinfo=UTC)

    def __enter__(self):
        import app.services.compliance.policy as policy_module
        self._module = policy_module
        self._original = policy_module.datetime
        target = self._target

        class _Frozen(self._original):
            @classmethod
            def now(cls, tz=None):
                return target

        policy_module.datetime = _Frozen
        return self

    def __exit__(self, *exc):
        self._module.datetime = self._original


async def _make_prospect_with_setting(db_session, tenant_id: str, exclude_weekends: bool | None):
    from app.models.schemas import Prospect, WorkspaceSetting

    if exclude_weekends is not None:
        db_session.add(WorkspaceSetting(tenant_id=tenant_id, exclude_weekends=exclude_weekends))
    prospect = Prospect(
        tenant_id=tenant_id, first_name="A", last_name="B",
        linkedin_url="https://x", email=f"{tenant_id}@example.com",
    )
    db_session.add(prospect)
    await db_session.flush()
    return prospect


async def test_check_business_hours_blocks_weekend_when_exclude_weekends_configured_true(db_session):
    from app.models.schemas import DecisionType
    prospect = await _make_prospect_with_setting(db_session, "t-weekend-excluded", exclude_weekends=True)

    # 2026-08-08 is a Saturday, 14:00 UTC = 10am America/New_York (EDT).
    with _FrozenAt(2026, 8, 8, 14):
        check = await check_business_hours(db_session, prospect, DecisionType.SEND_EMAIL, "America/New_York")

    assert not check.is_allowed
    assert "Mon-Fri" in check.reason


async def test_check_business_hours_allows_weekend_when_exclude_weekends_configured_false(db_session):
    from app.models.schemas import DecisionType
    prospect = await _make_prospect_with_setting(db_session, "t-weekend-allowed", exclude_weekends=False)

    # Same Saturday 10am local instant as above - only the setting differs.
    with _FrozenAt(2026, 8, 8, 14):
        check = await check_business_hours(db_session, prospect, DecisionType.SEND_EMAIL, "America/New_York")

    assert check.is_allowed


async def test_check_business_hours_defaults_to_blocking_weekends_when_no_setting_row_exists(db_session):
    """A tenant with no WorkspaceSetting row at all keeps the original,
    safe default (weekends blocked) rather than silently allowing them."""
    from app.models.schemas import DecisionType
    prospect = await _make_prospect_with_setting(db_session, "t-no-setting-row", exclude_weekends=None)

    with _FrozenAt(2026, 8, 8, 14):
        check = await check_business_hours(db_session, prospect, DecisionType.SEND_EMAIL, "America/New_York")

    assert not check.is_allowed


@pytest.mark.parametrize("exclude_weekends", [True, False])
async def test_check_business_hours_weekday_behavior_unchanged_by_the_setting(db_session, exclude_weekends):
    """The setting only changes weekend handling - a weekday during business
    hours is allowed, and a weekday outside business hours is blocked,
    regardless of what exclude_weekends is configured to."""
    from app.models.schemas import DecisionType
    prospect = await _make_prospect_with_setting(db_session, f"t-weekday-{exclude_weekends}", exclude_weekends=exclude_weekends)

    # 2026-08-03 is a Monday. 14:00 UTC = 10am America/New_York (within hours).
    with _FrozenAt(2026, 8, 3, 14):
        check = await check_business_hours(db_session, prospect, DecisionType.SEND_EMAIL, "America/New_York")
    assert check.is_allowed

    # 11:00 UTC = 7am America/New_York (before the 9am start) - same Monday.
    with _FrozenAt(2026, 8, 3, 11):
        check = await check_business_hours(db_session, prospect, DecisionType.SEND_EMAIL, "America/New_York")
    assert not check.is_allowed


async def test_check_business_hours_still_enforces_hour_of_day_when_weekends_allowed(db_session):
    """Turning off weekend exclusion must not turn off the hour-of-day
    check - a Saturday at 2am local is still outside business hours."""
    from app.models.schemas import DecisionType
    prospect = await _make_prospect_with_setting(db_session, "t-weekend-2am", exclude_weekends=False)

    # 2026-08-08 is a Saturday. 06:00 UTC = 2am America/New_York (EDT).
    with _FrozenAt(2026, 8, 8, 6):
        check = await check_business_hours(db_session, prospect, DecisionType.SEND_EMAIL, "America/New_York")

    assert not check.is_allowed
    assert "any day" in check.reason


def test_is_within_business_hours_exclude_weekends_false_allows_saturday_within_hours():
    """Direct unit test of the lower-level helper's new parameter, isolated
    from the DB-backed check_business_hours above."""
    now_utc = datetime(2026, 8, 8, 14, 0, tzinfo=UTC)  # Saturday, 10am America/New_York
    assert is_within_business_hours(now_utc, "America/New_York", exclude_weekends=False) is True
    assert is_within_business_hours(now_utc, "America/New_York", exclude_weekends=True) is False


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
