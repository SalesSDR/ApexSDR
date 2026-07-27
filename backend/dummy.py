import asyncio
from redis.asyncio import Redis
from arq import create_pool
from arq.connections import RedisSettings
import os

async def main():
    pool = await create_pool(RedisSettings(host='redis', port=6379, password='STRONG_AUTH_TOKEN'))
    prospect_id = "53e36ae3-571d-4c95-9960-d53b4b0d480b"
    tenant_id = "5b26ce9d-9273-455b-9d41-e945c7b3992b"  # Let's get the tenant ID from DB. Wait. Let's just pass dummy for now or query it.
    
if __name__ == "__main__":
    pass
