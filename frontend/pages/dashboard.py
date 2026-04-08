# --- file: pages/dashboard.py ---
import streamlit as st
from utils.api import get_records
from utils.auth import is_authenticated
from components.cards import render_kpi_strip, activity_item
from components.charts import bar_invoices_last30, donut_gst_validity, line_gst_trend, bar_amount_breakdown
from utils.formatters import fmt_inr
from datetime import datetime

CHART_CFG = {"displayModeBar": False, "responsive": True}

def _render_live_ticker(records):
    """Scrolling ticker of recent invoice merchants."""
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

def _render_insight_bar(records):
    """Quick insight strip with contextual financial facts."""
    processed = [r for r in records if r.get("status") == "processed"]
    if not processed:
        return
    total_gst = sum(r.get("GST_AMOUNT", 0) or 0 for r in processed)
    valid_pct  = int(sum(1 for r in processed if r.get("validation", {}).get("gst_valid")) / len(processed) * 100) if processed else 0
    avg        = sum(r.get("TOTAL_AMOUNT", 0) or 0 for r in processed) / len(processed) if processed else 0

    insights = [
        ("🏛️", f"Total ITC claimable: {fmt_inr(total_gst)}"),
        ("📈", f"GSTIN compliance: {valid_pct}%"),
        ("💡", f"Avg invoice: {fmt_inr(avg)}"),
        ("📅", f"Last updated: {datetime.now().strftime('%d %b %Y, %H:%M')}"),
    ]

    cols = st.columns(4, gap="small")
    for i, (icon, text) in enumerate(insights):
        cols[i].markdown(f"""
        <div style="background:rgba(0,212,170,0.04); border:1px solid rgba(0,212,170,0.1);
                    border-radius:10px; padding:0.6rem 0.85rem;
                    display:flex; align-items:center; gap:0.5rem;
                    transition:border-color 0.2s;"
             onmouseover="this.style.borderColor='rgba(0,212,170,0.25)'"
             onmouseout="this.style.borderColor='rgba(0,212,170,0.1)'">
            <span style="font-size:1rem;">{icon}</span>
            <span style="color:#A0AEC0; font-size:0.75rem; line-height:1.3;">{text}</span>
        </div>
        """, unsafe_allow_html=True)

