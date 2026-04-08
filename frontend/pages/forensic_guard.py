# --- file: pages/forensic_guard.py ---
# Feature: Forensic Duplicate & Integrity Guard
# CSS classes: .glass-card, .section-title, .forensic-row-invalid,
#              .duplicate-modal, .fp-chip, .badge-valid, .badge-invalid
# All in styles.py — no new style blocks here.
#
# Contract compliance: Section 3.4 + Section 8
# Fixes applied:
#   1. FIXED: _fingerprint() now uses MD5 hash AND includes GSTIN (Section 8.1)
#   2. FIXED: _integrity_issues() now uses ₹2 tolerance math check (Section 8.3)
#              (was relying solely on backend validation.amounts_match flag)
#   3. ADDED: GSTIN regex validation (Section 8, Section 9.5)
#   4. ADDED: GSTIN invalid records section in the UI

import streamlit as st
import hashlib                                                     # --- ADDED ---
import re                                                          # --- ADDED ---
from utils.api import get_records
from utils.auth import is_authenticated
from utils.formatters import fmt_inr, fmt_bool_badge, short_id

# GSTIN regex pattern (Contract Section 8 + Section 9.5)          # --- ADDED ---
_GSTIN_REGEX = re.compile(                                         # --- ADDED ---
    r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]$"               # --- ADDED ---
)                                                                  # --- ADDED ---


# ── FIXED: Fingerprint using MD5 + GSTIN (Contract Section 8.1) ─
def _fingerprint(record: dict) -> str:
    """
    MD5 hash of MERCHANT|TOTAL_AMOUNT|GSTIN|INVOICE_DATE.
    Contract Section 8.1 requires GSTIN in the fingerprint.
    Previous implementation omitted GSTIN — now fixed.
    """
    # --- FIXED: was merchant|amount|date only, now includes GSTIN per contract ---
    raw = (
        f"{record.get('MERCHANT', '')}|"
        f"{record.get('TOTAL_AMOUNT', 0)}|"
        f"{record.get('GSTIN', '')}|"
        f"{record.get('INVOICE_DATE', '')}"
    )
    return hashlib.md5(raw.encode()).hexdigest()                    # --- FIXED ---


def _detect_duplicates(records: list) -> dict:
    """
    Returns a dict mapping fingerprint → list of record _ids that share it.
    Any fingerprint with >1 entry is a duplicate group.
    """
    seen: dict = {}
    for r in records:
        fp  = _fingerprint(r)
        rid = r.get("_id", "")
        seen.setdefault(fp, []).append(rid)
    return seen


# ── FIXED: Integrity check with ₹2 tolerance (Contract Section 8.3) ─
def _integrity_issues(records: list) -> list:
    """
    Return records where abs((TAXABLE_AMOUNT + GST_AMOUNT) - TOTAL_AMOUNT) >= ₹2.
    Contract Section 8.3: tolerance is ₹2, missing fields = not a fail.
    Previous implementation relied only on validation.amounts_match from backend.
    Now independently computes the math check as the contract specifies.
    """
    issues = []
    for r in records:
        t = r.get("TOTAL_AMOUNT")   or 0
        x = r.get("TAXABLE_AMOUNT") or 0
        g = r.get("GST_AMOUNT")     or 0
        # Only flag if we have all three values (missing = cannot check)
        if t and x and g:                                          # --- FIXED ---
            if abs((x + g) - t) >= 2.0:                           # --- FIXED ---
                issues.append(r)                                   # --- FIXED ---
    return issues


# ── ADDED: GSTIN format validation (Contract Section 8 + 9.5) ───
def _gstin_format_issues(records: list) -> list:
    """
    Return records whose GSTIN field does not match the 15-char Indian GSTIN regex.
    Contract regex: \\d{2}[A-Z]{5}\\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]
    Empty/null GSTIN is treated separately (OCR failure, not format error).
    """
    issues = []
    for r in records:
        gstin = r.get("GSTIN") or ""
        if gstin and not _GSTIN_REGEX.match(gstin.strip()):        # --- ADDED ---
            issues.append(r)                                       # --- ADDED ---
    return issues
# ── END ADDED ────────────────────────────────────────────────────


