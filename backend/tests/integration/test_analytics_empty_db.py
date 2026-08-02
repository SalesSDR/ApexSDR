"""Every AnalyticsService method must return a well-formed, non-crashing
result against a tenant with zero data - dashboards render on day one
before any prospect exists."""
from app.services.analytics.service import FUNNEL_STAGE_ORDER, AnalyticsService

TENANT = "empty-tenant"


async def test_pipeline_funnel_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).pipeline_funnel()
    assert data["total_prospects"] == 0
    assert all(s["count"] == 0 for s in data["stages"])
    assert [s["stage"] for s in data["stages"]] == FUNNEL_STAGE_ORDER


async def test_prospects_by_state_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).prospects_by_state()
    assert all(count == 0 for count in data["by_state"].values())


async def test_outreach_metrics_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).outreach_metrics()
    assert data == {
        "currently_in_linkedin_outreach": 0,
        "currently_in_email_outreach": 0,
        "currently_in_call_outreach": 0,
        "currently_engaged": 0,
        "meetings_booked": 0,
    }


async def test_linkedin_metrics_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).linkedin_metrics()
    assert data["accounts"] == []
    assert all(v == 0 for v in data["by_state"].values())


async def test_email_metrics_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).email_metrics()
    assert all(v == 0 for v in data["by_state"].values())


async def test_call_metrics_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).call_metrics()
    assert data["call_attempts_distribution"] == {"0": 0, "1": 0, "2+": 0}


async def test_crm_sync_metrics_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).crm_sync_metrics()
    assert data["total_prospects"] == 0
    assert data["sync_coverage_pct"] == 0.0
    assert data["deals_by_stage"] == {}


async def test_calendar_metrics_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).calendar_metrics()
    assert data["meetings_booked"] == 0
    assert all(v == 0 for v in data["sync_by_status"].values())
    assert data["sync_by_event_type"] == {}


async def test_queue_metrics_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).queue_metrics()
    assert data["linkedin_queue"] == {
        "accounts": 0, "paused_accounts": 0, "total_daily_capacity": 0, "total_sent_today": 0,
    }


async def test_retry_metrics_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).retry_metrics()
    assert data["retry_count_distribution"] == {"0": 0, "1": 0, "2": 0, "3+": 0}
    assert data["retries_exhausted_needs_human"] == 0


async def test_daily_weekly_activity_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).daily_weekly_activity()
    assert data["buckets"] == []


async def test_failed_jobs_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).failed_jobs()
    assert data["total_pipeline_failures"] == 0
    assert data["total_calendar_failures"] == 0
    assert data["pipeline_failures_needing_human"] == []
    assert data["calendar_sync_failures"] == []


async def test_conversion_rates_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).conversion_rates()
    assert data["total_prospects"] == 0
    assert data["qualification_rate_pct"] == 0.0
    assert data["reply_rate_pct"] == 0.0
    assert data["meeting_conversion_rate_pct"] == 0.0


async def test_response_times_empty(db_session):
    data = await AnalyticsService(db_session, TENANT).response_times()
    assert data["sample_size"] == 0
    assert data["avg_time_to_first_response_hours"] is None
