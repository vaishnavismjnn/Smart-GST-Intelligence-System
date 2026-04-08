# --- file: app.py ---
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="GST Intelligence Platform",
    page_icon="🧾",
    initial_sidebar_state="expanded"
)

# ── All CSS lives in styles.py ─────────────────────────────────
from styles import load_css
load_css()

# ── Auth gate ──────────────────────────────────────────────────
from utils.auth import is_authenticated

if not is_authenticated():
    from pages.login import show as login_show
    login_show()
else:
    # 1. This handles the Sidebar UI (The side buttons)
    from components.sidebar import render_sidebar
    render_sidebar()
    # 2. UI CLEANUP: Force hide the default Streamlit top-bar and padding
    st.markdown("""
        <style>
            
            
            /* Reduce top padding so content starts exactly at the top */
            .block-container { padding-top: 1.5rem !important; }
            
            /* Ensure the sidebar doesn't have an 'empty' feeling at the top */
            [data-testid="stSidebarNav"] { display: none; }
        </style>
    """, unsafe_allow_html=True)

    # 2. This gets the current choice from the sidebar
    page = st.session_state.get("page", "dashboard")

    # 3. This renders ONLY the page content in the main area
    if page == "dashboard":
        from pages.dashboard import show
        show()
    elif page == "upload":
        from pages.upload import show
        show()
    elif page == "records":
        from pages.records import show
        show()
    elif page == "profile":
        from pages.profile import show
        show()
    elif page == "itc":
        from pages.itc_forecaster import show
        show()
    elif page == "forensic":
        from pages.forensic_guard import show
        show()
    else:
        st.error("Page not found.")