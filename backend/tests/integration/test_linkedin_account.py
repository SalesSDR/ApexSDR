from datetime import date, timedelta

from sqlalchemy import select

from app.models.schemas import LinkedInAccount
from app.services.linkedin.mock import MockLinkedInAdapter
from app.services.linkedin.service import LinkedInQueueService


async def test_get_or_create_account_creates_once_and_reuses(db_session):
    service = LinkedInQueueService(MockLinkedInAdapter())

    first = await service.get_or_create_account(db_session, "tenant-a", "acc_1", daily_limit=20)
    second = await service.get_or_create_account(db_session, "tenant-a", "acc_1", daily_limit=20)

    assert first.id == second.id

    rows = (await db_session.execute(
        select(LinkedInAccount).where(LinkedInAccount.tenant_id == "tenant-a", LinkedInAccount.account_id == "acc_1")
    )).scalars().all()
    assert len(rows) == 1  # no duplicate row created on the second call


async def test_get_or_create_account_is_scoped_per_tenant_and_account(db_session):
    # Multi-account support: different accounts (or different tenants using
    # the same underlying account_id) get independent rows/quotas.
    service = LinkedInQueueService(MockLinkedInAdapter())

    tenant_a = await service.get_or_create_account(db_session, "tenant-a", "acc_shared", daily_limit=20)
    tenant_b = await service.get_or_create_account(db_session, "tenant-b", "acc_shared", daily_limit=20)
    account_2 = await service.get_or_create_account(db_session, "tenant-a", "acc_2", daily_limit=20)

    assert tenant_a.id != tenant_b.id
    assert tenant_a.id != account_2.id


async def test_get_or_create_account_resets_stale_daily_count_immediately(db_session):
    service = LinkedInQueueService(MockLinkedInAdapter())
    db_session.add(LinkedInAccount(
        tenant_id="tenant-stale", account_id="acc_1",
        daily_send_count=20, daily_limit=20, daily_count_date=date.today() - timedelta(days=2),
    ))
    await db_session.flush()

    account = await service.get_or_create_account(db_session, "tenant-stale", "acc_1", daily_limit=20)

    assert account.daily_send_count == 0
    assert account.daily_count_date == date.today()
