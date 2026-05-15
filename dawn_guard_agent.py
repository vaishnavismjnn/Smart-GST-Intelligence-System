# ═══════════════════════════════════════════════════════════════════════════
# dawn_guard_agent.py  —  BEST-OF-BOTH PRODUCTION VERSION
# ═══════════════════════════════════════════════════════════════════════════
#
# PURPOSE:
#   Dawn Guard is a daily intelligence agent that:
#     1. Fetches ALL invoice records via the shared API layer (utils/api.py).
#     2. Applies deduplication + validation via cleaner.py helpers.
#     3. Runs forensic duplicate/integrity analysis (mirrors forensic_guard.py).
#     4. Computes ITC eligibility (mirrors itc_forecaster.py gate logic).
#     5. Calls Groq AI for a sharp natural-language insight paragraph.
#     6. Builds a rich Markdown + HTML brief.
#     7. Emails the brief via SMTP (optional).
#     8. Returns the brief as a Markdown string for dashboard.py to render.
#
# INTEGRATION MAP:
#   dashboard.py        → from dawn_guard_agent import run_dawn_guard_demo
#                         brief = run_dawn_guard_demo(user_email=demo_email)
#                         st.markdown(brief)
#   utils/api.py        → get_records()
#   utils/cleaner.py    → clean_amount(), deduplicate_records(), get_valid_processed()
#   utils/formatters.py → fmt_inr(), fmt_date()
#   utils/excel_builder.py → _build_excel()
#   forensic_guard.py   → _fingerprint()/_detect_duplicates()/_integrity_issues()
#                         (replicated locally — keeps agent self-contained)
#   itc_forecaster.py   → _compute_itc_eligible() mirrors Gate 5 logic exactly
#
# EMAIL:
#   Credentials: st.secrets["EMAIL_USER"] / st.secrets["EMAIL_PASS"]
#   Consistent with auth.py and api.py throughout this app.
#   Email is OPTIONAL — if secrets absent, brief is still returned as a string.
#
# AI:
#   Groq API — llama-3.3-70b-versatile, temperature 0.6, max_tokens 700.
#   Unchanged from original. Falls back to a plain message if unavailable.
#
# SAFE DEFAULTS:
#   • Never raises — all exceptions are caught and surfaced in the brief.
#   • Defensive ImportError fallbacks on every internal import.
#   • All division operations have explicit zero guards.
# ═══════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import logging
import random
import smtplib
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests

# ── Streamlit (for st.secrets only) ──────────────────────────────────────────
try:
    import streamlit as st
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False

# ── Internal imports with graceful fallbacks ──────────────────────────────────
try:
    from utils.api import get_records as _get_records
    _API_AVAILABLE = True
except ImportError:
    _get_records = None          # type: ignore
    _API_AVAILABLE = False

try:
    from utils.cleaner import (
        clean_amount,
        deduplicate_records,
        get_valid_processed,
    )
except ImportError:
    def clean_amount(x) -> float:          # type: ignore
        try:
            return float(str(x).replace(",", "").replace("₹", "").strip())
        except Exception:
            return 0.0

    def deduplicate_records(records):      # type: ignore
        return records

    def get_valid_processed(records):      # type: ignore
        return [r for r in records if isinstance(r, dict) and r.get("status") == "processed"]

try:
    from utils.formatters import fmt_inr, fmt_date
except ImportError:
    def fmt_inr(x) -> str:                # type: ignore
        return f"₹ {float(x):,.2f}" if isinstance(x, (int, float)) else str(x)

    def fmt_date(x) -> str:               # type: ignore
        return str(x) if x else "—"

try:
    from utils.excel_builder import _build_excel
    _EXCEL_AVAILABLE = True
except ImportError:
    _EXCEL_AVAILABLE = False
    _build_excel = None                    # type: ignore

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DawnGuard")


# ══════════════════════════════════════════════════════════════════════════════
# FORENSIC HELPERS
# Replicated from pages/forensic_guard.py — identical logic so Dawn Guard
# and Forensic Guard always agree on duplicate counts and integrity flags.
# ══════════════════════════════════════════════════════════════════════════════

def _fingerprint(record: dict) -> str:
    """
    Content fingerprint: MERCHANT | TOTAL_AMOUNT | INVOICE_DATE.
    Mirrors forensic_guard.py::_fingerprint() exactly.
    """
    return (
        f"{str(record.get('MERCHANT', '')).strip().lower()}"
        f"|{str(record.get('TOTAL_AMOUNT', '')).strip()}"
        f"|{str(record.get('INVOICE_DATE', '')).strip()}"
    )


def _detect_duplicates(records: list) -> dict:
    """
    Returns {fingerprint: [_id, ...]}. Entries with len > 1 are duplicate groups.
    Mirrors forensic_guard.py::_detect_duplicates() exactly.
    """
    seen: dict = {}
    for r in records:
        seen.setdefault(_fingerprint(r), []).append(r.get("_id", ""))
    return seen


