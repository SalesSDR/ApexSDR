from app.models.schemas import CalendarSyncLog, CalendarSyncStatus, LinkedInAccount, Prospect, ProspectState
from app.services.analytics.service import AnalyticsService

TENANT = "acc-tenant"


def _prospect(n, status, **overrides):
    defaults = dict(
        tenant_id=TENANT,
        first_name=f"P{n}",
        last_name="Test",
        linkedin_url=f"https://linkedin.com/in/p{n}",
        status=status,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


async def _seed(db_session):
    prospects = [
        _prospect(1, ProspectState.NEW),
        _prospect(2, ProspectState.ENRICHING),
        _prospect(3, ProspectState.DISQUALIFIED),
        _prospect(4, ProspectState.IDLE),
        _prospect(5, ProspectState.LI_REQ_SENT, retry_count=1),
        _prospect(6, ProspectState.EMAIL_SENT, retry_count=3, call_attempts=0),
        _prospect(7, ProspectState.CALL_IN_PROGRESS, call_attempts=1),
        _prospect(8, ProspectState.CALL_NO_ANSWER_2, call_attempts=2),
        _prospect(9, ProspectState.LINKEDIN_REPLIED),
        _prospect(10, ProspectState.EMAIL_REPLIED),
        _prospect(11, ProspectState.MEETING_BOOKED, hubspot_contact_id="c1", hubspot_deal_id="d1"),
        _prospect(12, ProspectState.ERROR_NEEDS_HUMAN, retry_count=3),
        _prospect(13, ProspectState.COMPLETED_DECLINED),
    ]
    db_session.add_all(prospects)
    await db_session.flush()  # assigns prospect.id (client-side default fires at flush, not __init__)

    db_session.add(LinkedInAccount(tenant_id=TENANT, account_id="acc_1", daily_send_count=3, daily_limit=20))
    db_session.add(CalendarSyncLog(
        tenant_id=TENANT, prospect_id=prospects[10].id, event_type="EVENT_CREATED", status=CalendarSyncStatus.SUCCESS,
    ))
    db_session.add(CalendarSyncLog(
        tenant_id=TENANT, prospect_id=prospects[10].id, event_type="API_FAILURE", status=CalendarSyncStatus.FAILED,
        error_message="boom",
    ))
    await db_session.flush()
    return prospects


async def test_pipeline_funnel_buckets_are_mutually_exclusive_and_sum_to_total(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.pipeline_funnel()

    assert data["total_prospects"] == 13
    by_stage = {s["stage"]: s["count"] for s in data["stages"]}
    assert by_stage["new"] == 1
    assert by_stage["enriching"] == 1
    assert by_stage["disqualified"] == 1
    assert by_stage["qualified_ready"] == 1
    assert by_stage["outreach_in_progress"] == 4
    assert by_stage["engaged"] == 2
    assert by_stage["meeting_booked"] == 1
    assert by_stage["closed_declined"] == 1
    assert by_stage["closed_unresponsive"] == 0
    assert by_stage["closed_lost"] == 0
    assert by_stage["needs_human"] == 1
    assert sum(by_stage.values()) == 13


async def test_prospects_by_state_matches_seeded_counts(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.prospects_by_state()

    assert data["by_state"][ProspectState.NEW.value] == 1
    assert data["by_state"][ProspectState.LI_REQ_SENT.value] == 1
    assert data["by_state"][ProspectState.CALL_CONNECTED.value] == 0  # never seeded


async def test_outreach_metrics_counts_per_channel(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.outreach_metrics()

    assert data["currently_in_linkedin_outreach"] == 2  # LI_REQ_SENT + LINKEDIN_REPLIED
    assert data["currently_in_email_outreach"] == 2  # EMAIL_SENT + EMAIL_REPLIED
    assert data["currently_in_call_outreach"] == 2  # CALL_IN_PROGRESS + CALL_NO_ANSWER_2
    assert data["currently_engaged"] == 2
    assert data["meetings_booked"] == 1


async def test_call_metrics_attempts_distribution(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.call_metrics()

    assert data["call_attempts_distribution"] == {"0": 11, "1": 1, "2+": 1}
    assert data["by_state"][ProspectState.CALL_IN_PROGRESS.value] == 1
    assert data["by_state"][ProspectState.CALL_NO_ANSWER_2.value] == 1


async def test_crm_sync_metrics_computes_coverage_and_deal_stage(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.crm_sync_metrics()

    assert data["total_prospects"] == 13
    assert data["contacts_synced"] == 1
    assert data["deals_created"] == 1
    assert data["sync_coverage_pct"] == round(1 / 13 * 100, 1)
    assert data["deals_by_stage"] == {"appointmentscheduled": 1}


async def test_calendar_metrics_reads_sync_log(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.calendar_metrics()

    assert data["meetings_booked"] == 1
    assert data["sync_by_status"][CalendarSyncStatus.SUCCESS.value] == 1
    assert data["sync_by_status"][CalendarSyncStatus.FAILED.value] == 1
    assert data["sync_by_event_type"] == {"EVENT_CREATED": 1, "API_FAILURE": 1}


async def test_queue_metrics_reports_linkedin_account_state(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.queue_metrics()

    assert data["linkedin_queue"] == {
        "accounts": 1, "paused_accounts": 0, "total_daily_capacity": 20, "total_sent_today": 3,
    }
    assert isinstance(data["arq_pending_jobs_total"], int)


async def test_retry_metrics_distribution_and_exhausted_count(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.retry_metrics()

    assert data["retry_count_distribution"] == {"0": 10, "1": 1, "2": 0, "3+": 2}
    assert data["retries_exhausted_needs_human"] == 1


async def test_daily_weekly_activity_buckets_todays_prospects(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.daily_weekly_activity(period="daily", days=30)

    assert data["period"] == "daily"
    assert sum(b["new_prospects"] for b in data["buckets"]) == 13


async def test_daily_weekly_activity_rejects_invalid_period(db_session):
    service = AnalyticsService(db_session, TENANT)
    import pytest
    with pytest.raises(ValueError):
        await service.daily_weekly_activity(period="monthly")


async def test_failed_jobs_lists_needs_human_and_calendar_failures(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.failed_jobs()

    assert data["total_pipeline_failures"] == 1
    assert data["total_calendar_failures"] == 1
    assert data["pipeline_failures_needing_human"][0]["name"] == "P12 Test"
    assert data["calendar_sync_failures"][0]["error_message"] == "boom"


async def test_conversion_rates_computed_from_snapshot(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.conversion_rates()

    assert data["total_prospects"] == 13
    assert data["qualification_rate_pct"] == round(10 / 11 * 100, 1)
    assert data["reply_rate_pct"] == round(2 / 13 * 100, 1)
    assert data["meeting_conversion_rate_pct"] == round(1 / 13 * 100, 1)


async def test_response_times_averages_reply_and_booked_prospects(db_session):
    await _seed(db_session)
    service = AnalyticsService(db_session, TENANT)

    data = await service.response_times()

    assert data["sample_size"] == 3  # LINKEDIN_REPLIED + EMAIL_REPLIED + MEETING_BOOKED
    assert data["avg_time_to_first_response_hours"] is not None
    assert data["avg_time_to_first_response_hours"] >= 0
