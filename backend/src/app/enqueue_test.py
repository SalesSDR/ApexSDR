"""
Debug helper: Manually enqueue a job for any prospect.
Usage: Set PROSPECT_ID and JOB_NAME below and run:
  docker compose exec api_gateway python /app/src/app/enqueue_test.py
"""
import asyncio
from arq import create_pool
from arq.connections import RedisSettings

PROSPECT_ID = "REPLACE_WITH_PROSPECT_ID"
TENANT_ID = "org_test_123"
JOB_NAME = "start_outbound_sequence"  # or execute_initial_message_task, execute_follow_up_task, etc.

async def main():
    pool = await create_pool(RedisSettings(host='redis', port=6379, password='STRONG_AUTH_TOKEN'))
    print(f"Enqueueing {JOB_NAME} for prospect {PROSPECT_ID}...")
    job = await pool.enqueue_job(JOB_NAME, PROSPECT_ID, tenant_id=TENANT_ID)
    print(f"Job enqueued: {job}")

if __name__ == "__main__":
    asyncio.run(main())
