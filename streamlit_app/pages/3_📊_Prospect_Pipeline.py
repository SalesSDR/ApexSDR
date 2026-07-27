import os
import time
import streamlit as st
import httpx
import pandas as pd

st.set_page_config(page_title="Prospect Pipeline", page_icon="📊", layout="wide")

BACKEND_URL = st.secrets.get("BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8000/api/v1"))

st.title("📊 Live Prospect Pipeline")
st.markdown("Monitor real-time state machine transitions and prospect statuses.")

auto_refresh = st.toggle("Auto-Refresh (10s)", value=False)

try:
    res = httpx.get(f"{BACKEND_URL}/prospects", timeout=10.0)
    if res.status_code == 200:
        prospects = res.json().get("data", [])
        
        if prospects:
            df = pd.DataFrame(prospects)
            
            # Status Metrics
            st.subheader("Pipeline Overview")
            
            status_counts = df['status'].value_counts().to_dict()
            
            # Define all 11 states to ensure they always show up
            all_states = [
                "IDLE", "LI_REQ_SENT", "LI_ACCEPTED_NO_MSG", "LI_MSG_SENT",
                "EMAIL_SENT", "CALL_QUEUED", "CALL_IN_PROGRESS", "MEETING_BOOKED",
                "PAUSED_NUDGED", "COMPLETED_DECLINED", "UNRESPONSIVE_DEAD"
            ]
            
            # Create a 4-column layout for metrics
            cols = st.columns(4)
            for idx, state in enumerate(all_states):
                col = cols[idx % 4]
                count = status_counts.get(state, 0)
                col.metric(label=state, value=count)
                
            st.divider()
            
            st.subheader("Live Prospect Data")
            display_df = df[['first_name', 'last_name', 'company_name', 'status', 'call_attempts', 'next_action_at', 'provider_id']]
            st.dataframe(display_df, use_container_width=True)
            
        else:
            st.info("No prospects in pipeline.")
    else:
        st.error(f"Failed to fetch prospects: {res.text}")
except Exception as e:
    st.error(f"Failed to connect to backend: {e}")

if auto_refresh:
    time.sleep(10)
    st.rerun()
