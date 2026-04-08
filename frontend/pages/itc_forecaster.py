# --- file: pages/itc_forecaster.py ---
# Feature: Input Tax Credit (ITC) Forecaster
# CSS classes used: .glass-card, .section-title, .itc-gauge-wrap,
#                  .itc-amount, .itc-label, .win-toast, .kpi-card
# All defined in styles.py — nothing new added here.

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from utils.api import get_records
from utils.auth import is_authenticated
from utils.formatters import fmt_inr

CHART_CFG = {"displayModeBar": False, "responsive": True}

# ── Helper: ITC aggregation ────────────────────────────────────
def _compute_itc(records: list):
    """
    Only invoices where BOTH gst_valid AND amounts_match are True
    qualify for Input Tax Credit. Aggregate GST_AMOUNT across those.
    Returns (eligible_records, total_itc, daily_wins).
    """
    eligible, wins = [], []
    for r in records:
        v = r.get("validation", {}) or {}
        if v.get("gst_valid") is True and v.get("amounts_match") is True:
            amt = r.get("GST_AMOUNT") or 0
            eligible.append(r)
            wins.append({
                "merchant": r.get("MERCHANT", "Unknown"),
                "amount":   amt,
                "date":     r.get("INVOICE_DATE", "—"),
            })
    total = sum(r.get("GST_AMOUNT", 0) or 0 for r in eligible)
    return eligible, round(total, 2), wins

def _build_trend_chart(eligible: list):
    """
    Cumulative ITC line chart sorted by INVOICE_DATE.
    X = date, Y = cumulative GST_AMOUNT from eligible invoices only.
    """
    dated = []
    for r in eligible:
        raw = r.get("INVOICE_DATE")
        amt = r.get("GST_AMOUNT") or 0
        if not raw:
            continue
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                d = datetime.strptime(str(raw), fmt).date()
                dated.append((d, float(amt)))
                break
            except ValueError:
                continue

    if not dated:
        return None

    dated.sort(key=lambda x: x[0])
    dates, running, cumulative = [], 0, []
    for d, a in dated:
        running += a
        dates.append(str(d))
        cumulative.append(round(running, 2))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=cumulative,
        mode="lines",
        line=dict(color="#00A896", width=2.5, shape="spline", smoothing=1.2),
        fill="tozeroy",
        fillcolor="rgba(0,168,150,0.08)",
        hovertemplate="<b>%{x}</b><br>Cumulative ITC: ₹%{y:,.2f}<extra></extra>",
        name="Cumulative ITC",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=cumulative,
        mode="markers",
        marker=dict(color="#00A896", size=7,
                    line=dict(color="#E8F4FD", width=2)),
        hoverinfo="skip", showlegend=False,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color="#2D5873", size=11),
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(0,168,150,0.3)",
            font=dict(family="DM Sans", color="#0F2137", size=12)
        ),
        title=dict(
            text="Cumulative ITC — Eligible Invoices Only",
            font=dict(size=13, color="#0F2137"), x=0, xanchor="left"
        ),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=9, color="#5A8FA8")),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,168,150,0.1)",
                   zeroline=False, tickfont=dict(size=9, color="#5A8FA8")),
        showlegend=False,
    )
    return fig

def _gauge_svg(pct: int, total_itc: float):
    """
    Semi-circular SVG gauge showing ITC accumulation percentage.
    pct = eligible GST / total GST * 100
    """
    # Arc math for semi-circle (180 degrees)
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
          <stop offset="0%" style="stop-color:#00A896"/>
          <stop offset="100%" style="stop-color:#D4A017"/>
        </linearGradient>
      </defs>
      <!-- Track -->
      <path d="M 25 110 A 85 85 0 0 1 195 110"
            fill="none" stroke="rgba(0,168,150,0.15)" stroke-width="14"
            stroke-linecap="round"/>
      <!-- Fill -->
      <path d="M 25 110 A 85 85 0 {large} 1 {ex:.2f} {ey:.2f}"
            fill="none" stroke="url(#gaugeGrad)" stroke-width="14"
            stroke-linecap="round"/>
      <!-- Center text -->
      <text x="110" y="95" fill="#00A896" font-size="22" font-weight="700"
            text-anchor="middle" font-family="DM Mono,monospace">{pct}%</text>
      <text x="110" y="115" fill="#5A8FA8" font-size="9" text-anchor="middle"
            font-family="DM Sans,sans-serif">of GST claimable as ITC</text>
    </svg>
    """

def show():
    if not is_authenticated():
        st.warning("Please log in.")
        return

    st.markdown("""
    <div class="page-header">
        <div class="page-title">💰 ITC Forecaster</div>
        <div class="page-sub">
            Input Tax Credit accumulation — only from fully validated invoices
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(""):
        records = get_records()

    eligible, total_itc, wins = _compute_itc(records)
    total_gst = sum(r.get("GST_AMOUNT", 0) or 0 for r in records if r.get("GST_AMOUNT"))
    pct = min(100, int(total_itc / total_gst * 100)) if total_gst > 0 else 0

    # ── Row 1: Gauge + KPIs ─────────────────────────────────
    col_gauge, col_kpis = st.columns([1, 1.6], gap="large")

    with col_gauge:
        st.markdown('<div class="glass-card itc-gauge-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">ITC Gauge</div>', unsafe_allow_html=True)
        st.markdown(_gauge_svg(pct, total_itc), unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align:center; margin-top:0.5rem;">
            <div class="itc-amount">{fmt_inr(total_itc)}</div>
            <div class="itc-label">Total ITC Claimable</div>
        </div>
        </div>""", unsafe_allow_html=True)

    with col_kpis:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Breakdown</div>', unsafe_allow_html=True)

        ineligible_cnt = len(records) - len(eligible)
        ineligible_gst = total_gst - total_itc

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
            </div>
            """, unsafe_allow_html=True)

        # ITC progress bar
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
        </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Row 2: Trend Chart + Daily Wins ─────────────────────
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
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_wins:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🎉 Daily Wins</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:0.72rem; color:var(--muted); margin-bottom:0.75rem;">
            Each eligible invoice adds to your ITC pool
        </div>
        """, unsafe_allow_html=True)

        if not wins:
            st.markdown("""
            <div style="text-align:center; padding:2rem; color:var(--muted);">
                <div style="font-size:2rem; margin-bottom:0.5rem;">🏆</div>
                <div style="font-size:0.82rem;">No eligible invoices yet</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for w in wins[-6:][::-1]:
                st.markdown(f"""
                <div class="win-toast">
                    <span style="font-size:1.2rem;">✅</span>
                    <div>
                        <div style="font-weight:600; font-size:0.82rem; color:var(--text);">
                            +{fmt_inr(w['amount'])} added to Tax Credits!
                        </div>
                        <div style="font-size:0.7rem; color:var(--muted); margin-top:2px;">
                            {w['merchant']} · {w['date']}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)