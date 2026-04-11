# --- file: pages/itc_forecaster.py ---
# ═══════════════════════════════════════════════════════════════════════════
# ITC FORECASTER PAGE
# Input Tax Credit accumulation tracker — only from fully validated invoices.
#
# ITC (Input Tax Credit) is a core GST mechanism:
#   When a registered business pays GST on purchases (input tax), it can
#   deduct that amount from the GST it must pay on its own sales (output tax).
#   This avoids double taxation. However, ITC can only be claimed when:
#     1. The supplier's GSTIN is valid (they are registered to collect GST)
#     2. The invoice amounts are internally consistent (not corrupted by OCR)
#     3. The invoice has been processed (OCR completed)
#     4. GST_AMOUNT > 0 (zero-GST transactions have nothing to claim)
# ═══════════════════════════════════════════════════════════════════════════

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from utils.api import get_records
from utils.auth import is_authenticated
from utils.formatters import fmt_inr
from utils.cleaner import clean_amount, deduplicate_records, get_valid_processed

CHART_CFG = {"displayModeBar": False, "responsive": True}


# ── _compute_itc ──────────────────────────────────────────────────────────────
# WHY SIX GATES (and not just gst_valid + amounts_match):
#
#   Gate 1 — status == "processed":
#     "Uploaded" invoices are still in the OCR queue. They have no validated
#     data — including them would mean claiming ITC on unverified numbers.
#
#   Gate 2 — Deduplicated:
#     A user who uploads the same invoice twice must not claim ITC twice.
#     Dedup runs before all other gates so that if copies disagree on validity,
#     we admit only the first occurrence.
#
#   Gate 3 — gst_valid is True:
#     The GSTIN was verified against the Indian GST registry format and check
#     digit. An invalid GSTIN means the supplier may not be registered — GST
#     paid to an unregistered supplier cannot be reclaimed.
#
#   Gate 4 — amounts_match is True:
#     TAXABLE_AMOUNT + GST_AMOUNT ≈ TOTAL_AMOUNT (within ₹2 tolerance).
#     If OCR misread any amount, this flag is False. We must not claim ITC
#     based on corrupted numbers.
#
#   Gate 5 — GST_AMOUNT > 0:
#     Some invoices are exempt from GST (e.g. basic food items). Their
#     GST_AMOUNT is 0. Zero GST means zero ITC — including them would
#     inflate the eligible invoice count without adding to the ITC total.
#
#   Gate 6 — TOTAL_AMOUNT > 0:
#     Enforced by get_valid_processed(). A backend validation gap can mark
#     an invoice valid even when OCR extracted no amounts (all None → 0.0).
#
# We use get_valid_processed() for Gates 1–2–3–4–6, then add Gate 5 here.
def _compute_itc(records: list):
    """
    Returns (eligible_records, total_itc_float, daily_wins_list).
    eligible_records: records that pass all six ITC gates.
    total_itc_float:  sum of GST_AMOUNT for eligible records, rounded to 2dp.
    daily_wins_list:  [{merchant, amount, date}] for the Daily Wins panel.
    """
    # Gates 1, 2, 3, 4, 6 via get_valid_processed
    base_valid = get_valid_processed(records)

    eligible: list = []
    wins:     list = []

    for r in base_valid:
        amt = clean_amount(r.get("GST_AMOUNT"))
        if amt <= 0:          # Gate 5: must have positive GST
            continue
        eligible.append(r)
        wins.append({
            "merchant": r.get("MERCHANT", "Unknown"),
            "amount":   amt,
            "date":     r.get("INVOICE_DATE", "—"),
        })

    total = sum(clean_amount(r.get("GST_AMOUNT")) for r in eligible)
    return eligible, round(total, 2), wins