# ── Chart: Validation status breakdown ─────────────────────────
def _validation_bar(records: list):
    import plotly.graph_objects as go
    valid_gst   = sum(1 for r in records if r.get("validation", {}).get("gst_valid") is True)
    invalid_gst = len(records) - valid_gst
    match_ok    = sum(1 for r in records if r.get("validation", {}).get("amounts_match") is True)
    match_fail  = len(records) - match_ok

    fig = go.Figure(data=[
        go.Bar(name="Valid",   x=["GSTIN", "Amounts"], y=[valid_gst, match_ok],
               marker_color="#00A896", marker_cornerradius=4),
        go.Bar(name="Invalid", x=["GSTIN", "Amounts"], y=[invalid_gst, match_fail],
               marker_color="#D63E58", marker_cornerradius=4),
    ])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        barmode="group", bargap=0.3,
        font=dict(family="DM Sans", color="#2D5873", size=11),
        margin=dict(l=10, r=10, t=35, b=10),
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.95)",
                        font=dict(family="DM Sans", color="#0F2137")),
        title=dict(text="Validation Summary",
                   font=dict(size=13, color="#0F2137"), x=0, xanchor="left"),
        xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#5A8FA8")),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,168,150,0.1)",
                   tickfont=dict(size=9, color="#5A8FA8")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=10)),
    )
    return fig

