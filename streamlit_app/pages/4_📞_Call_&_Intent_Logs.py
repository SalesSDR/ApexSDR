import os
import streamlit as st
import httpx
import pandas as pd

st.set_page_config(page_title="Call & Intent Logs", page_icon="📞", layout="wide")

BACKEND_URL = st.secrets.get("BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8000/api/v1"))

st.title("📞 Call Outcomes & AI Intent Analytics")
st.markdown("Review Twilio call outcomes and Gemini 2.0 Flash intent classifications from prospect replies.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🤖 AI Intent Analysis (Replies)")
    try:
        res = httpx.get(f"{BACKEND_URL}/analytics/intents", timeout=10.0)
        if res.status_code == 200:
            intents = res.json().get("data", [])
            if intents:
                df_intents = pd.DataFrame(intents)
                # Style intents with colors
                def color_intent(val):
                    color = 'green' if val == 'POSITIVE' else 'red' if val == 'NEGATIVE' else 'gray'
                    return f'color: {color}; font-weight: bold;'
                
                st.dataframe(df_intents.style.map(color_intent, subset=['intent']), use_container_width=True)
            else:
                st.info("No AI intent logs found yet.")
        else:
            st.error("Failed to fetch intent logs.")
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")

with col2:
    st.subheader("📞 Twilio Call Logs")
    try:
        res = httpx.get(f"{BACKEND_URL}/analytics/calls", timeout=10.0)
        if res.status_code == 200:
            calls = res.json().get("data", [])
            if calls:
                df_calls = pd.DataFrame(calls)
                st.dataframe(df_calls, use_container_width=True)
            else:
                st.info("No Twilio call logs found yet.")
        else:
            st.error("Failed to fetch call logs.")
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")
