# --- file: components/cards.py ---
# ═══════════════════════════════════════════════════════════════════════════
# CARDS — reusable UI components shared across dashboard and upload pages.
#
# WHY INLINE HELPERS:
#   cards.py is imported by dashboard.py. dashboard.py imports from cleaner.py.
#   If cards.py also imported from cleaner.py, the import chain would be:
#     dashboard → cards → cleaner (fine)
#   This is actually safe, but we keep _safe_num and _dedup as thin wrappers
#   around clean_amount / deduplicate_records from cleaner.py so there is
#   exactly one implementation — no risk of the two diverging.
# ═══════════════════════════════════════════════════════════════════════════

import streamlit as st
from utils.formatters import fmt_inr, fmt_bool_badge, short_id, fmt_date
from utils.cleaner import clean_amount, deduplicate_records, get_valid_processed


# ── kpi_card ─────────────────────────────────────────────────────────────────
# Renders a single KPI tile. Used by render_kpi_strip (4 tiles across the top
# of the dashboard). Pure HTML so the layout doesn't depend on st.metric's
# limited styling.
def kpi_card(icon: str, label: str, value: str, sub: str = "", col=None) -> None:
    html = f"""
    <div class="kpi-card">
        <span class="kpi-icon">{icon}</span>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {"" if not sub else f'<div class="kpi-sub">{sub}</div>'}
    </div>
    """
    target = col if col else st
    target.markdown(html, unsafe_allow_html=True)


# ── render_kpi_strip ─────────────────────────────────────────────────────────
# Renders the four KPI tiles at the top of the dashboard.
#
# TILE 1 — Total Invoices: raw count of all records (including invalid/uploaded)
#   so the user can see the full scope of what's in the database.
#
# TILE 2 — Total GST:
#   FORMULA: Σ GST_AMOUNT for valid processed invoices only.
#   WHY: This is the ITC-eligible GST pool. Including invalid invoices would
#   misrepresent how much GST can actually be reclaimed.
#
# TILE 3 — Validation Rate:
#   FORMULA: count(valid) / count(deduped_processed) × 100
#   Denominator is DEDUPED processed (not raw uploads) so duplicate submissions
#   don't artificially lower the rate. Both gst_valid AND amounts_match must
#   be True — one flag alone is not sufficient for ITC eligibility.
#
# TILE 4 — Processed:
#   Count of unique (deduped) processed invoices. Shows operational throughput.
def render_kpi_strip(records: list) -> None:
    valid           = get_valid_processed(records)
    all_proc        = [r for r in records if isinstance(r, dict) and r.get("status") == "processed"]
    all_proc_deduped = deduplicate_records(all_proc)

    total_gst = sum(clean_amount(r.get("GST_AMOUNT")) for r in valid)
    val_rate  = (
        f"{(len(valid) / len(all_proc_deduped) * 100):.0f}%"
        if all_proc_deduped else "—"
    )

    cols = st.columns(4, gap="medium")
    kpi_card("🧾", "Total Invoices",  str(len(records)),           "All records",    cols[0])
    kpi_card("💰", "Total GST",       fmt_inr(total_gst),          "Valid invoices", cols[1])
    kpi_card("✅", "Validation Rate", val_rate,                     "GSTIN + Amt ✓", cols[2])
    kpi_card("⚙️", "Processed",       str(len(all_proc_deduped)), "Unique",         cols[3])


