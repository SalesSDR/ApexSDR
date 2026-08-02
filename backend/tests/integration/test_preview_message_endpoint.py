"""Sprint 4, item 3: GET /prospects/{id}/preview-message wires
build_prospect_context + generate_outreach_message's `context` parameter
end-to-end - the one real call site this sprint can reach, since the
autonomous pipeline's own send call sites live in the Sequence Engine (out
of scope this sprint)."""
import app.api.v1.prospects as prospects_module
from app.models.schemas import Prospect, ProspectState
from tests.conftest import bearer_for


async def test_preview_message_uses_enrichment_context(client, db_session, monkeypatch):
    captured = {}

    async def _fake_generate(prospect_name, company, prompt_type="linkedin", fallback_mode=True, context=None):
        captured["context"] = context
        return "Hi there, personalized message."

    monkeypatch.setattr(prospects_module, "generate_outreach_message", _fake_generate)

    prospect = Prospect(
        tenant_id="org_preview", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-preview", status=ProspectState.IDLE,
        company_name="Acme Inc", job_title="VP of Engineering", industry="Fintech",
    )
    db_session.add(prospect)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/prospects/{prospect.id}/preview-message", headers=bearer_for("org_preview")
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["message"] == "Hi there, personalized message."
    assert captured["context"]["job_title"] == "VP of Engineering"
    assert captured["context"]["industry"] == "Fintech"


async def test_preview_message_404s_for_an_unknown_prospect(client):
    response = await client.get(
        "/api/v1/prospects/does-not-exist/preview-message", headers=bearer_for("org_preview_404")
    )
    assert response.status_code == 404


async def test_preview_message_requires_authentication(client, db_session):
    prospect = Prospect(
        tenant_id="org_preview_auth", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-preview", status=ProspectState.IDLE,
    )
    db_session.add(prospect)
    await db_session.flush()

    response = await client.get(f"/api/v1/prospects/{prospect.id}/preview-message")
    assert response.status_code in (401, 403)
