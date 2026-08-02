"""Sprint 5, item 5 (Revenue Attribution): estimated_pipeline_value,
meeting_value, won_value, and lost_value, all derived from
Prospect.estimated_deal_value."""
from app.models.schemas import Prospect, ProspectState
from app.services.analytics.service import AnalyticsService

TENANT = "revenue-tenant"


def _prospect(n, status, value, **overrides):
    defaults = dict(
        tenant_id=TENANT, first_name=f"P{n}", last_name="Test",
        linkedin_url=f"https://linkedin.com/in/rev{n}", status=status,
        estimated_deal_value=value,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


async def test_revenue_metrics_buckets_by_outcome(db_session):
    prospects = [
        _prospect(1, ProspectState.IDLE, 5000.0),            # open pipeline
        _prospect(2, ProspectState.EMAIL_SENT, 8000.0),       # open pipeline
        _prospect(3, ProspectState.MEETING_BOOKED, 20000.0),  # meeting value
        _prospect(4, ProspectState.CLOSED_WON, 15000.0),      # won
        _prospect(5, ProspectState.COMPLETED_DECLINED, 3000.0),  # lost
        _prospect(6, ProspectState.LOST, 4000.0),             # lost
        _prospect(7, ProspectState.UNRESPONSIVE_DEAD, 2000.0),  # lost
        _prospect(8, ProspectState.DISQUALIFIED, 9999.0),     # terminal, not counted anywhere
    ]
    db_session.add_all(prospects)
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).revenue_metrics()

    # estimated_pipeline_value is every still-OPEN deal, including one at
    # MEETING_BOOKED - a booked meeting isn't a closed outcome yet, so it's
    # both "open pipeline" and (separately) "meeting_value".
    assert data["estimated_pipeline_value"] == 5000.0 + 8000.0 + 20000.0
    assert data["meeting_value"] == 20000.0
    assert data["won_value"] == 15000.0
    assert data["lost_value"] == 3000.0 + 4000.0 + 2000.0


async def test_revenue_metrics_treats_missing_deal_values_as_zero(db_session):
    empty_tenant = TENANT + "-empty"
    db_session.add(_prospect(1, ProspectState.IDLE, None, tenant_id=empty_tenant))
    await db_session.flush()

    data = await AnalyticsService(db_session, empty_tenant).revenue_metrics()

    assert data["estimated_pipeline_value"] == 0.0
    assert data["meeting_value"] == 0.0
    assert data["won_value"] == 0.0
    assert data["lost_value"] == 0.0


async def test_revenue_metrics_is_scoped_per_tenant(db_session):
    other_tenant = TENANT + "-other"
    db_session.add(_prospect(1, ProspectState.CLOSED_WON, 100.0, tenant_id=other_tenant))
    db_session.add(_prospect(2, ProspectState.CLOSED_WON, 999.0, tenant_id=TENANT + "-isolated"))
    await db_session.flush()

    data = await AnalyticsService(db_session, other_tenant).revenue_metrics()
    assert data["won_value"] == 100.0
