import os
import streamlit as st
import httpx
import pandas as pd

st.set_page_config(page_title="Define ICP", page_icon="🎯", layout="wide")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")

if "preview_leads" not in st.session_state:
    st.session_state["preview_leads"] = []

if "unipile_account_id" not in st.session_state:
    st.session_state["unipile_account_id"] = ""

st.title("🎯 Define ICP & Live Search")

st.markdown("Use conversational AI to find prospects via Unipile's live LinkedIn integration.")

st.subheader("1. Configuration")
st.session_state["unipile_account_id"] = st.text_input("Unipile Account ID (Optional)", value=st.session_state["unipile_account_id"], help="Leave blank to use default from backend .env")

st.subheader("2. Conversational Search")
prompt = st.text_area("What kind of prospects are you looking for?", placeholder="e.g., Show me VPs of Marketing at SaaS companies in California")

if st.button("Search Prospects", type="primary"):
    if not prompt:
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Parsing intent & fetching live data via Unipile..."):
            try:
                payload = {"prompt": prompt}
                if st.session_state["unipile_account_id"]:
                    payload["account_id"] = st.session_state["unipile_account_id"]
                    
                response = httpx.post(f"{BACKEND_URL}/icp/preview", json=payload, timeout=45.0)
                if response.status_code == 200:
                    data = response.json()
                    st.session_state["preview_leads"] = data.get("leads", [])
                    st.success(f"Found {len(st.session_state['preview_leads'])} prospects!")
                else:
                    st.error(f"Error fetching prospects: {response.text}")
            except Exception as e:
                st.error(f"Failed to connect to backend: {e}")

st.subheader("3. Lead Preview & Approval")
if st.session_state["preview_leads"]:
    df = pd.DataFrame(st.session_state["preview_leads"])
    
    # Add a selection column at the front
    df.insert(0, "Select", True)
    
    # Display editable dataframe
    edited_df = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("Approve", default=True),
            "linkedin_url": st.column_config.LinkColumn("Profile URL")
        }
    )
    
    if st.button("🚀 Approve & Start Sequence", type="primary"):
        selected_rows = edited_df[edited_df["Select"] == True]
        if selected_rows.empty:
            st.warning("No leads selected.")
        else:
            with st.spinner("Importing leads into pipeline..."):
                profiles = []
                for _, row in selected_rows.iterrows():
                    profiles.append({
                        "provider_id": str(row.get("id")),
                        "first_name": row.get("first_name", ""),
                        "last_name": row.get("last_name", ""),
                        "title": row.get("title", ""),
                        "organization_name": row.get("company", ""),
                        "linkedin_url": row.get("linkedin_url", ""),
                        "email": row.get("email", "") or f"placeholder_{row.get('id')}@example.com"
                    })
                
                try:
                    res = httpx.post(f"{BACKEND_URL}/prospects/import-from-unipile", json={"profiles": profiles}, timeout=30.0)
                    if res.status_code == 200:
                        data = res.json()
                        st.success(f"Imported {data.get('imported', 0)} prospects. Skipped {data.get('skipped', 0)} duplicates.")
                        st.session_state["preview_leads"] = []
                        st.rerun()
                    else:
                        st.error(f"Failed to import: {res.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")
else:
    st.info("No leads to preview. Run a search above.")
