from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.ai as ai_module
import app.workers.tasks as tasks
from app.services.crm.mock import MockHubSpotAdapter
from app.services.crm.service import CRMService
from app.services.decision.engine import DecisionEngine
from app.services.linkedin.mock import MockLinkedInAdapter
from app.services.linkedin.service import LinkedInQueueService
from app.workers.tasks import run_waterfall_enrichment_task, start_outbound_sequence
from tests.conftest import bearer_for


class _FakeRedis:
    async def enqueue_job(self, name, *args, **kwargs):
        pass


async def _ret(value):
    return value


async def test_analytics_endpoints_reflect_a_prospect_driven_through_the_real_pipeline(client, db_session, monkeypatch):
    """End-to-end: create a prospect through the real API, drive it through
    the real qualification + outbound-sequence tasks (same functions the
    live worker calls), then confirm the analytics endpoints - hit through
    the real HTTP layer - report it correctly. This is the guarantee that
    AnalyticsService reads the same data the pipeline actually writes,
    not a parallel/duplicated view of it."""
    monkeypatch.setattr(tasks, "enrich_email_waterfall", lambda **kw: _ret("e2e@example.com"))
    monkeypatch.setattr(tasks, "enrich_phone_waterfall", lambda **kw: _ret(None))
    monkeypatch.setattr(tasks, "apply_jitter", lambda ctx, dev_mode=False: _ret(None))
    monkeypatch.setattr(ai_module, "generate_outreach_message", lambda *a, **kw: _ret("Looking forward to connecting!"))

    create_resp = await client.post(
        "/api/v1/prospects",
        json={
            "first_name": "Analytics",
            "last_name": "E2E",
            "email": "analytics.e2e@example.com",
            "linkedin_url": "https://linkedin.com/in/analytics-e2e",
        },
        headers=bearer_for("org_analytics_e2e"),
    )
    assert create_resp.status_code == 201
    prospect_id = create_resp.json()["data"]["id"]

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    crm_service = CRMService(MockHubSpotAdapter())

    await run_waterfall_enrichment_task(
        {"sessionmaker": session_factory, "crm_service": crm_service, "redis": _FakeRedis(), "decision_engine": DecisionEngine()},
        prospect_id,
    )
    await start_outbound_sequence(
        {
            "sessionmaker": session_factory,
            "linkedin_queue": LinkedInQueueService(MockLinkedInAdapter()),
            "crm_service": crm_service,
        },
        prospect_id,
        "org_analytics_e2e",
    )

    funnel_resp = await client.get(
        "/api/v1/analytics/metrics/funnel", headers=bearer_for("org_analytics_e2e")
    )
    by_state_resp = await client.get(
        "/api/v1/analytics/metrics/prospects-by-state", headers=bearer_for("org_analytics_e2e")
    )
    outreach_resp = await client.get(
        "/api/v1/analytics/metrics/outreach", headers=bearer_for("org_analytics_e2e")
    )

    funnel_by_stage = {s["stage"]: s["count"] for s in funnel_resp.json()["data"]["stages"]}
    assert funnel_by_stage["outreach_in_progress"] == 1

    assert by_state_resp.json()["data"]["by_state"]["LI_REQ_SENT"] == 1

    assert outreach_resp.json()["data"]["currently_in_linkedin_outreach"] == 1
