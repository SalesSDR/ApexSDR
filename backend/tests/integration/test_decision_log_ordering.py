"""DecisionLog deterministic ordering (Sprint 2, item 5). DecisionLog.created_at
uses the ORM default=func.now(), which in Postgres returns the *transaction*
start time - two rows inserted in the same transaction (a common case: e.g.
qualification's MARK_QUALIFIED followed immediately by the supervisor's
SEND_LINKEDIN within one session) get an identical created_at, so "ORDER BY
created_at DESC" has no defined tiebreak. sequence_number (a real Postgres
IDENTITY column) is what must actually be used - these tests reproduce the
exact same-transaction scenario and confirm ordering is stable."""
from datetime import UTC

from sqlalchemy import select

from app.models.schemas import DecisionLog, DecisionType, Prospect
from tests.conftest import bearer_for


async def test_two_decisions_in_the_same_transaction_get_distinct_sequence_numbers(db_session):
    prospect = Prospect(
        tenant_id="order-tenant", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-order",
    )
    db_session.add(prospect)
    await db_session.flush()

    log_1 = DecisionLog(
        tenant_id="order-tenant", prospect_id=prospect.id, decision_type=DecisionType.MARK_QUALIFIED,
        reason="first", confidence=0.9, prospect_status_at_decision="ENRICHING",
    )
    log_2 = DecisionLog(
        tenant_id="order-tenant", prospect_id=prospect.id, decision_type=DecisionType.SEND_LINKEDIN,
        reason="second", confidence=0.95, prospect_status_at_decision="IDLE",
    )
    db_session.add(log_1)
    await db_session.flush()  # log_1 committed to this transaction first
    db_session.add(log_2)
    await db_session.flush()  # same transaction, same func.now() value as log_1

    # The bug this replaces: both rows can share an identical created_at.
    assert log_1.sequence_number is not None
    assert log_2.sequence_number is not None
    assert log_2.sequence_number > log_1.sequence_number  # strictly increasing per insert


async def test_ordering_by_sequence_number_is_stable_even_with_identical_created_at(db_session, monkeypatch):
    """Forces both rows to have the exact same created_at (simulating the
    worst case even more directly than transaction-timing alone) and
    confirms sequence_number still orders them correctly."""
    from datetime import datetime
    frozen_time = datetime(2026, 1, 1, tzinfo=UTC)

    prospect = Prospect(
        tenant_id="order-tenant-2", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-order",
    )
    db_session.add(prospect)
    await db_session.flush()

    log_1 = DecisionLog(
        tenant_id="order-tenant-2", prospect_id=prospect.id, decision_type=DecisionType.MARK_QUALIFIED,
        reason="oldest-by-insertion", confidence=0.9, prospect_status_at_decision="ENRICHING",
        created_at=frozen_time,
    )
    db_session.add(log_1)
    await db_session.flush()

    log_2 = DecisionLog(
        tenant_id="order-tenant-2", prospect_id=prospect.id, decision_type=DecisionType.SEND_LINKEDIN,
        reason="newest-by-insertion", confidence=0.95, prospect_status_at_decision="IDLE",
        created_at=frozen_time,  # identical timestamp, forced
    )
    db_session.add(log_2)
    await db_session.flush()

    assert log_1.created_at == log_2.created_at  # confirms the ambiguous-timestamp scenario is real

    rows = (await db_session.execute(
        select(DecisionLog)
        .where(DecisionLog.prospect_id == prospect.id)
        .order_by(DecisionLog.sequence_number.desc())
    )).scalars().all()

    assert [r.reason for r in rows] == ["newest-by-insertion", "oldest-by-insertion"]


async def test_decisions_api_returns_most_recent_first_despite_identical_timestamps(client, db_session):
    """End-to-end through the real /decisions endpoint (api/v1/decisions.py),
    not just the raw query - the actual regression this sprint item fixes."""
    from datetime import datetime
    frozen_time = datetime(2026, 1, 1, tzinfo=UTC)

    prospect = Prospect(
        tenant_id="order-api-tenant", first_name="Katherine", last_name="Johnson",
        linkedin_url="https://linkedin.com/in/katherine-order-api",
    )
    db_session.add(prospect)
    await db_session.flush()

    db_session.add(DecisionLog(
        tenant_id="order-api-tenant", prospect_id=prospect.id, decision_type=DecisionType.MARK_QUALIFIED,
        reason="oldest", confidence=0.9, prospect_status_at_decision="ENRICHING", created_at=frozen_time,
    ))
    await db_session.flush()
    db_session.add(DecisionLog(
        tenant_id="order-api-tenant", prospect_id=prospect.id, decision_type=DecisionType.SEND_LINKEDIN,
        reason="newest", confidence=0.95, prospect_status_at_decision="IDLE", created_at=frozen_time,
    ))
    await db_session.flush()

    response = await client.get(
        f"/api/v1/decisions/{prospect.id}", headers=bearer_for("order-api-tenant")
    )

    assert response.status_code == 200
    reasons = [entry["reason"] for entry in response.json()["data"]]
    assert reasons == ["newest", "oldest"]