def _integrity_issues(records: list) -> list:
    """Records where amounts_match is False. Mirrors forensic_guard.py."""
    return [r for r in records if r.get("validation", {}).get("amounts_match") is False]


# ══════════════════════════════════════════════════════════════════════════════
# ITC HELPER
# Mirrors itc_forecaster.py::_compute_itc() exactly:
#   get_valid_processed() → Gates 1-2-3-4-6
#   GST_AMOUNT > 0        → Gate 5
# ══════════════════════════════════════════════════════════════════════════════

def _compute_itc_eligible(records: list) -> tuple:
    """Returns (eligible_records, total_itc_float). All 6 ITC gates applied."""
    base_valid = get_valid_processed(records)
    eligible   = [r for r in base_valid if clean_amount(r.get("GST_AMOUNT")) > 0]
    total_itc  = round(sum(clean_amount(r.get("GST_AMOUNT")) for r in eligible), 2)
    return eligible, total_itc


# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCH
# ══════════════════════════════════════════════════════════════════════════════

def _safe_get_records() -> list:
    """
    Fetch records via utils/api.get_records().
    That function handles JWT, limit=1000, unwrapping, retries, and 401 expiry.
    We add an outer try/except so any unexpected failure returns [] cleanly.
    """
    if not _API_AVAILABLE or _get_records is None:
        logger.error("utils.api not importable — cannot fetch records.")
        return []
    try:
        raw = _get_records()
        return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []
    except Exception as exc:
        logger.error("get_records() failed: %s", exc)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# KPI COMPUTATION
# Uses the same pipeline as dashboard.py and itc_forecaster.py.
# ══════════════════════════════════════════════════════════════════════════════