def show():
    if not is_authenticated():
        st.warning("Please log in.")
        return

    st.markdown("""
    <div class="page-header">
        <div class="page-title">🔬 Forensic Guard</div>
        <div class="page-sub">
            Duplicate invoice detection · Integrity validation · Fingerprint analysis
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(""):
        records = get_records()

    if not records:
        st.info("No records found. Upload invoices to enable forensic analysis.")
        return

    fp_map        = _detect_duplicates(records)
    issues        = _integrity_issues(records)
    gstin_issues  = _gstin_format_issues(records)               # --- ADDED ---

    # ── Alert banners ──────────────────────────────────────
    dup_groups = {fp: ids for fp, ids in fp_map.items() if len(ids) > 1}
    if dup_groups:
        total_dups = sum(len(v) - 1 for v in dup_groups.values())
        st.markdown(f"""
        <div class="duplicate-modal">
            <div style="display:flex; align-items:center; gap:0.75rem;">
                <span style="font-size:1.5rem;">⚠️</span>
                <div>
                    <div style="font-weight:700; color:var(--err); font-size:0.92rem;">
                        {total_dups} Duplicate Invoice(s) Detected
                    </div>
                    <div style="color:var(--text2); font-size:0.78rem; margin-top:2px;">
                        {len(dup_groups)} fingerprint group(s) contain duplicate submissions.
                        Review the table below for details.
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    if issues:
        st.markdown(f"""
        <div style="background:rgba(212,160,23,0.07); border:1px solid rgba(212,160,23,0.25);
                    border-left:4px solid var(--gold); border-radius:12px;
                    padding:0.85rem 1.25rem; margin-bottom:1rem;
                    display:flex; align-items:center; gap:0.75rem;">
            <span style="font-size:1.3rem;">🔢</span>
            <div>
                <div style="font-weight:700; color:var(--warn); font-size:0.88rem;">
                    {len(issues)} Amount Mismatch(es) Found
                </div>
                <div style="color:var(--text2); font-size:0.75rem; margin-top:2px;">
                    These invoices have GST amounts that don't reconcile with taxable + GST = total (±₹2).
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── ADDED: GSTIN format alert banner ─────────────────────
    if gstin_issues:                                               # --- ADDED ---
        st.markdown(f"""
        <div style="background:rgba(255,77,109,0.06); border:1px solid rgba(255,77,109,0.25);
                    border-left:4px solid #FF4D6D; border-radius:12px;
                    padding:0.85rem 1.25rem; margin-bottom:1rem;
                    display:flex; align-items:center; gap:0.75rem;">
            <span style="font-size:1.3rem;">🚫</span>
            <div>
                <div style="font-weight:700; color:#FF4D6D; font-size:0.88rem;">
                    {len(gstin_issues)} Invalid GSTIN Format(s)
                </div>
                <div style="color:var(--text2); font-size:0.75rem; margin-top:2px;">
                    These records have a GSTIN that does not match the required format
                    (e.g. 27AAPFU0939F1ZV). These cannot be used for ITC claims.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    # ── END ADDED ────────────────────────────────────────────

    # ── Summary KPIs ───────────────────────────────────────
    cols = st.columns(5, gap="small")   # --- MODIFIED: was 4, now 5 for GSTIN issues ---
    kpi_data = [
        ("Total Records",    str(len(records)),                                            "📦", "#00A896"),
        ("Duplicate Groups", str(len(dup_groups)),                                         "🔁", "#D63E58" if dup_groups else "#00A896"),
        ("Integrity Issues", str(len(issues)),                                             "⚠️", "#C8860A" if issues else "#00A896"),
        ("GSTIN Format Err", str(len(gstin_issues)),                                       "🚫", "#FF4D6D" if gstin_issues else "#00A896"),  # --- ADDED ---
        ("Clean Records",    str(max(0, len(records) - len(issues) - sum(len(v)-1 for v in dup_groups.values()))), "✅", "#00A896"),
    ]
    for col, (label, val, icon, color) in zip(cols, kpi_data):
        col.markdown(f"""
        <div style="background:var(--card); border:1px solid var(--card-border);
                    border-radius:10px; padding:0.85rem;
                    transition:transform 0.2s, box-shadow 0.2s;
                    box-shadow:0 2px 8px rgba(0,100,130,0.07);"
             onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 20px rgba(0,100,130,0.12)'"
             onmouseout="this.style.transform='translateY(0)';this.style.boxShadow='0 2px 8px rgba(0,100,130,0.07)'">
            <div style="font-size:0.85rem; margin-bottom:0.3rem;">{icon}</div>
            <div style="color:var(--muted); font-size:0.65rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin-bottom:0.2rem;">{label}</div>
            <div style="color:{color}; font-weight:700; font-size:1.2rem;
                        font-family:'DM Mono',monospace;">{val}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Chart + Fingerprint Legend ─────────────────────────
    col_chart, col_fp = st.columns([1.4, 1], gap="large")

    with col_chart:
        st.markdown('<div class="glass-card" style="padding:1.25rem 1.5rem;">', unsafe_allow_html=True)
        st.plotly_chart(_validation_bar(records), use_container_width=True,
                        config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with col_fp:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🔑 How Fingerprinting Works</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        <div style="color:var(--text2); font-size:0.8rem; line-height:1.6; margin-bottom:1rem;">
            Each invoice gets a unique <b>MD5 fingerprint</b> derived from four fields.
            If two invoices share the same fingerprint, they are flagged as duplicates.
        </div>
        """, unsafe_allow_html=True)

        # --- MODIFIED: now 4 fields including GSTIN per Section 8.1 ---
        for icon, field, desc in [
            ("🏢", "MERCHANT",      "Who issued the invoice"),
            ("💵", "TOTAL_AMOUNT",  "The final billed amount"),
            ("🔢", "GSTIN",         "Supplier tax ID"),          # --- ADDED ---
            ("📅", "INVOICE_DATE",  "When it was issued"),
        ]:
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:0.75rem;
                        padding:0.55rem 0; border-bottom:1px solid var(--border);">
                <span style="font-size:1rem; flex-shrink:0;">{icon}</span>
                <div>
                    <div style="font-family:'DM Mono',monospace; font-size:0.75rem;
                                color:var(--accent); font-weight:600;">{field}</div>
                    <div style="font-size:0.7rem; color:var(--muted);">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("""
        <div style="margin-top:1rem; padding:0.75rem; background:rgba(0,168,150,0.06);
                    border:1px solid rgba(0,168,150,0.15); border-radius:10px;">
            <div style="font-size:0.68rem; color:var(--muted); margin-bottom:0.3rem;">
                Algorithm: MD5(MERCHANT|AMOUNT|GSTIN|DATE)
            </div>
            <span class="fp-chip">a3f8c2...d91e</span>
        </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Forensic Table ─────────────────────────────────────
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔬 Forensic Invoice Table</div>', unsafe_allow_html=True)

    search = st.text_input("Filter by Merchant / GSTIN", placeholder="Search...",
                           key="forensic_search", label_visibility="collapsed")

    COLS = "0.5fr 1.6fr 1.4fr 0.9fr 1.1fr 0.75fr 0.75fr 1fr 0.9fr"
    st.markdown(f"""
    <div class="tbl-header" style="grid-template-columns:{COLS};">
        <div>ID</div><div>Merchant</div><div>GSTIN</div><div>Date</div>
        <div>Total</div><div>GSTIN ✓</div><div>Amt ✓</div>
        <div>Fingerprint</div><div>Status</div>
    </div>
    """, unsafe_allow_html=True)

    # Build a quick lookup set of IDs with GSTIN format issues     # --- ADDED ---
    gstin_issue_ids = {r.get("_id") for r in gstin_issues}         # --- ADDED ---

    shown = 0
    for r in records:
        merchant = r.get("MERCHANT", "—")
        gstin    = r.get("GSTIN", "—")

        if search and search.lower() not in merchant.lower() and search.lower() not in gstin.lower():
            continue

        shown += 1
        v        = r.get("validation", {}) or {}
        rid      = short_id(r.get("_id", ""))
        fp       = _fingerprint(r)
        is_dup   = len(fp_map.get(fp, [])) > 1
        # ── FIXED: use the ₹2 math check, not solely amounts_match flag ──
        t = r.get("TOTAL_AMOUNT") or 0
        x = r.get("TAXABLE_AMOUNT") or 0
        g = r.get("GST_AMOUNT") or 0
        bad_amt  = (t and x and g and abs((x + g) - t) >= 2.0)    # --- FIXED ---
        gst_ok   = v.get("gst_valid", False)
        fmt_bad  = r.get("_id") in gstin_issue_ids                 # --- ADDED ---

        gb = fmt_bool_badge(gst_ok, "✓", "✗")
        ab = fmt_bool_badge(not bad_amt, "✓", "✗")

        row_extra = 'class="forensic-row-invalid"' if bad_amt else ""
        row_bg    = "rgba(255,255,255,0.05)" if not bad_amt else ""

        # Priority: duplicate > mismatch > invalid GSTIN format > invalid GST > clean
        if is_dup:
            status_html = '<span class="badge-invalid">Duplicate</span>'
        elif bad_amt:
            status_html = '<span class="badge-warn">Mismatch</span>'
        elif fmt_bad:                                              # --- ADDED ---
            status_html = '<span class="badge-invalid">Bad GSTIN</span>'  # --- ADDED ---
        elif not gst_ok:
            status_html = '<span class="badge-invalid">Invalid GST</span>'
        else:
            status_html = '<span class="badge-valid">Clean</span>'

        fp_short = fp[:14] + "…" if len(fp) > 14 else fp          # --- MODIFIED: MD5 is longer ---

        st.markdown(f"""
        <div {row_extra} class="tbl-row"
             style="grid-template-columns:{COLS}; background:{row_bg};"
             onmouseover="this.style.background='rgba(0,168,150,0.05)'"
             onmouseout="this.style.background='{row_bg}'">
            <div style="color:var(--muted); font-family:'DM Mono',monospace;
                        font-size:0.7rem;">{rid}</div>
            <div style="color:var(--text); font-weight:600; font-size:0.82rem;">{merchant}</div>
            <div style="color:var(--text2); font-size:0.68rem; font-family:'DM Mono',monospace;">{gstin}</div>
            <div style="color:var(--text2); font-size:0.75rem;">{r.get('INVOICE_DATE','—')}</div>
            <div style="color:var(--accent); font-weight:700; font-size:0.82rem;
                        font-family:'DM Mono',monospace;">{fmt_inr(r.get('TOTAL_AMOUNT'))}</div>
            <div>{gb}</div>
            <div>{ab}</div>
            <div style="font-family:'DM Mono',monospace; font-size:0.62rem;
                        color:var(--muted);" title="{fp}">{fp_short}</div>
            <div>{status_html}</div>
        </div>
        """, unsafe_allow_html=True)

        if is_dup:
            dup_ids = [i for i in fp_map[fp] if i != r.get("_id","")]
            with st.expander(f"  ⚠️ Duplicate detail — {merchant} {rid}"):
                st.markdown(f"""
                <div class="duplicate-modal">
                    <div style="font-weight:700; color:var(--err); margin-bottom:0.5rem;">
                        Duplicate Invoice Detected
                    </div>
                    <div style="color:var(--text2); font-size:0.82rem; margin-bottom:0.75rem;">
                        This record matches the following Record ID(s):
                    </div>
                    {''.join(f'<span class="fp-chip" style="margin:2px;">#{i[-6:].upper()}</span>' for i in dup_ids)}
                    <div style="margin-top:0.75rem; color:var(--muted); font-size:0.72rem;">
                        MD5 Fingerprint: <span class="fp-chip">{fp}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    if shown == 0:
        st.markdown("""
        <div style="text-align:center; padding:2rem; color:var(--muted);">
            <div>No records match your search.</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center; color:var(--muted); font-size:0.72rem; margin-top:0.75rem;">
        {shown} records displayed · {len(dup_groups)} duplicate group(s) ·
        {len(issues)} integrity issue(s) · {len(gstin_issues)} GSTIN format error(s)
    </div>
    </div>""", unsafe_allow_html=True)