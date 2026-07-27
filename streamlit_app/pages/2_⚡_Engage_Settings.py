import os
import streamlit as st
import httpx

st.set_page_config(page_title="Engage Settings", page_icon="⚡", layout="wide")

BACKEND_URL = st.secrets.get("BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8000/api/v1"))

st.title("⚡ Engage Settings")
st.markdown("Configure your AI sequencing rules, limits, and Dev Mode testing overrides.")

# Fetch current settings
@st.cache_data(ttl=5)
def fetch_settings():
    try:
        res = httpx.get(f"{BACKEND_URL}/sequences/current", timeout=10.0)
        if res.status_code == 200:
            return res.json().get("rule", {})
        return None
    except Exception as e:
        st.error(f"Failed to fetch settings: {e}")
        return None

current_settings = fetch_settings()

if current_settings:
    with st.form("settings_form"):
        st.subheader("🛠️ Global Configuration")
        dev_mode = st.toggle("Dev/Test Mode (Overrides all intervals to 60 seconds)", value=current_settings.get("dev_mode", False))
        
        st.subheader("📬 LinkedIn Outreach")
        col1, col2 = st.columns(2)
        with col1:
            max_linkedin = st.number_input("Max LinkedIn Messages", min_value=1, max_value=10, value=current_settings.get("max_linkedin_msgs", 3))
        with col2:
            li_interval = st.number_input("Days Between LinkedIn Steps", min_value=1, max_value=30, value=current_settings.get("linkedin_interval_days", 1))
            
        st.subheader("📧 Email Outreach")
        col3, col4 = st.columns(2)
        with col3:
            max_emails = st.number_input("Max Emails", min_value=1, max_value=15, value=current_settings.get("max_emails", 4))
        with col4:
            email_interval = st.number_input("Days Between Emails", min_value=1, max_value=30, value=current_settings.get("email_interval_days", 1))

        st.subheader("📞 Voice Calling")
        col5, col6 = st.columns(2)
        with col5:
            max_calls = st.number_input("Max Voice Calls", min_value=1, max_value=5, value=current_settings.get("max_calls", 2))
        with col6:
            call_interval = st.number_input("Days Between Calls", min_value=1, max_value=30, value=current_settings.get("call_interval_days", 1))
            
        submitted = st.form_submit_button("💾 Save Settings", type="primary")
        
        if submitted:
            payload = {
                "max_linkedin_msgs": max_linkedin,
                "linkedin_interval_days": li_interval,
                "max_emails": max_emails,
                "email_interval_days": email_interval,
                "max_calls": max_calls,
                "call_interval_days": call_interval,
                "response_handling_action": current_settings.get("response_handling_action", "PAUSE_AND_NOTIFY"),
                "ai_guided_calls": current_settings.get("ai_guided_calls", True),
                "call_mode": current_settings.get("call_mode", "AUTOMATIC"),
                "assigned_lead_owner_id": current_settings.get("assigned_lead_owner_id"),
                "auto_handover_to_admin": current_settings.get("auto_handover_to_admin", True),
                "dev_mode": dev_mode
            }
            
            try:
                res = httpx.put(f"{BACKEND_URL}/sequences/rules", json=payload, timeout=10.0)
                if res.status_code == 200:
                    st.success("Settings saved successfully!")
                    fetch_settings.clear()
                    st.rerun()
                else:
                    st.error(f"Failed to save settings: {res.text}")
            except Exception as e:
                st.error(f"Error saving settings: {e}")
else:
    st.info("Loading settings...")
