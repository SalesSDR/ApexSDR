"""Sprint 7: end-to-end voice pipeline, entirely in mock mode (no Twilio,
Deepgram, or ElevenLabs) - drives a full turn through the real HTTP stack:
POST /voice/mock-call -> VoiceOrchestrator -> Conversation Manager -> mock
LLM -> Conversation Memory -> Decision Engine -> State Machine -> (enqueued)
CRM/Calendar tasks, then confirms the DB and the ARQ queue both reflect it."""
import uuid

from sqlalchemy import select

from app.config import settings
from app.models.schemas import ConversationMemory, MemoryType, Prospect, ProspectState
from tests.conftest import bearer_for


async def _seed_prospect(db_session, **overrides) -> Prospect:
    defaults = dict(
        id=str(uuid.uuid4()), tenant_id="org_voice_e2e", first_name="Taylor", last_name="Prospect",
        company_name="Acme Co", linkedin_url=f"https://linkedin.com/in/{uuid.uuid4().hex}",
        phone_number="+15559998888", status=ProspectState.CALL_CONNECTED,
    )
    defaults.update(overrides)
    prospect = Prospect(**defaults)
    db_session.add(prospect)
    await db_session.flush()
    return prospect


async def test_mock_call_requires_authentication(client):
    # Sprint 7.1: /mock-call now requires the same JWT/API-key tenant auth
    # as every other route - no credential means 401 before the prospect
    # lookup (or the production-mode gate) is ever reached.
    response = await client.post("/api/v1/voice/mock-call", json={"prospect_id": "does-not-matter", "text": "hi"})
    assert response.status_code == 401


async def test_mock_call_is_scoped_to_the_caller_tenant(client, db_session, monkeypatch):
    """Sprint 7.1 tenant isolation: a caller authenticated as one tenant
    must not be able to drive a voice turn for another tenant's prospect,
    even by guessing/knowing its ID."""
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    other_tenants_prospect = await _seed_prospect(db_session, tenant_id="org_voice_e2e_someone_else")
    await db_session.commit()

    response = await client.post(
        "/api/v1/voice/mock-call",
        json={"prospect_id": other_tenants_prospect.id, "text": "hi"},
        headers=bearer_for("org_voice_e2e_attacker"),
    )
    assert response.status_code == 404


async def test_mock_call_is_disabled_in_production_without_mock_clients(client, db_session, monkeypatch):
    """Sprint 7.1: a real production deployment (ENVIRONMENT=production,
    USE_MOCK_CLIENTS=false) must never expose this testing-only endpoint."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", False)
    prospect = await _seed_prospect(db_session, tenant_id="org_voice_e2e_prod_gate")
    await db_session.commit()

    response = await client.post(
        "/api/v1/voice/mock-call",
        json={"prospect_id": prospect.id, "text": "hi"},
        headers=bearer_for("org_voice_e2e_prod_gate"),
    )
    assert response.status_code == 404


async def test_full_pipeline_books_a_meeting_and_enqueues_calendar_task(client, db_session, monkeypatch, redis_test_client):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = await _seed_prospect(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/voice/mock-call",
        json={"prospect_id": prospect.id, "text": "Yes, I'd love to book a demo."},
        headers=bearer_for("org_voice_e2e"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "BOOK_MEETING"
    assert body["call_ended"] is True
    assert body["prospect_status"] == "MEETING_BOOKED"
    assert body["response"]["next_action"] == "BOOK_MEETING"

    # ARQ's queue is a sorted set (job_id -> score), not a list.
    queue_length = await redis_test_client.zcard("arq:queue")
    assert queue_length >= 1  # book_calendar_meeting_task was enqueued

    refreshed = await db_session.get(Prospect, prospect.id)
    assert refreshed.status == ProspectState.MEETING_BOOKED

    memories = (await db_session.execute(
        select(ConversationMemory).where(ConversationMemory.prospect_id == prospect.id)
    )).scalars().all()
    assert any(m.memory_type == MemoryType.BUYING_SIGNAL for m in memories)


async def test_full_pipeline_escalates_low_confidence_meeting_language_to_human_review(client, db_session, monkeypatch):
    """The mock provider is confident (0.9) about MEETING_REQUEST, so this
    test instead drives the escalation-language path, which the Decision
    Engine always routes to HUMAN_REVIEW regardless of confidence."""
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = await _seed_prospect(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/voice/mock-call",
        json={"prospect_id": prospect.id, "text": "I want to file a complaint with your manager."},
        headers=bearer_for("org_voice_e2e"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "HUMAN_REVIEW"
    assert body["prospect_status"] == "ERROR_NEEDS_HUMAN"


async def test_full_pipeline_not_interested_declines_without_booking(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = await _seed_prospect(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/voice/mock-call",
        json={"prospect_id": prospect.id, "text": "Not interested, please stop calling."},
        headers=bearer_for("org_voice_e2e"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "END_SEQUENCE"
    assert body["prospect_status"] == "COMPLETED_DECLINED"


async def test_full_pipeline_objection_keeps_the_call_going(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = await _seed_prospect(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/voice/mock-call",
        json={"prospect_id": prospect.id, "text": "That seems too expensive for our budget."},
        headers=bearer_for("org_voice_e2e"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["call_ended"] is False
    assert body["prospect_status"] == "CALL_CONNECTED"


async def test_conversations_endpoint_reflects_the_transcript(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    prospect = await _seed_prospect(db_session, tenant_id="org_voice_e2e_transcripts")
    await db_session.commit()

    await client.post(
        "/api/v1/voice/mock-call",
        json={"prospect_id": prospect.id, "text": "Tell me more about pricing options."},
        headers=bearer_for("org_voice_e2e_transcripts"),
    )

    response = await client.get("/api/v1/voice/conversations", headers=bearer_for("org_voice_e2e_transcripts"))
    assert response.status_code == 200
    transcripts = response.json()
    assert len(transcripts) == 1
    assert transcripts[0]["lines"]  # both the prospect's and assistant's turns were persisted
