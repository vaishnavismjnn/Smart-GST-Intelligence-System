# --- file: pages/records.py ---

import streamlit as st
import pandas as pd
import io
from utils.api import get_records
from utils.auth import is_authenticated
from utils.formatters import fmt_inr, fmt_bool_badge, short_id, fmt_date
from utils.cleaner import normalize_record, clean_amount, deduplicate_records
from components.illustrations import empty_records_illustration, render_illustration

PAGE_SIZE = 10


# ── SAFE DF BUILDER ──────────────────────────────────────────────────────────
def _build_df(records: list) -> pd.DataFrame:
    rows = []

    for r in records:
        try:
            r = normalize_record(r)
            v = r.get("validation") or {}

            rows.append({
                "ID":        short_id(r.get("_id", "")),
                "Merchant":  r.get("MERCHANT"),
                "GSTIN":     r.get("GSTIN"),
                "Date":      fmt_date(r.get("INVOICE_DATE")),
                "Total":     clean_amount(r.get("TOTAL_AMOUNT")),
                "GST":       clean_amount(r.get("GST_AMOUNT")),
                "GST Valid": bool(v.get("gst_valid")),
                "Amt Match": bool(v.get("amounts_match")),
                "Status":    r.get("status") or "processed",
                "_raw":      r,
            })
        except Exception:
            continue  # 🔒 Never break UI due to one bad record

    return pd.DataFrame(rows)


# ── MAIN VIEW ────────────────────────────────────────────────────────────────
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

    # ── FETCH DATA ───────────────────────────────────────────────────────────
    try:
        records = get_records()
    except Exception:
        records = []

    if not isinstance(records, list):
        records = []

    records = [r for r in records if isinstance(r, dict)]

    # ── EMPTY STATE ──────────────────────────────────────────────────────────
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

    # ── QUICK STATS ──────────────────────────────────────────────────────────
    deduped = deduplicate_records(records)

    total_val = sum(clean_amount(r.get("TOTAL_AMOUNT")) for r in deduped)
    total_gst = sum(clean_amount(r.get("GST_AMOUNT")) for r in deduped)

    valid_cnt = sum(
        1 for r in deduped
        if (r.get("validation") or {}).get("gst_valid") is True
    )

    qs_cols = st.columns(4)

    stats = [
        ("📦", "Total Records", str(len(deduped))),
        ("💰", "Total Value", fmt_inr(total_val)),
        ("🏛️", "Total GST", fmt_inr(total_gst)),
        ("✅", "Valid GSTINs", f"{valid_cnt}/{len(deduped)}"),
    ]

    for col, (icon, label, val) in zip(qs_cols, stats):
        col.markdown(f"""
        <div style="padding:0.7rem; border:1px solid rgba(0,212,170,0.12);
                    border-radius:10px;">
            <div>{icon} {label}</div>
            <div style="color:#00D4AA; font-weight:700;">{val}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── FILTERS ──────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns(4)

    search = fc1.text_input("Search", placeholder="Merchant or GSTIN...")
    status_f = fc2.selectbox("Status", ["All", "processed"])
    gst_f = fc3.selectbox("Validity", ["All", "Valid", "Invalid"])
    amt_f = fc4.selectbox("Amounts", ["All", "Match", "Mismatch"])

    filtered = df.copy()

    if search:
        filtered = filtered[
            filtered["Merchant"].str.contains(search, case=False, na=False) |
            filtered["GSTIN"].str.contains(search, case=False, na=False)
        ]

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

    if filtered.empty:
        st.info("No matching records found")
        return

    # ── TABLE ────────────────────────────────────────────────────────────────
    total_pages = max(1, (len(filtered) - 1) // PAGE_SIZE + 1)
    page = st.number_input("Page", 1, total_pages, 1)

    start = (page - 1) * PAGE_SIZE
    page_df = filtered.iloc[start:start + PAGE_SIZE]

    for _, row in page_df.iterrows():
        raw = row["_raw"]
        v = raw.get("validation", {})

        st.markdown(f"""
        <div style="padding:0.6rem; border-bottom:1px solid #222;">
            <b>{row["Merchant"]}</b> | {row["GSTIN"]}<br>
            {fmt_inr(row["Total"])} | GST: {fmt_inr(row["GST"])}<br>
            GST Valid: {v.get("gst_valid")} | Amount Match: {v.get("amounts_match")}
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Details"):
            st.write(raw)

    st.markdown(f"Page {page} / {total_pages}")