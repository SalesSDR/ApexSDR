import asyncio
import os
import sys

# Ensure backend/src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'src'))

from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.schemas import Prospect
from sqlalchemy import select

async def main():
    prospect_id = "87bb034d-c3e8-4c5b-852e-1c078a93ed3b"
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
        prospect = res.scalar_one_or_none()
        if not prospect:
            print(f"Prospect {prospect_id} not found!")
            return
            
        print(f"Found Prospect: {prospect.first_name} {prospect.last_name}")
        tenant_id = prospect.tenant_id

    pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    
    print(f"Enqueueing start_outbound_sequence for {prospect_id}...")
    await pool.enqueue_job(
        'start_outbound_sequence',
        prospect_id,
        tenant_id=tenant_id
    )
    print("Job enqueued successfully!")

if __name__ == "__main__":
    asyncio.run(main())
