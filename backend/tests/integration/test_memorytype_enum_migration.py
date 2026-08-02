"""Regression test for the BUYING_SIGNAL enum mismatch: the Python
MemoryType enum included BUYING_SIGNAL long before the Postgres `memorytype`
type was ever altered to add it (migration 4b083897ce1b only created the
original 7 values). Any BuyingSignalEngine._process_single_signal() or
voice_ai/transcript.py write of a BUYING_SIGNAL memory would raise
`invalid input value for enum memorytype` against a real database - a bug
the unit tests never caught because they mock the DB session away
entirely. This MUST run against real Postgres (db_session, not a mock) to
mean anything - see migration b1c2d3e4f5a6_fix_memorytype_buying_signal."""
from sqlalchemy import select

from app.models.schemas import ConversationMemory, MemoryType, Prospect


async def test_buying_signal_memory_type_can_be_persisted(db_session):
    prospect = Prospect(
        tenant_id="enum-fix-tenant", first_name="Ada", last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada-enum-fix",
    )
    db_session.add(prospect)
    await db_session.flush()

    memory = ConversationMemory(
        prospect_id=prospect.id,
        tenant_id="enum-fix-tenant",
        memory_type=MemoryType.BUYING_SIGNAL,
        content="Company just raised a Series B",
        source="SIGNAL_ENGINE",
        metadata_={"signal_type": "FUNDING_EVENT"},
    )
    db_session.add(memory)
    # The bug manifests here: without the migration, Postgres rejects the
    # INSERT with "invalid input value for enum memorytype: 'BUYING_SIGNAL'".
    await db_session.flush()

    rows = (await db_session.execute(
        select(ConversationMemory).where(ConversationMemory.prospect_id == prospect.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].memory_type == MemoryType.BUYING_SIGNAL


async def test_every_memorytype_value_can_be_persisted(db_session):
    """Broader safety net: every value the Python enum defines must exist
    in the database enum, not just BUYING_SIGNAL - catches any future
    addition to MemoryType that forgets its migration the same way."""
    prospect = Prospect(
        tenant_id="enum-fix-tenant-2", first_name="Grace", last_name="Hopper",
        linkedin_url="https://linkedin.com/in/grace-enum-fix",
    )
    db_session.add(prospect)
    await db_session.flush()

    for memory_type in MemoryType:
        db_session.add(ConversationMemory(
            prospect_id=prospect.id,
            tenant_id="enum-fix-tenant-2",
            memory_type=memory_type,
            content=f"Testing {memory_type.value}",
            source="TEST",
        ))
    await db_session.flush()

    rows = (await db_session.execute(
        select(ConversationMemory).where(ConversationMemory.prospect_id == prospect.id)
    )).scalars().all()
    assert {r.memory_type for r in rows} == set(MemoryType)
