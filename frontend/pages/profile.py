# --- file: pages/profile.py ---
# ═══════════════════════════════════════════════════════════════════════════
# PROFILE PAGE
# User avatar, usage statistics, API connection status, password change form,
# and sign-out (danger zone).
# ═══════════════════════════════════════════════════════════════════════════

import streamlit as st
from utils.api import login, get_records, health_check, BASE_URL
from utils.auth import is_authenticated, logout, get_user_initials
from utils.formatters import fmt_inr
from utils.cleaner import clean_amount, deduplicate_records, get_valid_processed


def show() -> None:
    if not is_authenticated():
        st.warning("Please log in.")
        return

    email    = st.session_state.get("user", "")
    initials = get_user_initials()
    username = email.split("@")[0].replace(".", " ").title()

    st.markdown("""
    <div class="page-header">
        <div class="page-title">👤 Profile & Settings</div>
        <div class="page-sub">Manage your account and view platform usage</div>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 2.2], gap="large")

    with col_left:
        # ── Avatar Card ───────────────────────────────────────────────────────
        st.markdown(f"""
        <div class="glass-card glow-anim" style="text-align:center; padding:2rem 1.5rem;">
            <div style="position:relative; display:inline-block; margin-bottom:1rem;">
                <div style="width:84px; height:84px; border-radius:50%;
                            background:linear-gradient(135deg,#00D4AA,#00A896);
                            display:flex; align-items:center; justify-content:center;
                            font-weight:700; color:#060D1F; font-size:1.9rem;
                            box-shadow:0 8px 30px rgba(0,212,170,0.35); position:relative; z-index:1;">
                    {initials}
                </div>
                <div style="position:absolute; inset:-6px; border-radius:50%;
                            border:2px solid rgba(0,212,170,0.3);
                            animation:spin-slow 8s linear infinite;"></div>
            </div>
            <div style="font-weight:700; font-size:1.05rem; color:#EDF2F7;">{username}</div>
            <div style="color:#A0AEC0; font-size:0.78rem; margin:4px 0 1rem 0;">{email}</div>
            <span class="badge-valid">● Active Account</span>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        # ── Usage Statistics ──────────────────────────────────────────────────
        # WHY get_valid_processed FOR GST TOTAL:
        #   The GST total shown here must match what the dashboard shows.
        #   Both use get_valid_processed() so the numbers are identical across pages.
        #
        # WHY DEDUP FOR PROCESSED COUNT:
        #   "Invoices Processed" should count unique invoices that went through
        #   OCR, not the number of upload attempts (which includes duplicates).
        raw_records = get_records()
        records     = [r for r in raw_records if isinstance(r, dict)] if isinstance(raw_records, list) else []

        deduped   = deduplicate_records(records)
        processed = [r for r in deduped if r.get("status") == "processed"]
        valid     = get_valid_processed(records)

        total_gst = sum(clean_amount(r.get("GST_AMOUNT")) for r in valid)
        valid_cnt = len(valid)
        itc_pct   = int(valid_cnt / len(processed) * 100) if processed else 0

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📊 Usage Statistics</div>', unsafe_allow_html=True)

        for icon, label, val, color in [
            ("🧾", "Invoices Processed", str(len(processed)), "#00D4AA"),
            ("📦", "Total Records",       str(len(records)),   "#00D4AA"),
            ("💰", "GST Extracted",       fmt_inr(total_gst),  "#F5C842"),
            ("✅", "Valid GSTINs",        str(valid_cnt),      "#00D4AA"),
        ]:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center;
                        padding:0.65rem 0.4rem; border-bottom:1px solid rgba(255,255,255,0.04);
                        border-radius:6px; transition:background 0.15s;"
                 onmouseover="this.style.background='rgba(0,212,170,0.04)'"
                 onmouseout="this.style.background='transparent'">
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <span>{icon}</span>
                    <span style="color:#A0AEC0; font-size:0.82rem;">{label}</span>
                </div>
                <span style="color:{color}; font-weight:700; font-family:'DM Mono',monospace;">{val}</span>
            </div>""", unsafe_allow_html=True)

        # ITC Compliance Rate:
        # FORMULA: count(valid) / count(deduped_processed) × 100
        # Interpretation: "Of all unique processed invoices, what fraction are
        # ITC-eligible?" A high rate means OCR and GSTIN validation are working well.
        st.markdown(f"""
        <div style="margin-top:1rem; padding:0.85rem; background:rgba(0,212,170,0.04);
                    border:1px solid rgba(0,212,170,0.12); border-radius:10px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;">
                <span style="color:#A0AEC0; font-size:0.72rem;">ITC Compliance Rate</span>
                <span style="color:#00D4AA; font-weight:700; font-size:0.78rem;">{itc_pct}%</span>
            </div>
            <div style="height:5px; background:rgba(0,212,170,0.1); border-radius:4px; overflow:hidden;">
                <div style="height:100%; width:{itc_pct}%;
                            background:linear-gradient(90deg,#00D4AA,#F5C842);
                            border-radius:4px;"></div>
            </div>
        </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        # ── API Connection Status ──────────────────────────────────────────────
        is_live = health_check()
        is_ok   = isinstance(is_live, dict) and is_live.get("status") == "ok"
        sc      = "#00D4AA" if is_ok else "#FF4D6D"
        st.markdown(f"""
        <div class="glass-card border-anim">
            <div class="section-title">🌐 API Connection</div>
            <div style="display:flex; justify-content:space-between; align-items:center;
                        padding:0.5rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">
                <span style="color:#A0AEC0; font-size:0.8rem;">Status</span>
                <span style="color:{sc}; font-weight:700; font-size:0.8rem;">
                    {"🟢 Online" if is_ok else "🔴 Offline"}
                </span>
            </div>
            <div style="margin-top:0.75rem;">
                <div style="color:#4A5568; font-size:0.62rem; text-transform:uppercase;
                            letter-spacing:0.08em;">Endpoint</div>
                <div style="color:#A0AEC0; font-size:0.7rem; font-family:'DM Mono',monospace;
                            margin-top:4px; word-break:break-all;">{BASE_URL}</div>
            </div>
        </div>""", unsafe_allow_html=True)

    with col_right:
        # ── Account Information ────────────────────────────────────────────────
        st.markdown('<div class="glass-card" style="margin-bottom:1rem;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🪪 Account Information</div>', unsafe_allow_html=True)
        for label, val in [
            ("Email Address",  email),
            ("Account Type",   "Standard"),
            ("Authentication", "JWT Bearer Token"),
            ("Data Storage",   "MongoDB Atlas"),
            ("Image Storage",  "Cloudinary CDN"),
            ("Backend Host",   "Render.com"),
        ]:
            st.markdown(f"""
            <div class="detail-row">
                <span class="detail-label">{label}</span>
                <span class="detail-value">{val}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Change Password ────────────────────────────────────────────────────
        st.markdown('<div class="glass-card" style="margin-bottom:1rem;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🔑 Change Password</div>', unsafe_allow_html=True)
        with st.form("change_password_form", clear_on_submit=True):
            current_pass = st.text_input("Current Password", type="password", key="cur_pass")
            c1, c2 = st.columns(2)
            new_pass     = c1.text_input("New Password",    type="password", key="new_pass")
            confirm_pass = c2.text_input("Confirm Password", type="password", key="conf_pass")
            st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Update Password", use_container_width=True)
            if submitted:
                if not current_pass or not new_pass or not confirm_pass:
                    st.error("All fields are required.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                elif len(new_pass) < 6:
                    st.error("Min 6 characters required.")
                else:
                    status, _ = login(email, current_pass)
                    if status == 200:
                        st.warning("⚠️ Password change pending MongoDB auth migration.")
                    else:
                        st.error("Current password is incorrect.")
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Danger Zone ────────────────────────────────────────────────────────
        st.markdown("""
        <div style="background:rgba(255,77,109,0.05); border:1px solid rgba(255,77,109,0.2);
                    border-radius:16px; padding:1.5rem; transition:border-color 0.2s;"
             onmouseover="this.style.borderColor='rgba(255,77,109,0.35)'"
             onmouseout="this.style.borderColor='rgba(255,77,109,0.2)'">
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
                <span style="color:#FF4D6D; font-size:0.72rem; font-weight:700;
                             text-transform:uppercase; letter-spacing:0.12em;">⚠ Danger Zone</span>
            </div>
            <div style="color:#A0AEC0; font-size:0.82rem; margin-bottom:1rem; line-height:1.5;">
                Signing out clears your JWT session. You will need to log in again.
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("🚪  Sign Out", key="profile_logout", use_container_width=True):
            logout()