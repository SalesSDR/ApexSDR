import asyncio
import sys
sys.path.insert(0, '/app/src')
from arq import create_pool
from arq.connections import RedisSettings

async def main():
    p = await create_pool(RedisSettings.from_dsn('redis://apex_sdr_redis:6379/0'))
    await p.enqueue_job('execute_initial_message_task', '87bb034d-c3e8-4c5b-852e-1c078a93ed3b', 'default_tenant')
    await p.close()

if __name__ == '__main__':
    asyncio.run(main())
