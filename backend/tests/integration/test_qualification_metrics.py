"""Sprint 4, item 6 (Analytics): qualification/priority distribution,
average score, and top ICP matches."""
from app.models.schemas import Prospect, ProspectState, QualificationLevel
from app.services.analytics.service import AnalyticsService

TENANT = "qual-metrics-tenant"


def _prospect(n, **overrides):
    defaults = dict(
        tenant_id=TENANT, first_name=f"P{n}", last_name="Test",
        linkedin_url=f"https://linkedin.com/in/qm{n}", status=ProspectState.IDLE,
    )
    defaults.update(overrides)
    return Prospect(**defaults)


async def test_qualification_metrics_reports_distribution_average_and_top_matches(db_session):
    prospects = [
        _prospect(1, qualification_score=90.0, qualification_level=QualificationLevel.HOT, qualification_reason="great fit"),
        _prospect(2, qualification_score=60.0, qualification_level=QualificationLevel.HIGH, qualification_reason="good fit"),
        _prospect(3, qualification_score=45.0, qualification_level=QualificationLevel.MEDIUM, qualification_reason="ok fit"),
        _prospect(4, qualification_score=10.0, qualification_level=QualificationLevel.LOW, qualification_reason="poor fit", status=ProspectState.DISQUALIFIED),
        _prospect(5, status=ProspectState.NEW),  # not yet scored
    ]
    db_session.add_all(prospects)
    await db_session.flush()

    data = await AnalyticsService(db_session, TENANT).qualification_metrics(top_n=2)

    assert data["qualification_distribution"] == {"HOT": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 1}
    assert data["priority_distribution"] == data["qualification_distribution"]
    assert data["not_yet_scored"] == 1
    assert data["scored_count"] == 4
    assert data["average_score"] == round((90.0 + 60.0 + 45.0 + 10.0) / 4, 2)

    assert len(data["top_icp_matches"]) == 2
    assert data["top_icp_matches"][0]["qualification_score"] == 90.0
    assert data["top_icp_matches"][0]["qualification_level"] == "HOT"
    assert data["top_icp_matches"][1]["qualification_score"] == 60.0


async def test_qualification_metrics_handles_no_scored_prospects(db_session):
    empty_tenant = TENANT + "-empty"
    db_session.add(_prospect(1, tenant_id=empty_tenant, status=ProspectState.NEW))
    await db_session.flush()

    data = await AnalyticsService(db_session, empty_tenant).qualification_metrics()

    assert data["average_score"] is None
    assert data["scored_count"] == 0
    assert data["top_icp_matches"] == []
    assert all(count == 0 for count in data["qualification_distribution"].values())
