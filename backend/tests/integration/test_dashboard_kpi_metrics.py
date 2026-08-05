"""Dashboard KPI cards (LinkedIn Responses / Meetings Booked / Invalid Data) -
RC-1 override feature. All three are derived from existing tables only
(Prospect, EmailVerification, EmailBounceSuppression, DoNotContactList) - no
schema changes, see AnalyticsService's new methods for the exact definitions."""
from datetime import UTC, datetime, timedelta

from app.models.schemas import (
    DoNotContactList,
    EmailBounceSuppression,
    EmailVerification,
    EmailVerificationStatus,
    Prospect,
    ProspectState,
)
from app.services.analytics.service import AnalyticsService

TENANT = "kpi-tenant"


def _prospect(n, status, **overrides):
    defaults = dict(
        tenant_id=TENANT,
        first_name=f"P{n}",
        last_name="Test",
        linkedin_url=f"https://linkedin.com/in/kpi{n}",
        status=status,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


async def test_linkedin_response_metrics_counts_only_post_accept_states(db_session):
    prospects = [
        _prospect(1, ProspectState.LI_ACCEPTED_NO_MSG),
        _prospect(2, ProspectState.LI_MSG_SENT),
        _prospect(3, ProspectState.LINKEDIN_NO_RESPONSE),
        _prospect(4, ProspectState.LI_REQ_SENT),  # not yet accepted - excluded
        _prospect(5, ProspectState.MEETING_BOOKED),  # channel-ambiguous - excluded
    ]
    db_session.add_all(prospects)
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).linkedin_response_metrics()

    assert data["linkedin_responses"] == 3


async def test_linkedin_responses_today_uses_last_status_change_at(db_session):
    old = _prospect(1, ProspectState.LI_ACCEPTED_NO_MSG, last_status_change_at=datetime.now(UTC) - timedelta(days=3))
    recent = _prospect(2, ProspectState.LI_MSG_SENT, last_status_change_at=datetime.now(UTC))
    db_session.add_all([old, recent])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).linkedin_response_metrics()

    assert data["linkedin_responses"] == 2
    assert data["linkedin_responses_today"] == 1


async def test_meetings_booked_metrics_includes_closed_won_not_declined(db_session):
    prospects = [
        _prospect(1, ProspectState.MEETING_BOOKED),
        _prospect(2, ProspectState.CLOSED_WON),
        _prospect(3, ProspectState.COMPLETED_DECLINED),  # ambiguous origin - excluded
        _prospect(4, ProspectState.LOST),  # ambiguous origin - excluded
    ]
    db_session.add_all(prospects)
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).meetings_booked_metrics()

    assert data["meetings_booked"] == 2


async def test_meetings_booked_today_uses_last_status_change_at(db_session):
    old = _prospect(1, ProspectState.MEETING_BOOKED, last_status_change_at=datetime.now(UTC) - timedelta(days=2))
    recent = _prospect(2, ProspectState.CLOSED_WON, last_status_change_at=datetime.now(UTC))
    db_session.add_all([old, recent])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).meetings_booked_metrics()

    assert data["meetings_booked"] == 2
    assert data["meetings_booked_today"] == 1


async def test_invalid_data_flags_risky_and_invalid_verified_emails(db_session):
    p1 = _prospect(1, ProspectState.IDLE, email="risky@example.com", company_name="Acme")
    p2 = _prospect(2, ProspectState.IDLE, email="fine@example.com", company_name="Acme")
    db_session.add_all([p1, p2])
    await db_session.flush()
    db_session.add(EmailVerification(
        email="risky@example.com", status=EmailVerificationStatus.RISKY, reason="no_mx", provider="test",
    ))
    db_session.add(EmailVerification(
        email="fine@example.com", status=EmailVerificationStatus.VALID, reason="ok", provider="test",
    ))
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).invalid_data_metrics()

    assert data["by_reason"]["invalid_or_risky_email"] == 1
    assert data["invalid_data"] == 1


