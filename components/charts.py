# --- file: components/charts.py ---
import plotly.graph_objects as go
from collections import Counter
from datetime import datetime, timedelta
from utils.formatters import short_id  # single source of truth — avoids duplication


def _safe_num(v) -> float:
    """
    Safe numeric parse for chart data — handles OCR strings like '1,800',
    None, empty string, and garbage without crashing.
    Intentionally inlined here to keep charts.py self-contained
    (avoids circular import through utils.cleaner → pandas at import time).
    """
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = v.replace(",", "").strip()
        if not cleaned:
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0

P = {
    "bg":     "#060D1F",
    "card":   "#0B1628",
    "accent": "#00D4AA",
    "accent2":"#00A896",
    "gold":   "#F5C842",
    "err":    "#FF4D6D",
    "muted":  "#A0AEC0",
    "border": "rgba(0,212,170,0.1)",
    "grid":   "rgba(255,255,255,0.04)",
}

BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans, sans-serif", color=P["muted"], size=11),
    margin=dict(l=10, r=10, t=40, b=10),
    hoverlabel=dict(
        bgcolor="#0B1628",
        bordercolor="rgba(0,212,170,0.3)",
        font=dict(family="DM Sans", color="#EDF2F7", size=12)
    ),
)

def bar_invoices_last30(records: list):
    today      = datetime.now().date()
    date_range = [(today - timedelta(days=i)) for i in range(29, -1, -1)]
    counts     = Counter({d: 0 for d in date_range})

    for r in records:
        raw = r.get("INVOICE_DATE") or r.get("date")
        if not raw:
            continue
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                d = datetime.strptime(str(raw), fmt).date()
                if d in counts:
                    counts[d] += 1
                break
            except ValueError:
                continue

    labels = [d.strftime("%d %b") for d in date_range]
    y_vals = [counts[d] for d in date_range]
    colors = [P["accent"] if v > 0 else "rgba(0,212,170,0.15)" for v in y_vals]

    fig = go.Figure(go.Bar(
        x=labels, y=y_vals,
        marker=dict(
            color=colors,
            line=dict(width=0),
            cornerradius=4,
        ),
        hovertemplate="<b>%{x}</b><br>%{y} invoice(s)<extra></extra>",
    ))

    fig.update_layout(
        **BASE,
        title=dict(
            text="Invoice Volume — Last 30 Days",
            font=dict(size=13, color="#EDF2F7", family="DM Sans"),
            x=0, xanchor="left", pad=dict(l=0)
        ),
        xaxis=dict(
            showgrid=False, tickfont=dict(size=9),
            showline=False, zeroline=False,
        ),
        yaxis=dict(
            showgrid=True, gridcolor=P["grid"],
            tickfont=dict(size=9), zeroline=False,
        ),
        bargap=0.35,
    )
    return fig

def donut_gst_validity(records: list):
    processed = [r for r in records if r.get("validation")]
    valid     = sum(1 for r in processed if r["validation"].get("gst_valid") is True)
    invalid   = len(processed) - valid

    if valid == 0 and invalid == 0:
        valid, invalid = 1, 0

    fig = go.Figure(go.Pie(
        labels=["Valid GSTIN", "Invalid GSTIN"],
        values=[valid, invalid],
        hole=0.65,
        marker=dict(
            colors=[P["accent"], P["err"]],
            line=dict(color="rgba(0,0,0,0)", width=0)
        ),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>",
        pull=[0.03, 0],
    ))

    pct = f"{(valid/(valid+invalid)*100):.0f}%" if (valid+invalid) > 0 else "—"
    fig.update_layout(
        **BASE,
        title=dict(
            text="GSTIN Validity",
            font=dict(size=13, color="#EDF2F7", family="DM Sans"),
            x=0, xanchor="left"
        ),
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.2,
            xanchor="center", x=0.5,
            font=dict(size=10),
        ),
        annotations=[dict(
            text=f"<b>{pct}</b><br><span style='font-size:10px;color:#A0AEC0'>Valid</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color=P["accent"], family="DM Sans"),
        )],
    )
    return fig

def line_gst_trend(records: list):
    dated = []
    for r in records:
        raw = r.get("INVOICE_DATE") or r.get("date")
        amt = _safe_num(r.get("GST_AMOUNT"))   # FIX: was float(r.get(...) or 0) — crashes on '1,800'
        if not raw:
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
    dates  = [str(d) for d, _ in dated]
    running, cumulative = 0, []
    for _, a in dated:
        running += a
        cumulative.append(running)

    fig = go.Figure()

    # Area fill
    fig.add_trace(go.Scatter(
        x=dates, y=cumulative,
        mode="lines",
        line=dict(color=P["accent"], width=2.5),
        fill="tozeroy",
        fillcolor="rgba(0,212,170,0.06)",
        hovertemplate="<b>%{x}</b><br>Cumulative GST: ₹%{y:,.2f}<extra></extra>",
        name="Cumulative GST",
    ))

    # Dots at data points
    fig.add_trace(go.Scatter(
        x=dates, y=cumulative,
        mode="markers",
        marker=dict(color=P["accent"], size=6, line=dict(color="#060D1F", width=2)),
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.update_layout(
        **BASE,
        title=dict(
            text="Cumulative GST Collected",
            font=dict(size=13, color="#EDF2F7", family="DM Sans"),
            x=0, xanchor="left"
        ),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=9)),
        yaxis=dict(showgrid=True, gridcolor=P["grid"], zeroline=False, tickfont=dict(size=9)),
        showlegend=False,
    )
    return fig

def bar_amount_breakdown(records: list):
    """Stacked bar: Taxable vs GST per record (last 10)."""
    recent = [r for r in records if r.get("TOTAL_AMOUNT")][-10:]
    if not recent:
        return None

    labels  = [r.get("MERCHANT", short_id(r.get("_id", "")))[:12] for r in recent]
    # FIX: was r.get("TAXABLE_AMOUNT") or 0 — passes OCR strings straight to Plotly
    taxable = [_safe_num(r.get("TAXABLE_AMOUNT")) for r in recent]
    gst_amt = [_safe_num(r.get("GST_AMOUNT"))     for r in recent]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Taxable", x=labels, y=taxable,
        marker=dict(color=P["accent"], cornerradius=4, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>Taxable: ₹%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="GST", x=labels, y=gst_amt,
        marker=dict(color=P["gold"], cornerradius=4, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>GST: ₹%{y:,.2f}<extra></extra>",
    ))

    fig.update_layout(
        **BASE,
        barmode="stack",
        title=dict(
            text="Taxable vs GST — Recent 10",
            font=dict(size=13, color="#EDF2F7", family="DM Sans"),
            x=0, xanchor="left"
        ),
        xaxis=dict(showgrid=False, tickfont=dict(size=9), tickangle=-30),
        yaxis=dict(showgrid=True, gridcolor=P["grid"], tickfont=dict(size=9)),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=10)
        ),
        bargap=0.3,
    )
    return fig

# short_id is imported from utils.formatters above — single definition, no duplication.