# --- file: pages/login.py ---
# CSS for this page: .auth-card, .demo-chip, .feature-pill,
#                   .security-strip, .security-item  → all in styles.py

import streamlit as st
from utils.api import login, signup

try:
    from components.illustrations import gst_hero_illustration
except ImportError:
    def gst_hero_illustration(): return ""

def show():
    # Floating orb animation — these are decorative position:fixed overlays,
    # kept here because they are page-specific DOM elements, not reusable classes.
    st.markdown("""
    <style>
    @keyframes float-orb {
        0%, 100% { transform: translateY(0px) scale(1);     opacity: 0.4; }
        50%       { transform: translateY(-20px) scale(1.05); opacity: 0.65; }
    }
    .orb-1 {
        position:fixed; top:12%; left:8%; width:280px; height:280px;
        background:radial-gradient(circle, rgba(0,168,150,0.08) 0%, transparent 70%);
        border-radius:50%; animation:float-orb 8s ease-in-out infinite; pointer-events:none;
    }
    .orb-2 {
        position:fixed; bottom:18%; right:6%; width:220px; height:220px;
        background:radial-gradient(circle, rgba(0,120,180,0.06) 0%, transparent 70%);
        border-radius:50%; animation:float-orb 10s ease-in-out infinite 2s; pointer-events:none;
    }
    .orb-3 {
        position:fixed; top:55%; left:3%; width:140px; height:140px;
        background:radial-gradient(circle, rgba(212,160,23,0.05) 0%, transparent 70%);
        border-radius:50%; animation:float-orb 12s ease-in-out infinite 4s; pointer-events:none;
    }
    </style>
    <div class="orb-1"></div>
    <div class="orb-2"></div>
    <div class="orb-3"></div>
    """, unsafe_allow_html=True)

    col_hero, col_form = st.columns([1.1, 1], gap="large")

    with col_hero:
        st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
        st.markdown(gst_hero_illustration(), unsafe_allow_html=True)

        st.markdown(f"""
        <div style="margin-top:2rem;">
            <div style="font-size:1.6rem; font-weight:700; color:var(--text);
                        letter-spacing:-0.03em; line-height:1.2;">
                Smart GST Invoice<br>
                <span class="shimmer-text">Intelligence Platform</span>
            </div>
            <div style="color:var(--text2); font-size:0.85rem; margin-top:0.75rem; line-height:1.6;">
                Automate invoice processing, validate GSTIN numbers,
                and gain real-time tax insights — all in one place.
            </div>
            <div style="margin-top:1.25rem;">
                <span class="feature-pill">🔍 OCR Extraction</span>
                <span class="feature-pill">✅ GST Validation</span>
                <span class="feature-pill">☁️ Cloud Storage</span>
                <span class="feature-pill">📊 Analytics</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Stats strip
        st.markdown(f"""
        <div style="display:flex; gap:2rem; margin-top:2rem; padding:1.25rem;
                    background:rgba(0,168,150,0.07); border:1px solid rgba(0,168,150,0.18);
                    border-radius:14px;">
            <div style="text-align:center;">
                <div style="color:var(--accent); font-weight:700; font-size:1.3rem;">99%</div>
                <div style="color:var(--muted); font-size:0.7rem;">OCR Accuracy</div>
            </div>
            <div style="text-align:center;">
                <div style="color:var(--accent); font-weight:700; font-size:1.3rem;">&lt;2s</div>
                <div style="color:var(--muted); font-size:0.7rem;">Processing Time</div>
            </div>
            <div style="text-align:center;">
                <div style="color:var(--accent); font-weight:700; font-size:1.3rem;">100%</div>
                <div style="color:var(--muted); font-size:0.7rem;">GSTIN Verified</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_form:
        st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:2rem;">
            <div style="width:44px; height:44px; border-radius:12px;
                        background:linear-gradient(135deg,#00A896,#007A6E);
                        display:flex; align-items:center; justify-content:center;
                        font-size:1.3rem; box-shadow:0 6px 20px rgba(0,168,150,0.3);">🧾</div>
            <div>
                <div style="font-weight:700; font-size:1.05rem; color:var(--text);">GST Intelligence</div>
                <div style="color:var(--muted); font-size:0.7rem;">Secure · Fast · Accurate</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="auth-card">', unsafe_allow_html=True)

        tab_login, tab_signup = st.tabs(["  Sign In  ", "  Create Account  "])

        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            email    = st.text_input("Email", placeholder="name@company.com", key="login_email")
            password = st.text_input("Password", type="password", placeholder="••••••••", key="login_pass")

            if st.button("Access Dashboard →", use_container_width=True, type="primary"):
                if not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    with st.spinner("Authenticating..."):
                        status, data = login(email, password)
                    if status == 200:
                        st.session_state["token"] = data.get("access_token")
                        st.session_state["user"]  = email
                        st.session_state["page"]  = "dashboard"
                        st.rerun()
                    else:
                        st.error(f"❌ {data.get('detail', 'Authentication failed.')}")

            st.markdown("""
            <div style="text-align:center; margin-top:1.5rem;">
                <div style="color:var(--muted); font-size:0.7rem; margin-bottom:0.4rem;">
                    Demo credentials
                </div>
                <span class="demo-chip">📧 test@test.com &nbsp;·&nbsp; 🔑 test123</span>
            </div>
            """, unsafe_allow_html=True)

        with tab_signup:
            st.markdown("<br>", unsafe_allow_html=True)
            new_email = st.text_input("Work Email", placeholder="user@company.com", key="signup_email")
            c1, c2 = st.columns(2)
            new_pass  = c1.text_input("Password", type="password", key="signup_pass")
            conf_pass = c2.text_input("Confirm",  type="password", key="signup_conf")

            if st.button("Create Account", use_container_width=True):
                if not new_email or not new_pass:
                    st.error("Fields cannot be empty.")
                elif new_pass != conf_pass:
                    st.error("Passwords do not match.")
                elif len(new_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Registering..."):
                        status, data = signup(new_email, new_pass)
                    if status == 200:
                        st.success("✅ Account created! Switch to Sign In.")
                    else:
                        st.error(f"❌ {data.get('detail', 'Signup failed.')}")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <div class="security-strip">
            <div class="security-item">🔒 JWT Auth</div>
            <div class="security-item">🛡️ BCrypt Hashed</div>
            <div class="security-item">☁️ Render Hosted</div>
        </div>
        """, unsafe_allow_html=True)