async def test_invalid_data_flags_bounced_email(db_session):
    p = _prospect(1, ProspectState.IDLE, email="bounced@example.com", company_name="Acme")
    db_session.add(p)
    await db_session.flush()
    db_session.add(EmailBounceSuppression(email="bounced@example.com", reason="hard_bounce"))
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).invalid_data_metrics()

    assert data["by_reason"]["bounced_email"] == 1
    assert data["invalid_data"] == 1


async def test_invalid_data_flags_blacklisted_contact_by_email_and_phone(db_session):
    p_email = _prospect(1, ProspectState.IDLE, email="blocked@example.com", company_name="Acme")
    p_phone = _prospect(2, ProspectState.IDLE, phone_number="+15550001111", company_name="Acme")
    db_session.add_all([p_email, p_phone])
    await db_session.flush()
    db_session.add(DoNotContactList(tenant_id=TENANT, value="blocked@example.com", type="EMAIL", source="USER_MANUAL"))
    db_session.add(DoNotContactList(tenant_id=TENANT, value="+15550001111", type="PHONE", source="USER_MANUAL"))
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).invalid_data_metrics()

    assert data["by_reason"]["blacklisted_contact"] == 2
    assert data["invalid_data"] == 2


async def test_invalid_data_flags_missing_company_and_missing_email(db_session):
    p1 = _prospect(1, ProspectState.IDLE, company_name=None, email="has-email@example.com")
    p2 = _prospect(2, ProspectState.IDLE, company_name="Acme", email=None)
    p3 = _prospect(3, ProspectState.IDLE, company_name="Acme", email="ok@example.com")
    db_session.add_all([p1, p2, p3])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).invalid_data_metrics()

    assert data["by_reason"]["missing_company"] == 1
    assert data["by_reason"]["missing_email"] == 1
    assert data["invalid_data"] == 2  # p1 and p2, p3 is clean


async def test_invalid_data_flags_duplicate_email_within_tenant_only(db_session):
    dup1 = _prospect(1, ProspectState.IDLE, email="dup@example.com", company_name="Acme")
    dup2 = _prospect(2, ProspectState.IDLE, email="dup@example.com", company_name="Acme")
    unique = _prospect(3, ProspectState.IDLE, email="unique@example.com", company_name="Acme")
    # Same email in a DIFFERENT tenant must not count as a duplicate here.
    other_tenant = _prospect(4, ProspectState.IDLE, email="dup@example.com", company_name="Acme", tenant_id="other-tenant")
    db_session.add_all([dup1, dup2, unique, other_tenant])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).invalid_data_metrics()

    assert data["by_reason"]["duplicate_lead"] == 2
    assert data["invalid_data"] == 2


async def test_invalid_data_total_does_not_double_count_a_prospect_with_multiple_reasons(db_session):
    # Missing company AND a bounced email - still one prospect in the total.
    p = _prospect(1, ProspectState.IDLE, email="both@example.com", company_name=None)
    db_session.add(p)
    await db_session.flush()
    db_session.add(EmailBounceSuppression(email="both@example.com", reason="hard_bounce"))
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).invalid_data_metrics()

    assert data["by_reason"]["missing_company"] == 1
    assert data["by_reason"]["bounced_email"] == 1
    assert data["invalid_data"] == 1  # not 2


async def test_dashboard_kpi_metrics_bundles_all_three(db_session):
    db_session.add_all([
        _prospect(1, ProspectState.LI_ACCEPTED_NO_MSG, email="p1@example.com", company_name="Acme"),
        _prospect(2, ProspectState.MEETING_BOOKED, email="p2@example.com", company_name="Acme"),
        _prospect(3, ProspectState.IDLE, email="p3@example.com", company_name=None),
    ])
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).dashboard_kpi_metrics()

    assert data["linkedinResponses"] == 1
    assert data["meetingsBooked"] == 1
    assert data["invalidData"] == 1
    assert "invalidDataByReason" in data
