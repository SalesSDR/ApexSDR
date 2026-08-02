"""Large-dataset check: aggregation must stay correct (and reasonably fast -
a handful of GROUP BY queries, not one query per row) at a size well above
what a manual/spot-check test would use."""
import time

from app.models.schemas import Prospect, ProspectState
from app.services.analytics.service import AnalyticsService

TENANT = "large-tenant"
ROW_COUNT = 600


async def test_aggregation_stays_correct_and_fast_at_scale(db_session):
    states = list(ProspectState)
    prospects = []
    for i in range(ROW_COUNT):
        status = states[i % len(states)]
        prospects.append(Prospect(
            tenant_id=TENANT,
            first_name=f"Bulk{i}",
            last_name="Prospect",
            linkedin_url=f"https://linkedin.com/in/bulk{i}",
            status=status,
            retry_count=i % 4,
        ))
    db_session.add_all(prospects)
    await db_session.flush()

    service = AnalyticsService(db_session, TENANT)

    started = time.monotonic()
    funnel = await service.pipeline_funnel()
    by_state = await service.prospects_by_state()
    retry = await service.retry_metrics()
    elapsed = time.monotonic() - started

    assert funnel["total_prospects"] == ROW_COUNT
    assert sum(s["count"] for s in funnel["stages"]) == ROW_COUNT
    assert sum(by_state["by_state"].values()) == ROW_COUNT

    expected_per_state = ROW_COUNT // len(states)
    for state in states:
        # Every state appears the same number of times except a handful that
        # absorb the remainder from ROW_COUNT % len(states).
        assert by_state["by_state"][state.value] in (expected_per_state, expected_per_state + 1)

    assert sum(retry["retry_count_distribution"].values()) == ROW_COUNT

    # Three GROUP BY queries over 600 rows should be well under a second even
    # on a slow CI box - this is a regression guard against an accidental
    # N+1 (which would make this take seconds, not milliseconds).
    assert elapsed < 5.0
