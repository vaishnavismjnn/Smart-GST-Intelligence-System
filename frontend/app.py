# --- file: app.py ---

import streamlit as st

# ── Page Config MUST be first Streamlit call ─────────────────────
st.set_page_config(
    layout="wide",
    page_title="GST Intelligence Platform",
    page_icon="🧾",
    initial_sidebar_state="auto",
)

# ── Styles (injected before anything renders) ─────────────────────
from styles import load_css
load_css()

# ── Auth gate ─────────────────────────────────────────────────────
from utils.auth import is_authenticated

if not is_authenticated():
    from pages.login import show as login_show
    login_show()
else:
    from components.sidebar import render_sidebar
    render_sidebar()
# Hide Streamlit's auto-generated multi-page nav (we use our own)
# and tighten the top padding so page headers sit flush.
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] { display: none !important; }
        .block-container { padding-top: 1.5rem !important; }
    </style>
""", unsafe_allow_html=True)

# ── Page Routing ──────────────────────────────────────────────────
PAGE_MAP = {
    "dashboard": "pages.dashboard",
    "upload":    "pages.upload",
    "records":   "pages.records",
    "profile":   "pages.profile",
    "itc":       "pages.itc_forecaster",
    "forensic":  "pages.forensic_guard",
}

page = st.session_state.get("page", "dashboard")

if page in PAGE_MAP:
    try:
        module = __import__(PAGE_MAP[page], fromlist=["show"])
        module.show()
    except Exception as e:
        st.error(f"Error loading page '{page}': {e}")
else:
    st.error("Page not found.")