def _compute_financials(records: list) -> dict:
    """
    Derive all financial + compliance + forensic KPIs used in the brief.
    Returns a flat dict of typed values.
    """
    _empty: dict = {
        "total_records": 0, "processed_count": 0, "valid_count": 0,
        "invalid_count": 0, "total_turnover": 0.0, "total_taxable": 0.0,
        "total_gst": 0.0, "itc_claimable": 0.0, "itc_recovery_pct": 0,
        "avg_invoice": 0.0, "compliance_pct": 0, "merchants": [],
        "top_merchant": "—", "top_merchant_amt": 0.0, "top_vendor_ratio": 0.0,
        "date_range": ("—", "—"), "high_value_count": 0,
        "zero_gst_count": 0, "dup_groups": 0, "amt_issues": 0,
        "duplicate_count": 0,
    }
    if not records:
        return _empty

    # ── Same pipeline as dashboard.py ─────────────────────────────────────────
    all_processed  = [r for r in records if r.get("status", "").lower() == "processed"]
    deduped        = deduplicate_records(records)
    processed      = [r for r in deduped if r.get("status") == "processed"]
    valid          = get_valid_processed(records)       # Gates 1–2–3–4–6
    duplicate_count = len(all_processed) - len(processed)

    # ── ITC (Gate 5 added — mirrors itc_forecaster.py) ───────────────────────
    _, itc_claimable = _compute_itc_eligible(records)

    # ── Monetary aggregates ───────────────────────────────────────────────────
    total_turnover    = sum(clean_amount(r.get("TOTAL_AMOUNT"))   for r in valid)
    total_taxable     = sum(clean_amount(r.get("TAXABLE_AMOUNT")) for r in valid)
    total_gst         = sum(clean_amount(r.get("GST_AMOUNT"))     for r in valid)
    all_processed_gst = sum(clean_amount(r.get("GST_AMOUNT"))     for r in processed)

    # ── Derived ratios ────────────────────────────────────────────────────────
    avg_invoice      = total_turnover / len(valid) if valid else 0.0
    compliance_pct   = int(len(valid) / len(processed) * 100) if processed else 0
    invalid_count    = len(processed) - len(valid)
    itc_recovery_pct = (
        min(100, int(itc_claimable / all_processed_gst * 100))
        if all_processed_gst > 0 else 0
    )

    # ── Risk indicators ───────────────────────────────────────────────────────
    high_value_count = (
        sum(1 for r in valid if clean_amount(r.get("TOTAL_AMOUNT")) > 2 * avg_invoice)
        if avg_invoice > 0 else 0
    )
    zero_gst_count = sum(1 for r in valid if clean_amount(r.get("GST_AMOUNT")) == 0)

    # ── Forensic (mirrors forensic_guard.py) ──────────────────────────────────
    fp_map     = _detect_duplicates(processed)
    dup_groups = sum(1 for ids in fp_map.values() if len(ids) > 1)
    amt_issues = len(_integrity_issues(processed))

    # ── Merchant breakdown ────────────────────────────────────────────────────
    merchant_totals: dict = defaultdict(float)
    for r in valid:
        merchant = (r.get("MERCHANT") or "Unknown").strip()
        merchant_totals[merchant] += clean_amount(r.get("TOTAL_AMOUNT"))

    merchants_sorted = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)
    top_merchant     = merchants_sorted[0][0] if merchants_sorted else "—"
    top_merchant_amt = merchants_sorted[0][1] if merchants_sorted else 0.0
    top_vendor_ratio = (
        merchant_totals[top_merchant] / total_turnover
        if total_turnover > 0 and merchant_totals else 0.0
    )

    # ── Date range ────────────────────────────────────────────────────────────
    dates = sorted(str(r.get("INVOICE_DATE")) for r in processed if r.get("INVOICE_DATE"))
    date_range = (dates[0], dates[-1]) if dates else ("—", "—")

    return {
        "total_records":    len(deduped),
        "processed_count":  len(processed),
        "valid_count":      len(valid),
        "invalid_count":    invalid_count,
        "total_turnover":   total_turnover,
        "total_taxable":    total_taxable,
        "total_gst":        total_gst,
        "itc_claimable":    itc_claimable,
        "itc_recovery_pct": itc_recovery_pct,
        "avg_invoice":      avg_invoice,
        "compliance_pct":   compliance_pct,
        "merchants":        merchants_sorted,
        "top_merchant":     top_merchant,
        "top_merchant_amt": top_merchant_amt,
        "top_vendor_ratio": top_vendor_ratio,
        "date_range":       date_range,
        "high_value_count": high_value_count,
        "zero_gst_count":   zero_gst_count,
        "dup_groups":       dup_groups,
        "amt_issues":       amt_issues,
        "duplicate_count":  duplicate_count,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GROQ AI INSIGHT
# Model / temperature / max_tokens unchanged from original dawn_guard_agent.py.
# Credentials: st.secrets["GROQ_API_KEY"] — consistent with the rest of app.
# ══════════════════════════════════════════════════════════════════════════════

def _call_groq(kpis: dict) -> Optional[str]:
    """
    Calls Groq API with a structured prompt built from KPIs.
    Returns the AI paragraph string, or None on any failure.
    """
    try:
        groq_api_key = st.secrets.get("GROQ_API_KEY") if _ST_AVAILABLE else None
    except Exception:
        groq_api_key = None

    if not groq_api_key:
        logger.warning("GROQ_API_KEY not found in st.secrets — skipping AI insight.")
        return None

    system_prompt = "You are a professional GST auditor and financial analyst."
    user_prompt   = f"""
Analyse the GST dataset and generate a concise, professional insight paragraph
for a morning intelligence brief. Focus on risks, anomalies, and one clear recommendation.

DATA:
Valid Invoices       : {kpis["valid_count"]}
Total Turnover       : ₹{kpis["total_turnover"]:,.0f}
Total GST            : ₹{kpis["total_gst"]:,.0f}
ITC Claimable        : ₹{kpis["itc_claimable"]:,.0f}
ITC Recovery Rate    : {kpis["itc_recovery_pct"]}%
Compliance Rate      : {kpis["compliance_pct"]}%
High Value Invoices  : {kpis["high_value_count"]}
Zero GST Invoices    : {kpis["zero_gst_count"]}
Vendor Concentration : {kpis["top_vendor_ratio"]:.2%}
Duplicate Groups     : {kpis["dup_groups"]}
Amount Mismatches    : {kpis["amt_issues"]}
Duplicates Removed   : {kpis["duplicate_count"]}

Keep response under 120 words. Be sharp and actionable.
""".strip()

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama-3.3-70b-versatile",
                "messages":    [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                "temperature": 0.6,
                "max_tokens":  700,
            },
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        logger.warning("Groq returned status %s", response.status_code)
        return None
    except Exception as exc:
        logger.error("Groq API call failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# BRIEF BUILDER — rich Markdown, renders in st.markdown() and email clients
# ══════════════════════════════════════════════════════════════════════════════

_MOTIVATIONAL_QUOTES = [
    "Success usually comes to those who are too busy to be looking for it. — Henry David Thoreau",
    "Opportunities don't happen. You create them. — Chris Grosser",
    "Do not wait to strike till the iron is hot; make it hot by striking. — W. B. Yeats",
    "The secret of getting ahead is getting started. — Mark Twain",
    "Risk comes from not knowing what you're doing. — Warren Buffett",
]


def _build_brief_markdown(user_email: str, kpis: dict, ai_insight: Optional[str]) -> str:
    """Render the Dawn Guard brief as a Markdown string for st.markdown()."""
    now_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y · %H:%M UTC")

    pct = kpis["compliance_pct"]
    if pct >= 90:
        health_icon, health_label = "🟢", "Excellent"
    elif pct >= 70:
        health_icon, health_label = "🟡", "Good"
    elif pct >= 50:
        health_icon, health_label = "🟠", "Needs Attention"
    else:
        health_icon, health_label = "🔴", "Critical"

    merchants = kpis.get("merchants", [])[:5]
    if merchants:
        merchant_rows = "\n| Merchant | Invoice Value |\n|---|---|\n"
        for name, amt in merchants:
            merchant_rows += f"| {name} | {fmt_inr(amt)} |\n"
    else:
        merchant_rows = "\n_No merchant data available._\n"

    ai_section = (
        ai_insight
        if ai_insight
        else "_AI insight unavailable — GROQ_API_KEY not configured or Groq unreachable._"
    )

    date_from, date_to = kpis["date_range"]
    quote = random.choice(_MOTIVATIONAL_QUOTES)

    return f"""
## 🌅 Dawn Guard — Daily Intelligence Brief

**Generated for:** `{user_email}`
**Report time:** {now_str}
**Invoice period:** {fmt_date(date_from)} → {fmt_date(date_to)}

---

### 📊 Portfolio Overview

| Metric | Value |
|---|---|
| Total Records (deduplicated) | {kpis["total_records"]} |
| Processed Invoices | {kpis["processed_count"]} |
| Fully Valid (ITC-eligible) | {kpis["valid_count"]} |
| Invalid / Non-compliant | {kpis["invalid_count"]} |

---

### 💰 Financial Summary

| Metric | Value |
|---|---|
| Total Turnover | {fmt_inr(kpis["total_turnover"])} |
| Total Taxable Amount | {fmt_inr(kpis["total_taxable"])} |
| Total GST Collected | {fmt_inr(kpis["total_gst"])} |
| **ITC Claimable** | **{fmt_inr(kpis["itc_claimable"])}** |
| Average Invoice Value | {fmt_inr(kpis["avg_invoice"])} |

---

### ✅ Compliance Status

{health_icon} **{health_label}** — {pct}% of processed invoices are ITC-eligible.

- ITC Recovery Rate: **{kpis["itc_recovery_pct"]}%**
- Valid GSTINs + Matching Amounts: **{kpis["valid_count"]} / {kpis["processed_count"]}**

---

### 🔬 Forensic Alerts

| Signal | Count |
|---|---|
| Fingerprint Duplicate Groups | {kpis["dup_groups"]} |
| Amount Mismatches | {kpis["amt_issues"]} |
| Duplicates Removed (dedup) | {kpis["duplicate_count"]} |
| High Value Invoices (>2× avg) | {kpis["high_value_count"]} |
| Zero GST Invoices | {kpis["zero_gst_count"]} |
| Top Vendor Concentration | {kpis["top_vendor_ratio"]:.1%} |

---

### 🏪 Top Merchants by Value (Valid Invoices Only)
{merchant_rows}

---

### 💡 AI Insight
{ai_section}

---

> 🔥 *{quote}*

---

> *Dawn Guard · GST Intelligence Platform · Auto-generated report*
> *Only deduplicated, validated invoices are included in financial aggregates.*
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# HTML EMAIL BUILDER
# Converts computed KPIs directly into a rich, pixel-perfect HTML email.
# Uses inline CSS (Gmail-safe), hero banner, colour-coded badges, styled
# tables, and motivational footer — no Markdown-in-<pre> hacks.
# ══════════════════════════════════════════════════════════════════════════════

def _build_email_html(user_email: str, kpis: dict, ai_insight: Optional[str], quote: str) -> str:
    """
    Build a fully self-contained, Gmail-compatible HTML email from KPIs.
    All CSS is inlined or in a <style> block compatible with major clients.
    """
    now_str    = datetime.now(timezone.utc).strftime("%A, %d %B %Y · %H:%M UTC")
    date_from, date_to = kpis["date_range"]
    date_range_str = f"{fmt_date(date_from)} → {fmt_date(date_to)}"

    # ── Compliance health badge ───────────────────────────────────────────────
    pct = kpis["compliance_pct"]
    if pct >= 90:
        health_color, health_label, health_emoji = "#00C896", "Excellent", "🟢"
    elif pct >= 70:
        health_color, health_label, health_emoji = "#F4A300", "Good", "🟡"
    elif pct >= 50:
        health_color, health_label, health_emoji = "#FF6B35", "Needs Attention", "🟠"
    else:
        health_color, health_label, health_emoji = "#E63946", "Critical", "🔴"

    # ── ITC recovery colour ───────────────────────────────────────────────────
    itc_pct = kpis["itc_recovery_pct"]
    itc_color = "#00C896" if itc_pct >= 80 else ("#F4A300" if itc_pct >= 50 else "#E63946")

    # ── Merchant rows ─────────────────────────────────────────────────────────
    merchants = kpis.get("merchants", [])[:5]
    if merchants:
        max_amt = merchants[0][1] if merchants[0][1] > 0 else 1
        merchant_rows_html = ""
        row_colors = ["#f0fffe", "#ffffff"]
        for i, (name, amt) in enumerate(merchants):
            bar_pct = int(amt / max_amt * 100)
            bg = row_colors[i % 2]
            merchant_rows_html += f"""
            <tr style="background:{bg};">
              <td style="padding:10px 14px;font-size:14px;color:#1a1a2e;border-bottom:1px solid #eef2f7;">
                <strong style="color:#007A6E;">#{i+1}</strong>&nbsp; {name}
              </td>
              <td style="padding:10px 14px;font-size:14px;color:#1a1a2e;border-bottom:1px solid #eef2f7;">
                {fmt_inr(amt)}
              </td>
              <td style="padding:10px 14px;border-bottom:1px solid #eef2f7;min-width:120px;">
                <div style="background:#e8f5f3;border-radius:20px;height:10px;overflow:hidden;">
                  <div style="background:linear-gradient(90deg,#00A896,#00C896);width:{bar_pct}%;height:10px;border-radius:20px;"></div>
                </div>
              </td>
            </tr>"""
    else:
        merchant_rows_html = """
            <tr><td colspan="3" style="padding:12px;color:#999;font-style:italic;">No merchant data available.</td></tr>"""

    # ── AI insight block ──────────────────────────────────────────────────────
    ai_html = (
        f'<p style="margin:0;font-size:15px;line-height:1.8;color:#2d3748;">{ai_insight}</p>'
        if ai_insight
        else '<p style="margin:0;font-size:14px;color:#999;font-style:italic;">AI insight unavailable — GROQ_API_KEY not configured or Groq unreachable.</p>'
    )

    # ── Forensic alert pills ──────────────────────────────────────────────────
    def _alert_pill(label: str, value, warn_if_nonzero: bool = True) -> str:
        color = "#E63946" if (warn_if_nonzero and int(value) > 0) else "#00C896"
        bg    = "#fff5f5" if (warn_if_nonzero and int(value) > 0) else "#f0fffe"
        return f"""
        <td style="padding:8px;text-align:center;">
          <div style="background:{bg};border:1px solid {color};border-radius:10px;padding:10px 8px;">
            <div style="font-size:22px;font-weight:700;color:{color};">{value}</div>
            <div style="font-size:11px;color:#555;margin-top:2px;">{label}</div>
          </div>
        </td>"""

    # ── Build KPI summary cards ───────────────────────────────────────────────
    def _kpi_card(icon: str, label: str, value: str, sub: str = "") -> str:
        return f"""
        <td style="padding:8px;" width="25%">
          <div style="background:#ffffff;border-radius:12px;padding:16px 12px;text-align:center;border:1px solid #eef2f7;box-shadow:0 2px 8px rgba(0,168,150,0.07);">
            <div style="font-size:28px;margin-bottom:4px;">{icon}</div>
            <div style="font-size:18px;font-weight:700;color:#00A896;">{value}</div>
            <div style="font-size:11px;color:#888;margin-top:3px;">{label}</div>
            {f'<div style="font-size:10px;color:#aaa;margin-top:2px;">{sub}</div>' if sub else ''}
          </div>
        </td>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Dawn Guard Brief</title>
</head>
<body style="margin:0;padding:0;background:#edf2f7;font-family:'Segoe UI',Arial,sans-serif;">

<!-- Wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" style="background:#edf2f7;">
<tr><td align="center" style="padding:32px 16px;">

<!-- Main Card -->
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.12);">

  <!-- ═══ HERO BANNER ═══ -->
  <tr>
    <td style="background:linear-gradient(135deg,#004d45 0%,#00A896 60%,#00d4b8 100%);padding:0;">
      <!-- Sky & sun illustration via SVG -->
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding:36px 36px 28px 36px;position:relative;">
            <!-- Decorative circles -->
            <div style="position:absolute;top:16px;right:36px;width:80px;height:80px;background:rgba(255,220,80,0.18);border-radius:50%;"></div>
            <div style="position:absolute;top:28px;right:48px;width:56px;height:56px;background:rgba(255,220,80,0.28);border-radius:50%;"></div>
            <div style="position:absolute;top:38px;right:58px;width:36px;height:36px;background:rgba(255,220,80,0.55);border-radius:50%;"></div>
            <!-- Brand -->
            <div style="font-size:11px;font-weight:600;letter-spacing:3px;color:rgba(255,255,255,0.7);text-transform:uppercase;margin-bottom:8px;">GST Intelligence Platform</div>
            <div style="font-size:32px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;line-height:1.1;">🌅 Dawn Guard</div>
            <div style="font-size:16px;color:rgba(255,255,255,0.85);margin-top:6px;font-weight:300;">Daily Intelligence Brief</div>
            <div style="margin-top:18px;display:inline-block;background:rgba(255,255,255,0.15);border-radius:20px;padding:6px 16px;">
              <span style="font-size:12px;color:#ffffff;">📅 {now_str}</span>
            </div>
            <div style="margin-top:8px;">
              <span style="font-size:12px;color:rgba(255,255,255,0.7);">📬 {user_email}</span>
              &nbsp;&nbsp;
              <span style="font-size:12px;color:rgba(255,255,255,0.7);">📁 Period: {date_range_str}</span>
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══ COMPLIANCE HEALTH BANNER ═══ -->
  <tr>
    <td style="background:{health_color};padding:14px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <span style="font-size:15px;font-weight:700;color:#ffffff;">{health_emoji} Compliance Health: {health_label}</span>
            <span style="font-size:13px;color:rgba(255,255,255,0.85);margin-left:12px;">{pct}% of invoices are ITC-eligible</span>
          </td>
          <td align="right">
            <div style="background:rgba(255,255,255,0.25);border-radius:20px;height:10px;width:140px;display:inline-block;overflow:hidden;vertical-align:middle;">
              <div style="background:#ffffff;width:{pct}%;height:10px;border-radius:20px;"></div>
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══ KPI SUMMARY CARDS ═══ -->
  <tr>
    <td style="padding:28px 28px 8px 28px;background:#f8fcfb;">
      <div style="font-size:13px;font-weight:700;letter-spacing:2px;color:#00A896;text-transform:uppercase;margin-bottom:14px;">📊 Portfolio Overview</div>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_kpi_card("🗂️", "Total Records", str(kpis['total_records']), "Deduplicated")}
          {_kpi_card("✅", "Valid Invoices", str(kpis['valid_count']), "ITC-eligible")}
          {_kpi_card("⚠️", "Non-compliant", str(kpis['invalid_count']), "Require action")}
          {_kpi_card("🔁", "Dupes Removed", str(kpis['duplicate_count']), "Auto-cleaned")}
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══ FINANCIAL SUMMARY ═══ -->
  <tr>
    <td style="padding:20px 28px;">
      <div style="font-size:13px;font-weight:700;letter-spacing:2px;color:#00A896;text-transform:uppercase;margin-bottom:14px;">💰 Financial Summary</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:12px;overflow:hidden;border:1px solid #eef2f7;">
        <tr style="background:linear-gradient(90deg,#004d45,#00A896);">
          <th style="padding:12px 16px;text-align:left;font-size:13px;color:#ffffff;font-weight:600;">Metric</th>
          <th style="padding:12px 16px;text-align:right;font-size:13px;color:#ffffff;font-weight:600;">Value</th>
        </tr>
        <tr style="background:#f8fcfb;">
          <td style="padding:11px 16px;font-size:14px;color:#444;border-bottom:1px solid #eef2f7;">Total Turnover</td>
          <td style="padding:11px 16px;font-size:14px;font-weight:600;color:#1a1a2e;text-align:right;border-bottom:1px solid #eef2f7;">{fmt_inr(kpis['total_turnover'])}</td>
        </tr>
        <tr style="background:#ffffff;">
          <td style="padding:11px 16px;font-size:14px;color:#444;border-bottom:1px solid #eef2f7;">Total Taxable Amount</td>
          <td style="padding:11px 16px;font-size:14px;font-weight:600;color:#1a1a2e;text-align:right;border-bottom:1px solid #eef2f7;">{fmt_inr(kpis['total_taxable'])}</td>
        </tr>
        <tr style="background:#f8fcfb;">
          <td style="padding:11px 16px;font-size:14px;color:#444;border-bottom:1px solid #eef2f7;">Total GST Collected</td>
          <td style="padding:11px 16px;font-size:14px;font-weight:600;color:#1a1a2e;text-align:right;border-bottom:1px solid #eef2f7;">{fmt_inr(kpis['total_gst'])}</td>
        </tr>
        <tr style="background:linear-gradient(90deg,#f0fffe,#e6faf8);">
          <td style="padding:13px 16px;font-size:15px;font-weight:700;color:#007A6E;border-bottom:1px solid #eef2f7;">⚡ ITC Claimable</td>
          <td style="padding:13px 16px;font-size:15px;font-weight:800;color:#00A896;text-align:right;border-bottom:1px solid #eef2f7;">{fmt_inr(kpis['itc_claimable'])}</td>
        </tr>
        <tr style="background:#ffffff;">
          <td style="padding:11px 16px;font-size:14px;color:#444;">Average Invoice Value</td>
          <td style="padding:11px 16px;font-size:14px;font-weight:600;color:#1a1a2e;text-align:right;">{fmt_inr(kpis['avg_invoice'])}</td>
        </tr>
      </table>

      <!-- ITC Recovery Rate progress bar -->
      <div style="margin-top:16px;background:#f0fffe;border-radius:12px;padding:14px 18px;border:1px solid #d0f0eb;">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
          <span style="font-size:13px;color:#555;font-weight:600;">ITC Recovery Rate</span>
          <span style="font-size:13px;font-weight:800;color:{itc_color};">{itc_pct}%</span>
        </div>
        <div style="background:#d4ede9;border-radius:20px;height:12px;overflow:hidden;">
          <div style="background:linear-gradient(90deg,{itc_color},{itc_color}99);width:{itc_pct}%;height:12px;border-radius:20px;"></div>
        </div>
      </div>
    </td>
  </tr>

  <!-- ═══ FORENSIC ALERTS ═══ -->
  <tr>
    <td style="padding:8px 28px 20px 28px;">
      <div style="font-size:13px;font-weight:700;letter-spacing:2px;color:#00A896;text-transform:uppercase;margin-bottom:14px;">🔬 Forensic Alerts</div>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_alert_pill("Duplicate Groups", kpis['dup_groups'])}
          {_alert_pill("Amount Mismatches", kpis['amt_issues'])}
          {_alert_pill("High-Value Invoices", kpis['high_value_count'])}
          {_alert_pill("Zero GST Invoices", kpis['zero_gst_count'])}
          {_alert_pill("Vendor Concentration", f"{kpis['top_vendor_ratio']:.0%}", warn_if_nonzero=False)}
        </tr>
      </table>
      <div style="margin-top:10px;font-size:11px;color:#aaa;text-align:center;">🔴 Red = action required &nbsp;|&nbsp; 🟢 Green = all clear</div>
    </td>
  </tr>

  <!-- ═══ TOP MERCHANTS ═══ -->
  <tr>
    <td style="padding:8px 28px 20px 28px;">
      <div style="font-size:13px;font-weight:700;letter-spacing:2px;color:#00A896;text-transform:uppercase;margin-bottom:14px;">🏪 Top Merchants by Value</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:12px;overflow:hidden;border:1px solid #eef2f7;">
        <tr style="background:linear-gradient(90deg,#004d45,#00A896);">
          <th style="padding:11px 14px;text-align:left;font-size:13px;color:#fff;font-weight:600;">Merchant</th>
          <th style="padding:11px 14px;text-align:left;font-size:13px;color:#fff;font-weight:600;">Invoice Value</th>
          <th style="padding:11px 14px;text-align:left;font-size:13px;color:#fff;font-weight:600;">Share</th>
        </tr>
        {merchant_rows_html}
      </table>
    </td>
  </tr>

  <!-- ═══ AI INSIGHT ═══ -->
  <tr>
    <td style="padding:8px 28px 24px 28px;">
      <div style="background:linear-gradient(135deg,#f0fffe,#e8f5f3);border-radius:14px;padding:22px 24px;border-left:5px solid #00A896;border:1px solid #c8ede9;border-left:5px solid #00A896;">
        <div style="font-size:13px;font-weight:700;letter-spacing:2px;color:#00A896;text-transform:uppercase;margin-bottom:12px;">💡 AI Insight · Groq LLaMA</div>
        {ai_html}
      </div>
    </td>
  </tr>

  <!-- ═══ MOTIVATIONAL QUOTE ═══ -->
  <tr>
    <td style="padding:0 28px 28px 28px;">
      <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:14px;padding:20px 24px;text-align:center;">
        <div style="font-size:18px;margin-bottom:8px;">✨</div>
        <div style="font-size:14px;color:#a0c4c0;font-style:italic;line-height:1.7;">&ldquo;{quote}&rdquo;</div>
      </div>
    </td>
  </tr>

  <!-- ═══ FOOTER ═══ -->
  <tr>
    <td style="background:#f8fcfb;border-top:1px solid #eef2f7;padding:20px 36px;text-align:center;">
      <div style="font-size:12px;color:#00A896;font-weight:700;letter-spacing:1px;">🌅 DAWN GUARD · GST Intelligence Platform</div>
      <div style="font-size:11px;color:#aaa;margin-top:6px;">Auto-generated report · Only deduplicated, validated invoices are included in financial aggregates.</div>
      <div style="font-size:11px;color:#ccc;margin-top:4px;">© {datetime.now().year} Dawn Guard · Powered by Groq AI</div>
    </td>
  </tr>

