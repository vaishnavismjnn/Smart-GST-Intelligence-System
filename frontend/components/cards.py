# --- file: components/cards.py ---
import streamlit as st
from utils.formatters import fmt_inr, fmt_bool_badge, short_id, fmt_date

def kpi_card(icon, label, value, sub="", col=None):
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

def render_kpi_strip(records: list):
    processed = [r for r in records if r.get("status") == "processed"]
    total_gst  = sum(r.get("GST_AMOUNT", 0) or 0 for r in processed)
    valid_gst  = sum(1 for r in processed if r.get("validation", {}).get("gst_valid") is True)
    val_rate   = f"{(valid_gst / len(processed) * 100):.0f}%" if processed else "—"

    cols = st.columns(4, gap="medium")
    kpi_card("🧾", "Total Invoices",  str(len(records)),     "All records",    cols[0])
    kpi_card("💰", "Total GST",       fmt_inr(total_gst),    "Extracted",      cols[1])
    kpi_card("✅", "Validation Rate", val_rate,               "GSTIN valid",    cols[2])
    kpi_card("⚙️", "Processed",       str(len(processed)),   "Success",        cols[3])

def result_card(result: dict):
    extracted  = result.get("extracted", {})
    validation = extracted.get("validation", {})
    gst_valid  = validation.get("gst_valid", False)
    amounts_ok = validation.get("amounts_match", False)

    st.markdown('<div class="section-title">Extracted Invoice Data</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Identity</div>', unsafe_allow_html=True)
        fields = [
            ("🏢 Merchant",     extracted.get("MERCHANT", "—")),
            ("🔢 GSTIN",        extracted.get("GSTIN", "—")),
            ("🧾 Invoice No.",  extracted.get("INVOICE_NO", "—")),
            ("📅 Invoice Date", fmt_date(extracted.get("INVOICE_DATE"))),
        ]
        for label, val in fields:
            st.markdown(f"""
            <div class="detail-row">
                <span class="detail-label">{label}</span>
                <span class="detail-value mono">{val}</span>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="margin-top:1rem; display:flex; gap:0.5rem; align-items:center;">
            <span style="color:#A0AEC0; font-size:0.78rem;">GSTIN Status:</span>
            {fmt_bool_badge(gst_valid, "✓ Valid", "✗ Invalid")}
        </div>
        </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Financials</div>', unsafe_allow_html=True)
        amounts = [
            ("💵 Total Amount",   fmt_inr(extracted.get("TOTAL_AMOUNT"))),
            ("📋 Taxable Amount", fmt_inr(extracted.get("TAXABLE_AMOUNT"))),
            ("🏛️ GST Amount",    fmt_inr(extracted.get("GST_AMOUNT"))),
        ]
        for label, val in amounts:
            st.markdown(f"""
            <div class="detail-row">
                <span class="detail-label">{label}</span>
                <span class="detail-value" style="color:#00D4AA; font-weight:700;">{val}</span>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="margin-top:1rem; display:flex; gap:0.5rem; align-items:center;">
            <span style="color:#A0AEC0; font-size:0.78rem;">Amount Check:</span>
            {fmt_bool_badge(amounts_ok, "✓ Match", "✗ Mismatch")}
        </div>
        </div>""", unsafe_allow_html=True)

    # Record ID strip
    st.markdown(f"""
    <div style="margin-top:1rem; padding:0.85rem 1.25rem;
                background:rgba(0,212,170,0.05);
                border:1px solid rgba(0,212,170,0.15);
                border-radius:12px;
                display:flex; justify-content:space-between; align-items:center;">
        <span style="color:#A0AEC0; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.08em;">
            MongoDB Record ID
        </span>
        <span style="color:#00D4AA; font-weight:600; font-family:'DM Mono',monospace; font-size:0.82rem;">
            {result.get('record_id', '—')}
        </span>
    </div>
    """, unsafe_allow_html=True)

def activity_item(record: dict):
    merchant = record.get("MERCHANT", "Unknown Merchant")
    amount   = fmt_inr(record.get("TOTAL_AMOUNT"))
    gst_ok   = record.get("validation", {}).get("gst_valid", False)
    rec_id   = short_id(record.get("_id", ""))
    badge    = fmt_bool_badge(gst_ok, "Valid", "Invalid")
    gstin    = record.get("GSTIN", "—")

    st.markdown(f"""
    <div class="activity-item">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:0.75rem;">
                <div style="width:36px; height:36px; border-radius:10px;
                            background:rgba(0,212,170,0.1);
                            border:1px solid rgba(0,212,170,0.2);
                            display:flex; align-items:center; justify-content:center;
                            font-size:1rem; flex-shrink:0;">🧾</div>
                <div>
                    <div style="font-weight:600; font-size:0.88rem; color:#EDF2F7;">
                        {merchant}
                    </div>
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