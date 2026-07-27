import asyncio
from sqlalchemy import text
from app.database import engine

async def update_schema():
    async with engine.begin() as conn:
        try:
            # Create ENUM type if not exists
            await conn.execute(text("""
                DO $$ BEGIN
                    CREATE TYPE prospectstatus AS ENUM (
                        'IDLE', 'LI_REQ_SENT', 'LI_ACCEPTED_NO_MSG', 'LI_MSG_SENT', 
                        'EMAIL_SENT', 'CALL_QUEUED', 'CALL_IN_PROGRESS', 
                        'MEETING_BOOKED', 'PAUSED_NUDGED', 'COMPLETED_DECLINED', 
                        'UNRESPONSIVE_DEAD'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))
            print("Enum ProspectStatus ensured.")

            # Alter prospects table
            await conn.execute(text("ALTER TABLE prospects ADD COLUMN IF NOT EXISTS status prospectstatus DEFAULT 'IDLE' NOT NULL;"))
            await conn.execute(text("ALTER TABLE prospects ADD COLUMN IF NOT EXISTS call_attempts INTEGER DEFAULT 0 NOT NULL;"))
            await conn.execute(text("ALTER TABLE prospects ADD COLUMN IF NOT EXISTS last_call_attempt_at TIMESTAMP WITH TIME ZONE;"))
            await conn.execute(text("ALTER TABLE prospects ADD COLUMN IF NOT EXISTS next_action_at TIMESTAMP WITH TIME ZONE;"))
            print("Prospects table altered.")

            # Alter workspace_settings
            await conn.execute(text("ALTER TABLE workspace_settings ADD COLUMN IF NOT EXISTS dev_mode BOOLEAN DEFAULT FALSE NOT NULL;"))
            print("WorkspaceSettings table altered.")

        except Exception as e:
            print(f"Error altering schema: {e}")

if __name__ == "__main__":
    asyncio.run(update_schema())
