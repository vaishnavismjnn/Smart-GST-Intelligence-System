# --- file: pages/dashboard.py ---

import streamlit as st
from utils.api import get_records
from utils.auth import is_authenticated
from components.cards import render_kpi_strip, activity_item
from components.charts import (
    bar_invoices_last30,
    donut_gst_validity,
    line_gst_trend,
    bar_amount_breakdown,
)
from utils.formatters import fmt_inr
from datetime import datetime
import time

CHART_CFG = {"displayModeBar": False, "responsive": True}


# ------------------ HELPERS ------------------

def _render_live_ticker(records):
    records = records or []
    processed = [r for r in records if r.get("MERCHANT") and r.get("status") == "processed"]

    if not processed:
        return

    items = " &nbsp;·&nbsp; ".join(
        f"<span style='color:#00D4AA;'>▸</span> {r['MERCHANT']} "
        f"<span style='color:#F5C842;'>{fmt_inr(r.get('TOTAL_AMOUNT'))}</span>"
        for r in processed[-10:]
    )

    st.markdown(f"""
    <div style="
        overflow:hidden;
        background:rgba(0,212,170,0.05);
        border:1px solid rgba(0,212,170,0.15);
        border-radius:10px;
        padding:0.5rem 1rem;
        margin-bottom:1.2rem;
    ">
        <div style="display:flex; align-items:center; gap:1rem;">
            
            <!-- LIVE TAG -->
            <span style="
                color:#00D4AA;
                font-size:0.7rem;
                font-weight:700;
                letter-spacing:0.1em;
                white-space:nowrap;
            ">
                ● LIVE
            </span>

            <!-- SCROLLING CONTENT -->
            <div style="overflow:hidden; flex:1;">
                <div style="
                    white-space:nowrap;
                    display:inline-block;
                    animation: scrollTicker 18s linear infinite;
                    font-size:0.85rem;
                    color:#A0AEC0;
                ">
                    {items}
                </div>
            </div>
        </div>
    </div>

    <style>
    @keyframes scrollTicker {{
        0%   {{ transform: translateX(100%); }}
        100% {{ transform: translateX(-100%); }}
    }}
    </style>
    """, unsafe_allow_html=True)


def _render_insight_bar(records):
    records = records or []
    processed = [r for r in records if r.get("status") == "processed"]
    if not processed:
        return

    total_gst = sum(r.get("GST_AMOUNT", 0) or 0 for r in processed)
    valid_pct = int(
        sum(1 for r in processed if (r.get("validation") or {}).get("gst_valid")) 
        / len(processed) * 100
    ) if processed else 0

    avg = sum(r.get("TOTAL_AMOUNT", 0) or 0 for r in processed) / len(processed)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total ITC", fmt_inr(total_gst))
    col2.metric("GST Compliance", f"{valid_pct}%")
    col3.metric("Avg Invoice", fmt_inr(avg))
    col4.metric("Updated", datetime.now().strftime('%H:%M'))


# ------------------ MAIN ------------------

def show():

    if not is_authenticated():
        st.warning("Please log in.")
        return

    user = st.session_state.get("user", "").split("@")[0].title()

    st.title(f"Welcome back, {user} 👋")

    # ------------------ SAFE DATA FETCH ------------------

    records = []

    with st.spinner("Fetching records..."):
        for _ in range(3):  # retry logic
            try:
                records = get_records()
                if records:
                    break
            except Exception:
                pass
            time.sleep(2)

    records = records or []

    # ------------------ UI ------------------

    _render_live_ticker(records)

    render_kpi_strip(records)

    _render_insight_bar(records)

    # ------------------ CHARTS ------------------

    col1, col2 = st.columns(2)

    with col1:
        fig_bar = bar_invoices_last30(records)
        if fig_bar:
            st.plotly_chart(fig_bar, use_container_width=True, config=CHART_CFG)

    with col2:
        fig_donut = donut_gst_validity(records)
        if fig_donut:
            st.plotly_chart(fig_donut, use_container_width=True, config=CHART_CFG)

    fig_line = line_gst_trend(records)
    if fig_line:
        st.plotly_chart(fig_line, use_container_width=True, config=CHART_CFG)

    fig_stack = bar_amount_breakdown(records)
    if fig_stack:
        st.plotly_chart(fig_stack, use_container_width=True, config=CHART_CFG)

    # ------------------ ACTIVITY ------------------

    st.subheader("Recent Activity")

    recent = [r for r in records if r.get("status") == "processed"][-5:][::-1]

    if not recent:
        st.info("No recent activity")
    else:
        for rec in recent:
            activity_item(rec)

    # ------------------ SUMMARY ------------------

    st.subheader("Financial Summary")

    processed = [r for r in records if r.get("TOTAL_AMOUNT")]

    if processed:
        total_turnover = sum(r.get("TOTAL_AMOUNT", 0) or 0 for r in processed)
        avg_invoice = total_turnover / len(processed)
        total_taxable = sum(r.get("TAXABLE_AMOUNT", 0) or 0 for r in processed)
        total_gst = sum(r.get("GST_AMOUNT", 0) or 0 for r in processed)

        st.write("Total Turnover:", fmt_inr(total_turnover))
        st.write("Avg Invoice:", fmt_inr(avg_invoice))
        st.write("Total Taxable:", fmt_inr(total_taxable))
        st.write("Total GST:", fmt_inr(total_gst))

        # Excel export
        try:
            from utils.excel_builder import _build_excel

            excel_bytes = _build_excel(records, title="GST Intelligence")

            st.download_button(
                "Download Excel",
                excel_bytes,
                file_name="gst_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except Exception as e:
            st.error(f"Excel export error: {e}")

    else:
        st.info("Upload invoices to see analytics")