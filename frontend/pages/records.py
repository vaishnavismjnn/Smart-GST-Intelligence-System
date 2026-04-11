# --- file: pages/records.py ---
# ═══════════════════════════════════════════════════════════════════════════
# RECORDS PAGE
# Full paginated invoice browser with search, filter, CSV/Excel export,
# and per-record expandable detail cards with Cloudinary image viewer.
# ═══════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import io
from utils.api import get_records
from utils.auth import is_authenticated
from utils.formatters import fmt_inr, fmt_bool_badge, short_id, fmt_date
from utils.cleaner import normalize_record, clean_amount, deduplicate_records
from components.illustrations import empty_records_illustration, render_illustration

PAGE_SIZE = 10


# ── _build_df ─────────────────────────────────────────────────────────────────
# WHY normalize_record HERE:
#   normalize_record converts raw MongoDB docs to clean typed Python dicts
#   before they enter the DataFrame. This means every amount column is a
#   Python float (never a string) so pandas sort/filter operations work
#   correctly and fmt_inr never receives a string it can't format.
#   The original _raw is stored in the DataFrame so the expander detail
#   card can show all fields including ones not in the main table.
def _build_df(records: list) -> pd.DataFrame:
    rows = []
    for r in records:
        r = normalize_record(r)
        v = r.get("validation") or {}
        rows.append({
            "ID":        short_id(r.get("_id", "")),
            "Merchant":  r.get("MERCHANT"),
            "GSTIN":     r.get("GSTIN"),
            "Date":      fmt_date(r.get("INVOICE_DATE")),
            "Total":     r.get("TOTAL_AMOUNT"),    # float after normalize_record
            "GST":       r.get("GST_AMOUNT"),       # float after normalize_record
            "GST Valid": v.get("gst_valid"),
            "Amt Match": v.get("amounts_match"),
            "Status":    r.get("status"),
            "_raw":      r,                         # full record for expander
        })
    return pd.DataFrame(rows)


