import streamlit as st

st.set_page_config(
    page_title="Apex SDR",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚡ Apex SDR")
st.markdown("""
Welcome to the **Apex SDR Unified Dashboard**.

Select a page from the sidebar to get started:
- **🎯 Define ICP:** Search for prospects using conversational AI.
- **⚡ Engage Settings:** Configure sequence rules and Dev Mode.
- **📊 Prospect Pipeline:** Monitor live pipeline progression.
- **📞 Call & Intent Logs:** View AI classifications and call outcomes.
""")
