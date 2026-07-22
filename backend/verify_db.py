import asyncio
import os
import sys

# Ensure we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from app.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.schemas import Prospect, FollowUp

async def verify():
    print("Connecting to DB to verify side-effects...")
    async with AsyncSessionLocal() as db:
        # Check Prospect State
        p_res = await db.execute(select(Prospect).where(Prospect.id == "14d8c822-9cbd-4fe6-a6c9-0e06c144bd1d"))
        prospect = p_res.scalar_one_or_none()
        if prospect:
            print(f"Prospect ID: {prospect.id}")
            print(f"Current State: {prospect.current_state}")
        else:
            print("Prospect NOT FOUND!")
            
        # Check FollowUp States
        f_res = await db.execute(select(FollowUp).where(FollowUp.prospect_id == "14d8c822-9cbd-4fe6-a6c9-0e06c144bd1d"))
        follow_ups = f_res.scalars().all()
        print(f"Found {len(follow_ups)} FollowUp rows:")
        for f in follow_ups:
            print(f"- FollowUp ID {f.id} -> Status: {f.status}")

if __name__ == "__main__":
    asyncio.run(verify())