# ── show ──────────────────────────────────────────────────────────────────────
def show() -> None:
    if not is_authenticated():
        st.warning("Please log in.")
        return

    st.markdown("""
    <div class="page-header">
        <div class="page-title">📋 Invoice Records</div>
        <div class="page-sub">Browse, search, filter and export all processed GST invoices</div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(""):
        records = get_records()

    # Ensure we have a list of dicts
    if not isinstance(records, list):
        records = []
    records = [r for r in records if isinstance(r, dict)]

    if not records:
        st.markdown('<div class="glass-card" style="text-align:center; padding:5rem 2rem;">',
                    unsafe_allow_html=True)
        render_illustration(empty_records_illustration())
        st.markdown("""
        <div style="margin-top:1rem;">
            <div style="font-weight:700; color:#EDF2F7; font-size:1rem; margin-bottom:0.4rem;">
                No records yet</div>
            <div style="color:#4A5568; font-size:0.85rem;">
                Upload and process invoices to see them listed here</div>
        </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    df = _build_df(records)

    # ── Quick Stats ───────────────────────────────────────────────────────────
    # Deduplicate before aggregating — totals must not double-count duplicates.
    # We show totals across ALL records (not just valid) so the user can see
    # the full picture before applying filters.
    deduped = deduplicate_records(records)
    total_val = sum(clean_amount(r.get("TOTAL_AMOUNT")) for r in deduped)
    total_gst = sum(clean_amount(r.get("GST_AMOUNT"))   for r in deduped)
    valid_cnt = sum(
        1 for r in deduped
        if (r.get("validation") or {}).get("gst_valid") is True
    )

    qs_cols = st.columns(4, gap="small")
    for col, (label, val, icon) in zip(qs_cols, [
        ("Total Records", str(len(deduped)),                    "📦"),
        ("Total Value",   fmt_inr(total_val),                   "💰"),
        ("Total GST",     fmt_inr(total_gst),                   "🏛️"),
        ("Valid GSTINs",  f"{valid_cnt}/{len(deduped)}",         "✅"),
    ]):
        col.markdown(f"""
        <div style="background:rgba(0,212,170,0.05); border:1px solid rgba(0,212,170,0.12);
                    border-radius:10px; padding:0.7rem 0.85rem;
                    transition:border-color 0.2s, transform 0.2s;"
             onmouseover="this.style.borderColor='rgba(0,212,170,0.3)';this.style.transform='translateY(-2px)'"
             onmouseout="this.style.borderColor='rgba(0,212,170,0.12)';this.style.transform='translateY(0)'">
            <div style="display:flex; align-items:center; gap:0.4rem; margin-bottom:0.25rem;">
                <span style="font-size:0.85rem;">{icon}</span>
                <span style="color:#4A5568; font-size:0.65rem; text-transform:uppercase;
                             letter-spacing:0.08em;">{label}</span>
            </div>
            <div style="color:#00D4AA; font-weight:700; font-size:0.95rem;
                        font-family:'DM Mono',monospace;">{val}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown('<div class="glass-card" style="margin-bottom:1rem; padding:1rem 1.25rem;">',
                unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔍 Search & Filter</div>', unsafe_allow_html=True)

    fc1, fc2, fc3, fc4 = st.columns([2.5, 1.5, 1.5, 1])
    with fc1:
        search = st.text_input("Search", placeholder="Merchant or GSTIN...",
                               key="rec_search", label_visibility="collapsed")
    with fc2:
        status_f = st.selectbox("Status", ["All", "processed", "uploaded"],
                                key="rec_status", label_visibility="collapsed")
    with fc3:
        gst_f = st.selectbox("Validity", ["All Validity", "Valid", "Invalid"],
                             key="rec_gst", label_visibility="collapsed")
    with fc4:
        amt_f = st.selectbox("Amounts", ["All", "Match", "Mismatch"],
                             key="rec_amt", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    # Apply filters
    filtered = df.copy()
    if search:
        mask = (
            filtered["Merchant"].str.contains(search, case=False, na=False) |
            filtered["GSTIN"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]
    if status_f != "All":
        filtered = filtered[filtered["Status"] == status_f]
    if gst_f == "Valid":
        filtered = filtered[filtered["GST Valid"] == True]
    elif gst_f == "Invalid":
        filtered = filtered[filtered["GST Valid"] == False]
    if amt_f == "Match":
        filtered = filtered[filtered["Amt Match"] == True]
    elif amt_f == "Mismatch":
        filtered = filtered[filtered["Amt Match"] == False]

    filtered_raw = [row["_raw"] for _, row in filtered.iterrows()] if not filtered.empty else []

    # ── Results Bar + Export Buttons ──────────────────────────────────────────
    rc1, rc2, rc3 = st.columns([2.5, 1, 1])
    with rc1:
        filtered_val = fmt_inr(sum(
            clean_amount(row["_raw"].get("TOTAL_AMOUNT"))
            for _, row in filtered.iterrows()
        ))
        st.markdown(f"""
        <div style="padding:0.4rem 0; color:#A0AEC0; font-size:0.82rem;">
            Showing <b style="color:#00D4AA;">{len(filtered)}</b> records ·
            Total value: <b style="color:#00D4AA;">{filtered_val}</b>
        </div>""", unsafe_allow_html=True)

    with rc2:
        if not filtered.empty:
            exp_df = filtered.drop(columns=["_raw"], errors="ignore").copy()
            exp_df["Total"] = exp_df["Total"].apply(fmt_inr)
            exp_df["GST"]   = exp_df["GST"].apply(fmt_inr)
            buf = io.StringIO()
            exp_df.to_csv(buf, index=False)
            st.download_button("⬇️ CSV", buf.getvalue(),
                               "gst_records.csv", "text/csv",
                               key="csv_export", use_container_width=True)

    with rc3:
        if filtered_raw:
            try:
                from utils.excel_builder import _build_excel
                is_filtered = (
                    bool(search) or status_f != "All"
                    or gst_f != "All Validity" or amt_f != "All"
                )
                title = ("GST Intelligence — Filtered Export"
                         if is_filtered else "GST Intelligence — All Invoices")
                excel_bytes = _build_excel(filtered_raw, title=title)
                st.download_button(
                    label="📊 Excel",
                    data=excel_bytes,
                    file_name="gst_records.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="excel_export",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Excel error: {e}")

    if filtered.empty:
        st.markdown("""
        <div style="text-align:center; padding:3rem; color:#4A5568;">
            <div style="font-size:2rem; margin-bottom:0.5rem;">🔍</div>
            <div style="font-size:0.88rem;">No records match your current filters</div>
        </div>""", unsafe_allow_html=True)
        return

    # ── Table ─────────────────────────────────────────────────────────────────
    COLS = "0.55fr 1.8fr 1.55fr 0.9fr 1.1fr 1.1fr 0.75fr 0.75fr"
    st.markdown(f"""
    <div class="tbl-header" style="grid-template-columns:{COLS};">
        <div>ID</div><div>Merchant</div><div>GSTIN</div><div>Date</div>
        <div>Total</div><div>GST</div><div>GSTIN ✓</div><div>Amt ✓</div>
    </div>""", unsafe_allow_html=True)

    total_pages = max(1, (len(filtered) - 1) // PAGE_SIZE + 1)
    _, pg_col, _ = st.columns([3, 1, 3])
    with pg_col:
        page_num = st.number_input("", min_value=1, max_value=total_pages,
                                   value=1, step=1, key="rec_page",
                                   label_visibility="collapsed")

    start   = (page_num - 1) * PAGE_SIZE
    page_df = filtered.iloc[start: start + PAGE_SIZE]

    for _, row in page_df.iterrows():
        raw = row.get("_raw", {})
        v   = raw.get("validation", {}) or {}
        gb  = fmt_bool_badge(v.get("gst_valid",    False), "✓", "✗")
        ab  = fmt_bool_badge(v.get("amounts_match", False), "✓", "✗")
        row_bg = "rgba(255,77,109,0.04)" if not v.get("gst_valid") else "var(--card)"

        st.markdown(f"""
        <div class="tbl-row" style="grid-template-columns:{COLS}; background:{row_bg};"
             onmouseover="this.style.background='rgba(0,212,170,0.05)'"
             onmouseout="this.style.background='{row_bg}'">
            <div style="color:#4A5568; font-family:'DM Mono',monospace; font-size:0.72rem;">{row["ID"]}</div>
            <div style="color:#EDF2F7; font-weight:600; font-size:0.83rem;">{row["Merchant"]}</div>
            <div style="color:#A0AEC0; font-size:0.7rem; font-family:'DM Mono',monospace;">{row["GSTIN"]}</div>
            <div style="color:#A0AEC0; font-size:0.78rem;">{row["Date"]}</div>
            <div style="color:#00D4AA; font-weight:700; font-size:0.83rem;
                        font-family:'DM Mono',monospace;">{fmt_inr(row["Total"])}</div>
            <div style="color:#EDF2F7; font-size:0.82rem;">{fmt_inr(row["GST"])}</div>
            <div>{gb}</div>
            <div>{ab}</div>
        </div>""", unsafe_allow_html=True)

        with st.expander(f"  Details — {row['Merchant']}  {row['ID']}", expanded=False):
            d1, d2 = st.columns(2, gap="medium")
            with d1:
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">Identity</div>', unsafe_allow_html=True)
                for field in ["GSTIN", "INVOICE_NO", "INVOICE_DATE", "MERCHANT"]:
                    st.markdown(f"""
                    <div class="detail-row">
                        <span class="detail-label">{field.replace("_", " ").title()}</span>
                        <span class="detail-value mono">{raw.get(field, "—")}</span>
                    </div>""", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with d2:
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">Financials</div>', unsafe_allow_html=True)
                for field, label in [
                    ("TOTAL_AMOUNT",   "Total Amount"),
                    ("TAXABLE_AMOUNT", "Taxable Amount"),
                    ("GST_AMOUNT",     "GST Amount"),
                ]:
                    st.markdown(f"""
                    <div class="detail-row">
                        <span class="detail-label">{label}</span>
                        <span class="detail-value" style="color:#00D4AA;
                              font-family:'DM Mono',monospace;">{fmt_inr(raw.get(field))}</span>
                    </div>""", unsafe_allow_html=True)
                cloudinary = raw.get("cloudinary_url")
                if cloudinary:
                    st.image(cloudinary, use_container_width=True)
                    st.markdown(f"""
                    <a href="{cloudinary}" target="_blank"
                       style="color:#00D4AA; font-size:0.75rem; text-decoration:none;">
                       ☁️ Open on Cloudinary ↗</a>""", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center; color:#4A5568; font-size:0.72rem; margin-top:0.75rem;">
        Page {page_num} of {total_pages} · {len(filtered)} records · {PAGE_SIZE} per page
    </div>""", unsafe_allow_html=True)