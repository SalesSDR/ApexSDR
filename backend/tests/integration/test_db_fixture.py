from sqlalchemy import select

from app.models.schemas import Prospect


async def test_prospect_round_trips_through_isolated_test_db(db_session):
    prospect = Prospect(
        tenant_id="test-tenant",
        first_name="Ada",
        last_name="Lovelace",
        linkedin_url="https://linkedin.com/in/ada",
    )
    db_session.add(prospect)
    await db_session.flush()

    result = await db_session.execute(select(Prospect).where(Prospect.id == prospect.id))
    fetched = result.scalar_one()

    assert fetched.first_name == "Ada"
    assert fetched.current_state == "PROSPECT_CREATED"
