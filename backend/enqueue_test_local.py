import asyncio
from redis.asyncio import Redis
from arq import create_pool
from arq.connections import RedisSettings
import os
from dotenv import load_dotenv

load_dotenv(".env.production")

async def main():
    pool = await create_pool(RedisSettings(
        host='localhost', 
        port=6379, 
        password=os.getenv("REDIS_PASSWORD")
    ))
    prospect_id = "53e36ae3-571d-4c95-9960-d53b4b0d480b"
    print(f"Enqueueing execute_email_dispatch_task for prospect {prospect_id}...")
    job = await pool.enqueue_job('execute_email_dispatch_task', prospect_id)
    print(f"Job enqueued: {job}")

if __name__ == "__main__":
    asyncio.run(main())
