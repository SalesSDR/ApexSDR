import asyncio
from sqlalchemy import select, update
from app.database import AsyncSessionLocal, get_redis
from app.models.schemas import Prospect
from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings

async def main():
    prospect_id = "87bb034d-c3e8-4c5b-852e-1c078a93ed3b"
    tenant_id = "org_test_123"
    
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Prospect)
            .where(Prospect.id == prospect_id)
            .values(current_state="PROSPECT_CREATED")
        )
        await db.commit()
        print("Set prospect back to PROSPECT_CREATED")

    arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await arq_pool.enqueue_job("start_outbound_sequence", prospect_id, tenant_id=tenant_id)
    print("Enqueued start_outbound_sequence")
    await arq_pool.close()

if __name__ == "__main__":
    asyncio.run(main())