</table>
<!-- /Main Card -->

</td></tr>
</table>
<!-- /Wrapper -->

</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL DELIVERY
# Uses st.secrets (EMAIL_USER, EMAIL_PASS) — consistent with auth.py / api.py.
# Sends plain-text + rich HTML multipart so all email clients render correctly.
# ══════════════════════════════════════════════════════════════════════════════

def _send_email(
    recipient: str,
    subject: str,
    brief_md: str,
    kpis: Optional[dict] = None,
    ai_insight: Optional[str] = None,
    quote: str = "",
) -> bool:
    """
    Send the brief via Gmail SMTP (TLS, port 587).
    When kpis are supplied the email renders as a rich visual HTML brief;
    otherwise falls back to the Markdown plain-text body.
    Returns True on success, False on any failure. Never raises.
    """
    try:
        email_user = st.secrets.get("EMAIL_USER") if _ST_AVAILABLE else None
        email_pass = st.secrets.get("EMAIL_PASS") if _ST_AVAILABLE else None
    except Exception:
        email_user = email_pass = None

    if not email_user or not email_pass:
        logger.warning("Email skipped — EMAIL_USER / EMAIL_PASS not in st.secrets.")
        return False

    # Build rich HTML if KPIs are available, else minimal fallback
    if kpis:
        html_body = _build_email_html(recipient, kpis, ai_insight, quote or "")
    else:
        html_body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body  {{font-family:'Segoe UI',Arial,sans-serif;background:#edf2f7;padding:20px;}}
  .card {{background:#fff;border-radius:16px;padding:32px;max-width:640px;
          margin:0 auto;box-shadow:0 4px 24px rgba(0,0,0,0.10);}}
  pre   {{white-space:pre-wrap;font-family:'Segoe UI',Arial,sans-serif;
          line-height:1.8;font-size:14px;color:#2d3748;}}
  .footer{{font-size:11px;color:#aaa;margin-top:24px;text-align:center;}}
</style></head>
<body><div class="card">
  <pre>{brief_md}</pre>
  <div class="footer">🌅 Dawn Guard · GST Intelligence Platform</div>
</div></body></html>"""

    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = email_user
        msg["To"]      = recipient
        msg.attach(MIMEText(brief_md,  "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html",  "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(email_user, email_pass)
            server.sendmail(email_user, recipient, msg.as_string())

        logger.info("Dawn Guard email delivered → %s", recipient)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth failed. Check EMAIL_USER / EMAIL_PASS in st.secrets.")
    except smtplib.SMTPException as exc:
        logger.error("SMTP error: %s", exc)
    except Exception as exc:
        logger.error("Unexpected email error: %s\n%s", exc, traceback.format_exc())
    return False


# ══════════════════════════════════════════════════════════════════════════════
# EXCEL HELPER — uses the shared excel_builder (same export as dashboard)
# ══════════════════════════════════════════════════════════════════════════════

def _build_excel_bytes(valid_records: list) -> Optional[bytes]:
    """Build a styled .xlsx workbook. Returns None on failure."""
    if not _EXCEL_AVAILABLE or _build_excel is None or not valid_records:
        return None
    try:
        return _build_excel(valid_records, title="Dawn Guard — Valid Invoices Brief")
    except Exception as exc:
        logger.warning("Excel build failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def run_dawn_guard(user_email: str, send_email: bool = True) -> str:
    """
    Full Dawn Guard pipeline.

      1. Fetch records via utils/api.get_records().
      2. Compute financial + compliance + forensic KPIs.
      3. Call Groq AI for an insight paragraph.
      4. Build Markdown brief.
      5. Send email if send_email=True and st.secrets are configured.
      6. Return brief as a Markdown string.

    Never raises — all errors are caught and surfaced in the returned string.
    """
    logger.info("Dawn Guard starting for %s", user_email)

    try:
        records = _safe_get_records()
    except Exception as exc:
        logger.error("Record fetch failed: %s", exc)
        return (
            f"## ⚠️ Dawn Guard Error\n\n"
            f"Failed to fetch records: `{exc}`\n\n"
            f"```\n{traceback.format_exc()}\n```"
        )

    if not records:
        return (
            "## 🌅 Dawn Guard\n\n"
            "No invoice records found. Upload and process invoices to generate a brief."
        )

    try:
        kpis = _compute_financials(records)
    except Exception as exc:
        logger.error("KPI computation failed: %s", exc)
        kpis = {
            k: 0 for k in [
                "total_records", "processed_count", "valid_count", "invalid_count",
                "total_turnover", "total_taxable", "total_gst", "itc_claimable",
                "itc_recovery_pct", "avg_invoice", "compliance_pct", "top_merchant",
                "top_merchant_amt", "high_value_count", "zero_gst_count",
                "top_vendor_ratio", "dup_groups", "amt_issues", "duplicate_count",
            ]
        }
        kpis["merchants"]  = []
        kpis["date_range"] = ("—", "—")

    ai_insight = _call_groq(kpis)
    quote      = random.choice(_MOTIVATIONAL_QUOTES)
    brief      = _build_brief_markdown(user_email, kpis, ai_insight)

    if send_email:
        date_str = datetime.now().strftime("%d %b %Y")
        _send_email(
            recipient=user_email,
            subject=f"🌅 Dawn Guard Brief · {date_str} · GST Intelligence",
            brief_md=brief,
            kpis=kpis,
            ai_insight=ai_insight,
            quote=quote,
        )

    logger.info("Dawn Guard complete for %s", user_email)
    return brief


def run_dawn_guard_demo(user_email: str) -> str:
    """
    Demo entry point called from dashboard.py.
    Sends the email (matching original behaviour) and returns the brief.

    dashboard.py usage:
        from dawn_guard_agent import run_dawn_guard_demo
        brief = run_dawn_guard_demo(user_email=demo_email)
        st.markdown(brief)
    """
    return run_dawn_guard(user_email=user_email, send_email=True)


# ══════════════════════════════════════════════════════════════════════════════
# CLI / CRON ENTRY POINT
# Usage: python dawn_guard_agent.py user@example.com
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    target_email = sys.argv[1] if len(sys.argv) > 1 else ""
    if not target_email:
        print("Usage: python dawn_guard_agent.py <user_email>")
        sys.exit(1)

    print(run_dawn_guard(user_email=target_email, send_email=True))