def show():
    if not is_authenticated():
        st.warning("Please log in.")
        return

    user = st.session_state.get("user", "").split("@")[0].replace(".", " ").title()

    # Page header
    st.markdown(f"""
    <div class="page-header">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
                <div class="page-title">
                    Welcome back, {user} 👋
                </div>
                <div class="page-sub">
                    Real-time GST invoice intelligence · {datetime.now().strftime('%A, %d %B %Y')}
                </div>
            </div>
            <div style="display:flex; gap:0.75rem; align-items:center;">
                <div style="background:rgba(0,212,170,0.08); border:1px solid rgba(0,212,170,0.15);
                            border-radius:10px; padding:0.5rem 1rem; text-align:right;">
                    <div style="font-size:0.62rem; color:#A0AEC0; text-transform:uppercase;
                                letter-spacing:0.08em;">Backend</div>
                    <div style="font-size:0.78rem; color:#00D4AA; font-weight:600;">
                        <span class="pulse-dot" style="width:6px;height:6px;"></span>
                        &nbsp;Render API Live
                    </div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(""):
        records = get_records()

    # Live ticker
    _render_live_ticker(records)

    # KPI Strip
    render_kpi_strip(records)

    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

    # Insight bar
    _render_insight_bar(records)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # Charts row 1
    col_bar, col_donut = st.columns([2.2, 1], gap="medium")
    with col_bar:
        st.markdown('<div class="glass-card fade-up-d1" style="padding:1.25rem 1.5rem;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📊 Invoice Volume</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_invoices_last30(records), use_container_width=True, config=CHART_CFG)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_donut:
        st.markdown('<div class="glass-card fade-up-d2" style="padding:1.25rem 1.5rem;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🎯 GSTIN Validity</div>', unsafe_allow_html=True)
        st.plotly_chart(donut_gst_validity(records), use_container_width=True, config=CHART_CFG)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # Charts row 2
    col_trend, col_stack = st.columns([1, 1], gap="medium")
    with col_trend:
        fig_line = line_gst_trend(records)
        if fig_line:
            st.markdown('<div class="glass-card fade-up-d1" style="padding:1.25rem 1.5rem;">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">📈 GST Collection Trend</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_line, use_container_width=True, config=CHART_CFG)
            st.markdown('</div>', unsafe_allow_html=True)

    with col_stack:
        fig_stack = bar_amount_breakdown(records)
        if fig_stack:
            st.markdown('<div class="glass-card fade-up-d2" style="padding:1.25rem 1.5rem;">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">💰 Amount Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_stack, use_container_width=True, config=CHART_CFG)
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # Bottom row
    col_activity, col_summary = st.columns([1.5, 1], gap="medium")

    with col_activity:
        st.markdown('<div class="glass-card fade-up">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">⚡ Recent Activity</div>', unsafe_allow_html=True)
        recent = [r for r in records if r.get("status") == "processed"][-5:][::-1]

        if not recent:
            from components.illustrations import empty_records_illustration, render_illustration
            render_illustration(empty_records_illustration())
        else:
            for rec in recent:
                activity_item(rec)

        st.markdown('</div>', unsafe_allow_html=True)

    with col_summary:
        st.markdown('<div class="glass-card fade-up">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🏦 Financial Summary</div>', unsafe_allow_html=True)

        processed = [r for r in records if r.get("TOTAL_AMOUNT")]
        if processed:
            total_turnover = sum(r.get("TOTAL_AMOUNT", 0) or 0 for r in processed)
            avg_invoice    = total_turnover / len(processed)
            total_taxable  = sum(r.get("TAXABLE_AMOUNT", 0) or 0 for r in processed)
            total_gst      = sum(r.get("GST_AMOUNT", 0) or 0 for r in processed)

            for label, val, icon, color in [
                ("Total Turnover",  fmt_inr(total_turnover), "💰", "#00D4AA"),
                ("Avg Invoice",     fmt_inr(avg_invoice),    "📊", "#00D4AA"),
                ("Total Taxable",   fmt_inr(total_taxable),  "📋", "#00D4AA"),
                ("Total GST (ITC)", fmt_inr(total_gst),      "🏛️", "#F5C842"),
            ]:
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            padding:0.75rem 0.5rem; border-bottom:1px solid rgba(255,255,255,0.05);
                            border-radius:6px; transition:background 0.15s; cursor:default;"
                     onmouseover="this.style.background='rgba(0,212,170,0.04)'"
                     onmouseout="this.style.background='transparent'">
                    <div style="display:flex; align-items:center; gap:0.5rem;">
                        <span style="font-size:0.95rem;">{icon}</span>
                        <span style="color:#A0AEC0; font-size:0.82rem;">{label}</span>
                    </div>
                    <span style="color:{color}; font-weight:700; font-size:0.9rem;
                                 font-family:'DM Mono',monospace;">{val}</span>
                </div>
                """, unsafe_allow_html=True)

            # Mini ITC ring
            valid_gst = sum(r.get("GST_AMOUNT", 0) or 0 for r in processed
                            if r.get("validation", {}).get("gst_valid") and
                               r.get("validation", {}).get("amounts_match"))
            pct = min(100, int(valid_gst / total_gst * 100)) if total_gst > 0 else 0

            st.markdown(f"""
            <div style="margin-top:1rem; padding:1rem; background:rgba(0,212,170,0.04);
                        border:1px solid rgba(0,212,170,0.12); border-radius:12px;
                        text-align:center;">
                <div style="font-size:0.68rem; color:#A0AEC0; text-transform:uppercase;
                            letter-spacing:0.1em; margin-bottom:0.5rem;">
                    ITC Eligible GST
                </div>
                <div style="font-size:1.4rem; font-weight:700; color:#F5C842;
                            font-family:'DM Mono',monospace;">{fmt_inr(valid_gst)}</div>
                <div style="font-size:0.72rem; color:#4A5568; margin-top:0.25rem;">
                    {pct}% of total GST claimable
                </div>
                <div style="height:4px; background:rgba(0,212,170,0.1); border-radius:4px;
                            margin-top:0.75rem; overflow:hidden;">
                    <div style="height:100%; width:{pct}%;
                                background:linear-gradient(90deg,#00D4AA,#F5C842);
                                border-radius:4px; transition:width 1s ease;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── ADDED: Excel Export button (Section 3.5 + Section 9.2) ──
            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            try:
                from utils.excel_builder import _build_excel          # --- ADDED ---
                excel_bytes = _build_excel(                            # --- ADDED ---
                    records,                                           # --- ADDED ---
                    title="GST Intelligence — All Invoices"            # --- ADDED ---
                )                                                      # --- ADDED ---
                st.download_button(                                    # --- ADDED ---
                    label="📊 Export All as Excel",                    # --- ADDED ---
                    data=excel_bytes,                                  # --- ADDED ---
                    file_name="gst_all_invoices.xlsx",                 # --- ADDED ---
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # --- ADDED ---
                    use_container_width=True,                          # --- ADDED ---
                    key="dashboard_excel_export",                      # --- ADDED ---
                )                                                      # --- ADDED ---
            except Exception as e:                                     # --- ADDED ---
                st.error(f"Excel export error: {e}")                   # --- ADDED ---
            # ── END ADDED ──────────────────────────────────────────────

        else:
            from components.illustrations import analytics_illustration, render_illustration
            render_illustration(analytics_illustration(), "Upload invoices to see financial summary")

        st.markdown('</div>', unsafe_allow_html=True)