# ── _build_trend_chart ────────────────────────────────────────────────────────
# Cumulative ITC line chart sorted chronologically.
#
# HOW CUMULATIVE SUM WORKS:
#   For each eligible invoice sorted by INVOICE_DATE, we add its GST_AMOUNT
#   to a running total. The chart shows how the ITC pool has grown over time.
#   This helps identify: seasonal patterns, months with high valid invoice
#   volumes, and periods where validation failed (flat sections of the line).
#
# Date parsing: We try three formats in order (day-month-year with hyphens,
#   with slashes, then ISO format) because OCR and manual data entry produce
#   all three. We skip invoices with unparseable dates rather than crashing.
def _build_trend_chart(eligible: list):
    dated = []
    for r in eligible:
        raw = r.get("INVOICE_DATE")
        amt = clean_amount(r.get("GST_AMOUNT"))
        if not raw or amt <= 0:
            continue
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                d = datetime.strptime(str(raw), fmt).date()
                dated.append((d, amt))
                break
            except ValueError:
                continue

    if not dated:
        return None

    dated.sort(key=lambda x: x[0])
    dates, running, cumulative = [], 0.0, []
    for d, a in dated:
        running += a
        dates.append(str(d))
        cumulative.append(round(running, 2))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=cumulative, mode="lines",
        line=dict(color="#00A896", width=2.5, shape="spline", smoothing=1.2),
        fill="tozeroy", fillcolor="rgba(0,168,150,0.08)",
        hovertemplate="<b>%{x}</b><br>Cumulative ITC: ₹%{y:,.2f}<extra></extra>",
        name="Cumulative ITC",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=cumulative, mode="markers",
        marker=dict(color="#00A896", size=7, line=dict(color="#E8F4FD", width=2)),
        hoverinfo="skip", showlegend=False,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color="#2D5873", size=11),
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.95)",
                        bordercolor="rgba(0,168,150,0.3)",
                        font=dict(family="DM Sans", color="#0F2137", size=12)),
        title=dict(text="Cumulative ITC — Eligible Invoices Only",
                   font=dict(size=13, color="#0F2137"), x=0, xanchor="left"),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=9, color="#5A8FA8")),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,168,150,0.1)",
                   zeroline=False, tickfont=dict(size=9, color="#5A8FA8")),
        showlegend=False,
    )
    return fig


# ── _gauge_svg ────────────────────────────────────────────────────────────────
# Semi-circular SVG gauge.
#
# MATH (arc drawing):
#   The gauge is a 180° semicircle (left to right = 0% to 100%).
#   pct% of the semicircle = pct/100 × 180 degrees.
#   To draw the filled arc we need the endpoint (ex, ey) of that angle.
#   We use standard polar→Cartesian: x = cx + r·cos(θ), y = cy - r·sin(θ)
#   The angle θ is measured from the RIGHT (0°) going counter-clockwise,
#   but our gauge goes from LEFT (180°) to RIGHT (0°), so:
#     θ = 180° - (pct/100 × 180°)
#   The SVG arc large-arc-flag = 1 when the arc spans more than 180° (never
#   happens in a 0-100% semicircle, so large = 0 always — we keep the check
#   for correctness).
def _gauge_svg(pct: int) -> str:
    import math
    cx, cy, r = 110, 110, 85
    angle = (pct / 100) * 180
    rad   = math.radians(180 - angle)
    ex    = cx + r * math.cos(rad)
    ey    = cy - r * math.sin(rad)
    large = 1 if angle > 180 else 0

    return f"""
    <svg viewBox="0 0 220 130" xmlns="http://www.w3.org/2000/svg"
         style="width:100%;max-width:260px;margin:0 auto;display:block;">
      <defs>
        <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   style="stop-color:#00A896"/>
          <stop offset="100%" style="stop-color:#D4A017"/>
        </linearGradient>
      </defs>
      <path d="M 25 110 A 85 85 0 0 1 195 110"
            fill="none" stroke="rgba(0,168,150,0.15)" stroke-width="14" stroke-linecap="round"/>
      <path d="M 25 110 A 85 85 0 {large} 1 {ex:.2f} {ey:.2f}"
            fill="none" stroke="url(#gaugeGrad)" stroke-width="14" stroke-linecap="round"/>
      <text x="110" y="95"  fill="#00A896" font-size="22" font-weight="700"
            text-anchor="middle" font-family="DM Mono,monospace">{pct}%</text>
      <text x="110" y="115" fill="#5A8FA8" font-size="9"  text-anchor="middle"
            font-family="DM Sans,sans-serif">of GST claimable as ITC</text>
    </svg>
    """