# ── result_card ───────────────────────────────────────────────────────────────
# Shown on the upload page after a successful invoice processing.
# Displays the extracted fields side by side in two glass-card columns:
#   Left  — Identity fields (merchant, GSTIN, invoice number, date)
#   Right — Financial fields (total, taxable, GST amounts)
# Both include a coloured badge showing validation status.
def result_card(result: dict) -> None:
    extracted  = result.get("extracted", {})
    validation = extracted.get("validation", {}) or {}
    gst_valid  = validation.get("gst_valid",  False)
    amounts_ok = validation.get("amounts_match", False)

    st.markdown('<div class="section-title">Extracted Invoice Data</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Identity</div>', unsafe_allow_html=True)
        for label, val in [
            ("🏢 Merchant",    extracted.get("MERCHANT", "—")),
            ("🔢 GSTIN",       extracted.get("GSTIN", "—")),
            ("🧾 Invoice No.", extracted.get("INVOICE_NO", "—")),
            ("📅 Date",        fmt_date(extracted.get("INVOICE_DATE"))),
        ]:
            st.markdown(f"""
            <div class="detail-row">
                <span class="detail-label">{label}</span>
                <span class="detail-value mono">{val}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="margin-top:1rem; display:flex; gap:0.5rem; align-items:center;">
            <span style="color:#A0AEC0; font-size:0.78rem;">GSTIN Status:</span>
            {fmt_bool_badge(gst_valid, "✓ Valid", "✗ Invalid")}
        </div></div>""", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Financials</div>', unsafe_allow_html=True)
        for label, val in [
            ("💵 Total Amount",   fmt_inr(extracted.get("TOTAL_AMOUNT"))),
            ("📋 Taxable Amount", fmt_inr(extracted.get("TAXABLE_AMOUNT"))),
            ("🏛️ GST Amount",    fmt_inr(extracted.get("GST_AMOUNT"))),
        ]:
            st.markdown(f"""
            <div class="detail-row">
                <span class="detail-label">{label}</span>
                <span class="detail-value" style="color:#00D4AA; font-weight:700;">{val}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="margin-top:1rem; display:flex; gap:0.5rem; align-items:center;">
            <span style="color:#A0AEC0; font-size:0.78rem;">Amount Check:</span>
            {fmt_bool_badge(amounts_ok, "✓ Match", "✗ Mismatch")}
        </div></div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="margin-top:1rem; padding:0.85rem 1.25rem;
                background:rgba(0,212,170,0.05); border:1px solid rgba(0,212,170,0.15);
                border-radius:12px; display:flex; justify-content:space-between; align-items:center;">
        <span style="color:#A0AEC0; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.08em;">
            MongoDB Record ID
        </span>
        <span style="color:#00D4AA; font-weight:600; font-family:'DM Mono',monospace; font-size:0.82rem;">
            {result.get("record_id", "—")}
        </span>
    </div>
    """, unsafe_allow_html=True)


# ── activity_item ─────────────────────────────────────────────────────────────
# Single row in the Recent Activity feed on the dashboard.
# Shows: invoice icon | merchant name + GSTIN·ID | gst_valid badge | total amount.
# Purely display — no financial calculations here.
def activity_item(record: dict) -> None:
    merchant = record.get("MERCHANT", "Unknown Merchant")
    amount   = fmt_inr(record.get("TOTAL_AMOUNT"))
    gst_ok   = (record.get("validation") or {}).get("gst_valid", False)
    rec_id   = short_id(record.get("_id", ""))
    badge    = fmt_bool_badge(gst_ok, "Valid", "Invalid")
    gstin    = record.get("GSTIN", "—")

    st.markdown(f"""
    <div class="activity-item">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:0.75rem;">
                <div style="width:36px; height:36px; border-radius:10px;
                            background:rgba(0,212,170,0.1); border:1px solid rgba(0,212,170,0.2);
                            display:flex; align-items:center; justify-content:center;
                            font-size:1rem; flex-shrink:0;">🧾</div>
                <div>
                    <div style="font-weight:600; font-size:0.88rem; color:#EDF2F7;">{merchant}</div>
                    <div style="font-size:0.72rem; color:#4A5568; font-family:'DM Mono',monospace;">
                        {gstin} · {rec_id}
                    </div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:0.75rem; flex-shrink:0;">
                {badge}
                <span style="color:#00D4AA; font-weight:700; font-size:0.92rem;">{amount}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)