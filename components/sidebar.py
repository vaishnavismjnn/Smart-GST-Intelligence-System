# --- file: components/sidebar.py ---
# All sidebar COMPONENT classes (sb-brand, sb-nav-item, etc.) live in styles.py.
# The one <style> block here handles BUTTON CHROME only — it is intentionally
# kept here because it must load inside st.sidebar's render context.

import streamlit as st
from utils.auth import logout, get_user_initials

PAGES = [
    ("dashboard", "📊", "Dashboard",      "Overview & analytics"),
    ("upload",    "📤", "Upload Invoice",  "Process new invoices"),
    ("records",   "📋", "Records",         "Browse all invoices"),
    ("itc",       "💰", "ITC Forecaster",  "Tax credit tracking"),
    ("forensic",  "🔬", "Forensic Guard",  "Duplicate detection"),
    ("profile",   "👤", "Profile",         "Account settings"),
]

def render_sidebar():
    with st.sidebar:

        # ── Brand ─────────────────────────────────────────────────
        st.markdown("""
        <div class="sb-brand">
            <div class="sb-brand-icon">🧾</div>
            <div>
                <div class="sb-brand-name">GST Intel</div>
                <div class="sb-brand-tag">Invoice Intelligence Platform</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── User card ──────────────────────────────────────────────
        initials   = get_user_initials()
        user_email = st.session_state.get("user", "")
        username   = user_email.split("@")[0].replace(".", " ").title()
        st.markdown(f"""
        <div class="sb-user">
            <div class="sb-avatar">{initials}</div>
            <div style="overflow:hidden; flex:1; min-width:0;">
                <div class="sb-username">{username}</div>
                <div class="sb-usertag">
                    <span class="sb-online"></span>Active
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Navigation ─────────────────────────────────────────────
        st.markdown('<div class="sb-nav-label">Navigation</div>', unsafe_allow_html=True)

        current = st.session_state.get("page", "dashboard")

        for key, icon, label, sub in PAGES:
            active_cls = "active" if current == key else ""

            # 1. Visual row — pure HTML, no interactivity
            st.markdown(f"""
            <div class="sb-nav-item {active_cls}">
                <span class="sb-nav-icon">{icon}</span>
                <div style="min-width:0;">
                    <div class="sb-nav-text {active_cls}">{label}</div>
                    <div class="sb-nav-sub">{sub}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 2. Invisible native button — collapsed to zero height so it
            #    sits flush below the markdown row above and intercepts clicks.
            #    (position:absolute is intentionally avoided — it escapes the
            #    stButton wrapper which has position:static, causing the hit
            #    area to land in the wrong place.)
            if st.button(label, key=f"nav_{key}", use_container_width=True, help=sub):
                st.session_state["page"] = key
                st.rerun()

        # ── Spacer + divider ───────────────────────────────────────
        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        st.markdown("---")

        # ── Sign Out ───────────────────────────────────────────────
        if st.button("🚪  Sign Out", use_container_width=True, key="sidebar_logout"):
            logout()

        # ── Version stamp ──────────────────────────────────────────
        st.markdown(
            '<div class="sb-version">GST Intelligence v2.0 · Render API</div>',
            unsafe_allow_html=True
        )

        # ── Button chrome overrides ────────────────────────────────
        # Injected once, at the bottom, after all buttons are rendered.
        #
        # NAV BUTTONS  → opacity:0 + height:0 + negative margin so the
        #                 invisible button overlaps the markdown row above it.
        # LOGOUT BUTTON → :last-of-type restores full visibility.
        #                 We cannot use button[key="sidebar_logout"] because
        #                 `key` is a React prop, NOT an HTML attribute — the
        #                 browser never sees it, so that selector matches nothing.
        st.markdown("""
        <style>
        /* ── All sidebar buttons: invisible, zero-height, still clickable ── */
        [data-testid="stSidebar"] .stButton {
            margin: 0 !important;
            padding: 0 !important;
        }
        [data-testid="stSidebar"] .stButton > button {
            opacity: 0 !important;
            height: 0px !important;
            min-height: 0 !important;
            padding: 0 !important;
            margin: -0.55rem 0 0.1rem 0 !important;
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
            position: relative !important;
            pointer-events: all !important;
            z-index: 10 !important;
        }

        /* ── Logout button: last .stButton in sidebar — fully restored ── */
        [data-testid="stSidebar"] .stButton:last-of-type {
            margin: 0 !important;
            padding: 0 !important;
        }
        [data-testid="stSidebar"] .stButton:last-of-type > button {
            opacity: 1 !important;
            height: auto !important;
            min-height: unset !important;
            padding: 0.55rem 1.25rem !important;
            margin: 0 !important;
            background: rgba(248,81,73,0.08) !important;
            color: #F85149 !important;
            border: 1px solid rgba(248,81,73,0.22) !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
            box-shadow: none !important;
            position: relative !important;
            pointer-events: all !important;
            z-index: auto !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] .stButton:last-of-type > button:hover {
            background: rgba(248,81,73,0.16) !important;
            border-color: rgba(248,81,73,0.45) !important;
            transform: none !important;
            box-shadow: 0 0 12px rgba(248,81,73,0.15) !important;
        }
        </style>
        """, unsafe_allow_html=True)