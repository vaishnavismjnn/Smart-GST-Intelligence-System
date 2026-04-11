# --- file: pages/dashboard.py ---
# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD PAGE
# Overview analytics: KPI strip, live ticker, insight bar, 4 charts,
# recent activity feed, financial summary with ITC progress.
# ═══════════════════════════════════════════════════════════════════════════

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
from utils.cleaner import clean_amount, deduplicate_records, get_valid_processed
from utils.excel_builder import _build_excel   # ← wired in: dashboard Excel export
from datetime import datetime

CHART_CFG = {"displayModeBar": False, "responsive": True}


# ── _safe_records ─────────────────────────────────────────────────────────────
# WHY: get_records() now always returns a list (api.py enforces this), but we
# keep this normaliser as a belt-and-suspenders guard. Any page that calls
# get_records() and passes the result here is guaranteed to get a clean list
# of dicts regardless of what the API returned.
def _safe_records(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, dict):
        if "records" in raw and isinstance(raw["records"], list):
            return [r for r in raw["records"] if isinstance(r, dict)]
        return []
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    return []


# ── _render_live_ticker ───────────────────────────────────────────────────────
# Shows the last 8 processed invoices scrolling horizontally.
# Purely cosmetic — uses all processed records (not just valid) so the ticker
# shows real activity, not a filtered subset.
def _render_live_ticker(records: list) -> None:
    processed = [r for r in records if r.get("MERCHANT") and r.get("status") == "processed"]
    if not processed:
        return
    items = " &nbsp;·&nbsp; ".join(
        f'<span style="color:#00D4AA;">▸</span> {r["MERCHANT"]} '
        f'<span style="color:#F5C842;">{fmt_inr(r.get("TOTAL_AMOUNT"))}</span>'
        for r in processed[-8:]
    )
    st.markdown(f"""
    <div style="overflow:hidden; background:rgba(0,212,170,0.04);
                border:1px solid rgba(0,212,170,0.1); border-radius:8px;
                padding:0.45rem 1rem; margin-bottom:1.5rem;">
        <div style="display:flex; align-items:center; gap:1rem;">
            <span style="color:#00D4AA; font-size:0.65rem; font-weight:700;
                         text-transform:uppercase; letter-spacing:0.1em;
                         white-space:nowrap; flex-shrink:0;">
                <span class="pulse-dot"></span>&nbsp; LIVE
            </span>
            <div style="overflow:hidden; flex:1;">
                <div style="font-size:0.75rem; color:#A0AEC0;
                            white-space:nowrap; font-family:'DM Mono',monospace;
                            animation:ticker 18s linear infinite;">
                    {items}
                </div>
            </div>
        </div>
    </div>
    <style>
    @keyframes ticker {{
        0%   {{ transform: translateX(100%); }}
        100% {{ transform: translateX(-100%); }}
    }}
    </style>
    """, unsafe_allow_html=True)


# ── _render_insight_bar ───────────────────────────────────────────────────────
# Four quick-read stat chips below the KPI strip.
#
# ITC chip:
#   Shows only the GST from fully valid invoices — the ITC-claimable amount.
#   Uses get_valid_processed() so duplicates and invalid invoices are excluded.
#
# Compliance chip:
#   valid_count / deduped_processed_count × 100
#   Deduped denominator: we want "what % of unique invoices passed validation"
#   not "what % of upload attempts passed". A duplicate upload should not
#   lower the compliance rate.
#
# Avg chip:
#   Average invoice value across all deduped processed invoices (including
#   invalid ones — this is an operational average, not a financial one).
def _render_insight_bar(records: list) -> None:
    records = records or []

    # Denominator: all processed invoices deduplicated
    deduped_processed = deduplicate_records([
        r for r in records
        if isinstance(r, dict) and r.get("status") == "processed"
    ])
    if not deduped_processed:
        return

    # ITC-eligible GST: only from fully valid invoices
    valid = get_valid_processed(records)
    itc_gst = sum(clean_amount(r.get("GST_AMOUNT")) for r in valid)

    # Operational average across all processed (not just valid)
    total_amt = sum(clean_amount(r.get("TOTAL_AMOUNT")) for r in deduped_processed)
    avg = total_amt / len(deduped_processed)

    # Compliance = valid / deduped_processed (both gst_valid AND amounts_match)
    valid_pct = int(len(valid) / len(deduped_processed) * 100) if deduped_processed else 0

    cols = st.columns(4, gap="small")
    for i, (icon, text) in enumerate([
        ("🏛️", f"ITC: {fmt_inr(itc_gst)}"),
        ("📈", f"Compliance: {valid_pct}%"),
        ("💡", f"Avg: {fmt_inr(avg)}"),
        ("📅", datetime.now().strftime("%d %b %H:%M")),
    ]):
        cols[i].markdown(
            f"""<div style="padding:0.6rem;background:rgba(0,212,170,0.04);
                border:1px solid rgba(0,212,170,0.1);border-radius:10px;">
                {icon} {text}</div>""",
            unsafe_allow_html=True,
        )