# ── show ──────────────────────────────────────────────────────────────────────
def show() -> None:
    if not is_authenticated():
        st.warning("Please log in.")
        return

    st.markdown("""
    <div class="page-header">
        <div class="page-title">💰 ITC Forecaster</div>
        <div class="page-sub">Input Tax Credit accumulation — only from fully validated invoices</div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(""):
        raw_records = get_records()

    # Normalise API response — get_records() guarantees a list, but guard anyway
    if isinstance(raw_records, list):
        records = [r for r in raw_records if isinstance(r, dict)]
    else:
        records = []

    eligible, total_itc, wins = _compute_itc(records)

    # ITC Recovery Rate denominator:
    #   = total GST from ALL deduped processed invoices (not just valid)
    #   This answers: "of all the GST we paid on processed invoices, how much
    #   can we actually reclaim?"  A low % means many invoices failed validation.
    deduped_processed = deduplicate_records([
        r for r in records if isinstance(r, dict) and r.get("status") == "processed"
    ])
    total_gst = sum(clean_amount(r.get("GST_AMOUNT")) for r in deduped_processed)

    pct            = min(100, int(total_itc / total_gst * 100)) if total_gst > 0 else 0
    ineligible_cnt = len(deduped_processed) - len(eligible)
    ineligible_gst = max(0.0, total_gst - total_itc)

    # ── Row 1: Gauge + KPI Breakdown ──────────────────────────────────────────
    col_gauge, col_kpis = st.columns([1, 1.6], gap="large")

    with col_gauge:
        st.markdown('<div class="glass-card itc-gauge-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">ITC Gauge</div>', unsafe_allow_html=True)
        st.markdown(_gauge_svg(pct), unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align:center; margin-top:0.5rem;">
            <div class="itc-amount">{fmt_inr(total_itc)}</div>
            <div class="itc-label">Total ITC Claimable</div>
        </div></div>""", unsafe_allow_html=True)

    with col_kpis:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Breakdown</div>', unsafe_allow_html=True)
        for icon, label, val, color in [
            ("✅", "Eligible Invoices",   str(len(eligible)),      "#00A896"),
            ("❌", "Ineligible Invoices", str(ineligible_cnt),     "#D63E58"),
            ("💰", "ITC Claimable",       fmt_inr(total_itc),      "#00A896"),
            ("🚫", "ITC Blocked",         fmt_inr(ineligible_gst), "#D63E58"),
            ("📊", "Total GST Pool",      fmt_inr(total_gst),      "#D4A017"),
        ]:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center;
                        padding:0.7rem 0.4rem; border-bottom:1px solid var(--border);
                        border-radius:6px; transition:background 0.15s;"
                 onmouseover="this.style.background='rgba(0,168,150,0.04)'"
                 onmouseout="this.style.background='transparent'">
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <span>{icon}</span>
                    <span style="color:var(--text2); font-size:0.82rem;">{label}</span>
                </div>
                <span style="color:{color}; font-weight:700; font-family:'DM Mono',monospace;
                             font-size:0.88rem;">{val}</span>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="margin-top:1rem; padding:0.85rem; background:rgba(0,168,150,0.06);
                    border:1px solid rgba(0,168,150,0.15); border-radius:10px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;">
                <span style="color:var(--text2); font-size:0.72rem;">ITC Recovery Rate</span>
                <span style="color:var(--accent); font-weight:700; font-size:0.78rem;">{pct}%</span>
            </div>
            <div style="height:6px; background:rgba(0,168,150,0.12); border-radius:4px; overflow:hidden;">
                <div style="height:100%; width:{pct}%;
                            background:linear-gradient(90deg,#00A896,#D4A017);
                            border-radius:4px; transition:width 1.2s ease;"></div>
            </div>
        </div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Row 2: Trend Chart + Daily Wins ───────────────────────────────────────
    col_chart, col_wins = st.columns([1.6, 1], gap="large")

    with col_chart:
        st.markdown('<div class="glass-card" style="padding:1.25rem 1.5rem;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📈 ITC Accumulation Trend</div>', unsafe_allow_html=True)
        fig = _build_trend_chart(eligible)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)
        else:
            st.markdown("""
            <div style="text-align:center; padding:3rem; color:var(--muted);">
                <div style="font-size:2rem; margin-bottom:0.5rem;">📊</div>
                <div style="font-size:0.85rem;">No dated eligible invoices yet</div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_wins:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🎉 Daily Wins</div>', unsafe_allow_html=True)
        st.markdown("""<div style="font-size:0.72rem; color:var(--muted); margin-bottom:0.75rem;">
            Each eligible invoice adds to your ITC pool</div>""", unsafe_allow_html=True)
        if not wins:
            st.markdown("""
            <div style="text-align:center; padding:2rem; color:var(--muted);">
                <div style="font-size:2rem; margin-bottom:0.5rem;">🏆</div>
                <div style="font-size:0.82rem;">No eligible invoices yet</div>
            </div>""", unsafe_allow_html=True)
        else:
            for w in wins[-6:][::-1]:
                st.markdown(f"""
                <div class="win-toast">
                    <span style="font-size:1.2rem;">✅</span>
                    <div>
                        <div style="font-weight:600; font-size:0.82rem; color:var(--text);">
                            +{fmt_inr(w["amount"])} added to Tax Credits!
                        </div>
                        <div style="font-size:0.7rem; color:var(--muted); margin-top:2px;">
                            {w["merchant"]} · {w["date"]}
                        </div>
                    </div>
                </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)