# --- file: components/sidebar.py ---
# CSS for sidebar classes is in styles.py (sb-brand, sb-user, sb-nav-* etc.)

import streamlit as st
from utils.auth import logout, get_user_initials

PAGES = [
    ("dashboard", "📊", "Dashboard",       "Overview & analytics"),
    ("upload",    "📤", "Upload Invoice",   "Process new invoices"),
    ("records",   "📋", "Records",          "Browse all invoices"),
    ("itc",       "💰", "ITC Forecaster",   "Tax credit tracking"),
    ("forensic",  "🔬", "Forensic Guard",   "Duplicate detection"),
    ("profile",   "👤", "Profile",          "Account settings"),
]

def render_sidebar():
    with st.sidebar:
        # Brand
        st.markdown("""
        <div class="sb-brand">
            <div class="sb-brand-icon">🧾</div>
            <div>
                <div class="sb-brand-name">GST Intel</div>
                <div class="sb-brand-tag">INVOICE INTELLIGENCE PLATFORM</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # User card
        initials   = get_user_initials()
        user_email = st.session_state.get("user", "")
        username   = user_email.split("@")[0].replace(".", " ").title()
        st.markdown(f"""
        <div class="sb-user">
            <div class="sb-avatar">{initials}</div>
            <div style="overflow:hidden; flex:1;">
                <div class="sb-username">{username}</div>
                <div class="sb-usertag">
                    <span class="sb-online"></span>Active
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Navigation
        st.markdown('<div class="sb-nav-label">Navigation</div>', unsafe_allow_html=True)
        current = st.session_state.get("page", "dashboard")

        for key, icon, label, sub in PAGES:
            active_cls = "active" if current == key else ""
            st.markdown(f"""
            <div class="sb-nav-item {active_cls}">
                <span class="sb-nav-icon">{icon}</span>
                <div>
                    <div class="sb-nav-text {active_cls}">{label}</div>
                    <div class="sb-nav-sub">{sub}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(label, key=f"nav_{key}", use_container_width=True, help=sub):
                st.session_state["page"] = key
                st.rerun()
            # Hide native button — HTML above is the visual
            st.markdown("""
            <style>
            [data-testid="stSidebar"] .stButton > button {
                opacity: 0 !important; height: 0 !important;
                padding: 0 !important; margin: -0.6rem 0 0.15rem 0 !important;
                pointer-events: all !important; position: relative !important;
                z-index: 10 !important;
            }
            </style>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
        st.markdown("---")

        if st.button("🚪  Sign Out", use_container_width=True, key="sidebar_logout"):
            logout()

        st.markdown('<div class="sb-version">GST Intelligence v2.0 · Render API</div>',
                    unsafe_allow_html=True)