# ── show ──────────────────────────────────────────────────────────────────────
def show() -> None:
    if not is_authenticated():
        st.warning("Please log in.")
        return

    user = st.session_state.get("user", "").split("@")[0].replace(".", " ").title()

    st.markdown(f"""
    <div class="page-header">
        <div class="page-title">Welcome back, {user} 👋</div>
        <div class="page-sub">
            GST Intelligence Dashboard · {datetime.now().strftime("%A, %d %B %Y")}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Fetch ─────────────────────────────────────────────────────────────────
    try:
        raw = get_records()
    except Exception:
        raw = []
    records = _safe_records(raw)

    # ── Top UI ────────────────────────────────────────────────────────────────
    _render_live_ticker(records)
    render_kpi_strip(records)
    _render_insight_bar(records)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    # All four chart functions accept the raw records list and do their own
    # filtering internally — they show trends across all data, not just valid.
    col1, col2 = st.columns([2.2, 1])
    with col1:
        fig = bar_invoices_last30(records)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)
    with col2:
        fig = donut_gst_validity(records)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

    fig = line_gst_trend(records)
    if fig:
        st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

    fig = bar_amount_breakdown(records)
    if fig:
        st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Bottom Section ────────────────────────────────────────────────────────
    col_activity, col_summary = st.columns([1.5, 1], gap="medium")

    # Activity feed: all deduped processed invoices (shows real pipeline activity)
    processed_deduped = deduplicate_records([
        r for r in records if r.get("status") == "processed"
    ])

    # Financial summary: only fully valid, deduped invoices
    valid = get_valid_processed(records)

    # ── Activity Feed ─────────────────────────────────────────────────────────
    with col_activity:
        st.markdown("### ⚡ Recent Activity")
        recent = processed_deduped[-5:][::-1]
        if not recent:
            st.info("No activity yet")
        else:
            for r in recent:
                activity_item(r)

    # ── Financial Summary ──────────────────────────────────────────────────────
    # FORMULAS:
    #   Turnover  = Σ TOTAL_AMOUNT   for all valid invoices
    #   Taxable   = Σ TAXABLE_AMOUNT for all valid invoices
    #   GST total = Σ GST_AMOUNT     for all valid invoices
    #   Avg       = Turnover / count(valid)
    #
    #   ITC = Σ GST_AMOUNT for valid invoices where GST_AMOUNT > 0
    #     (valid already gates on gst_valid + amounts_match, so all ITC-eligible)
    #
    #   ITC % = ITC / GST_total × 100   (capped at 100 for display safety)
    #     Interpretation: "What fraction of our total GST spend is recoverable
    #     as Input Tax Credit?" Lower means more invoices failed validation.
    with col_summary:
        st.markdown("### 🏦 Financial Summary")
        if valid:
            total_turnover = sum(clean_amount(r.get("TOTAL_AMOUNT"))   for r in valid)
            total_taxable  = sum(clean_amount(r.get("TAXABLE_AMOUNT")) for r in valid)
            total_gst      = sum(clean_amount(r.get("GST_AMOUNT"))     for r in valid)
            avg_invoice    = total_turnover / len(valid)

            st.write("Turnover:",    fmt_inr(total_turnover))
            st.write("Avg Invoice:", fmt_inr(avg_invoice))
            st.write("Taxable:",     fmt_inr(total_taxable))
            st.write("GST:",         fmt_inr(total_gst))

            itc = sum(
                clean_amount(r.get("GST_AMOUNT"))
                for r in valid
                if clean_amount(r.get("GST_AMOUNT")) > 0
            )
            pct = min(100, int((itc / total_gst) * 100)) if total_gst > 0 else 0

            st.metric("ITC Eligible GST", fmt_inr(itc))
            st.progress(pct / 100)

            # ── Excel Export ──────────────────────────────────────────────────
            # Exports only the valid processed (ITC-eligible) invoices so the
            # workbook contains the same set that the Financial Summary is built
            # from — turnover, GST totals, and ITC figures all tie out exactly.
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            try:
                excel_bytes = _build_excel(
                    valid,
                    title="GST Intelligence — Dashboard Financial Summary"
                )
                st.download_button(
                    label="📊 Export Valid Invoices to Excel",
                    data=excel_bytes,
                    file_name="gst_dashboard_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dashboard_excel_export",
                )
            except Exception as e:
                st.error(f"Excel export error: {e}")
        else:
            st.info("Upload invoices to see financial summary")