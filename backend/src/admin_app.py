import streamlit as st
import asyncio
import httpx
import json
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

st.set_page_config(page_title="ApexSDR Admin", page_icon="🚀", layout="wide")

st.title("🚀 ApexSDR Internal Admin Console")

# --- Config & DB ---
DATABASE_URL = os.getenv("DATABASE_ASYNC_URL", "postgresql+asyncpg://sdr_admin:SECURE_VAULT_PW@localhost:5433/apex_sdr_prod")
API_URL = "http://api_gateway:8000" if os.getenv("DATABASE_ASYNC_URL") else "http://localhost:8000"

@st.cache_resource
def get_db_engine():
    return create_async_engine(DATABASE_URL, echo=False)

engine = get_db_engine()
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# --- Sidebar Navigation ---
page = st.sidebar.selectbox("Select Tool", ["Pipeline Visualizer", "Agent Tester", "Webhook Simulator", "Worker Status"])

# --- 1. Pipeline Visualizer ---
if page == "Pipeline Visualizer":
    st.header("📊 Real-time Prospect Pipeline")
    
    async def fetch_pipeline_stats():
        async with AsyncSessionLocal() as session:
            # Query prospects grouped by status (assuming standard status field)
            try:
                result = await session.execute(text("SELECT status, COUNT(*) FROM prospects GROUP BY status"))
                return result.fetchall()
            except Exception as e:
                return [("Error", str(e))]

    stats = asyncio.run(fetch_pipeline_stats())
    
    if stats and stats[0][0] != "Error":
        col1, col2, col3 = st.columns(3)
        metrics = {row[0]: row[1] for row in stats}
        col1.metric("Active Prospects", metrics.get("active", 0))
        col2.metric("Paused", metrics.get("paused", 0))
        col3.metric("Bounced/Failed", metrics.get("failed", 0))
        st.bar_chart(metrics)
    else:
        st.warning(f"Could not fetch data: {stats[0][1] if stats else 'No data'}")
        st.info("Ensure the database tables are created and seeded.")

# --- 2. Agent Prompt Tester ---
elif page == "Agent Tester":
    st.header("🤖 Gemini Agent Prompt & Fallback Tester")
    
    context_input = st.text_area("Prospect Context (JSON or Text)", value="{'name': 'John Doe', 'company': 'Acme Corp', 'role': 'CTO'}")
    prompt_input = st.text_area("System Prompt / Goal", value="Draft a highly personalized LinkedIn connection request for this prospect.")
    
    if st.button("Run Agent Test"):
        with st.spinner("Testing Agent..."):
            # Import dynamically to avoid breaking Streamlit if agent is not ready
            try:
                from app.services.agent import GeminiOrchestrator
                import traceback
                
                orchestrator = GeminiOrchestrator()
                # Simulate a generic run (we'll implement draft_channel_outreach)
                # Since we don't have async event loop in button natively, we run it manually
                async def run_agent():
                    try:
                        return await orchestrator.draft_channel_outreach("linkedin", "friendly", json.dumps(context_input))
                    except Exception as e:
                        print("Fallback triggered")
                        from app.services.ai import generate_outreach_message
                        return await generate_outreach_message("Jane Doe", "Acme Corp", "linkedin", True)

                result = asyncio.run(run_agent())
                st.success("Agent Response:")
                st.write(result)
            except Exception as e:
                st.error(f"Error testing agent: {str(e)}")
                st.code(traceback.format_exc())

# --- 3. Webhook Simulator ---
elif page == "Webhook Simulator":
    st.header("🔌 Webhook Simulator (n8n -> FastAPI)")
    
    webhook_type = st.selectbox("Webhook Event Type", ["trigger-outreach", "reply-received"])
    
    payload = st.text_area("Payload (JSON)", value=json.dumps({
        "prospect_id": "12345",
        "channel": "email",
        "message": "I'm interested, let's chat next week.",
        "intent": "MEETING_REQUESTED"
    }, indent=2), height=200)
    
    if st.button("Send Webhook"):
        try:
            parsed_payload = json.loads(payload)
            with httpx.Client() as client:
                resp = client.post(f"{API_URL}/api/v1/webhooks/n8n/{webhook_type}", json=parsed_payload)
                if resp.status_code == 200:
                    st.success(f"Success! {resp.json()}")
                else:
                    st.error(f"Failed [{resp.status_code}]: {resp.text}")
        except json.JSONDecodeError:
            st.error("Invalid JSON payload.")
        except Exception as e:
            st.error(f"Connection Error: {e}")

# --- 4. ARQ Worker Status ---
elif page == "Worker Status":
    st.header("⚙️ ARQ Worker & Redis Queue Status")
    
    import redis.asyncio as redis
    
    async def get_redis_info():
        REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")
        try:
            r = redis.from_url(REDIS_URL)
            info = await r.info()
            keys = await r.keys('arq:*')
            await r.close()
            return info, len(keys)
        except Exception as e:
            return None, str(e)
            
    info, jobs = asyncio.run(get_redis_info())
    
    if info:
        st.success("Redis Connection Active")
        st.metric("Pending ARQ Jobs", jobs)
        st.json({"connected_clients": info.get("connected_clients"), "used_memory_human": info.get("used_memory_human")})
    else:
        st.error(f"Could not connect to Redis: {jobs}")
