# --- file: pages/upload.py ---
# ═══════════════════════════════════════════════════════════════════════════════
# UPLOAD PAGE — Production-Grade Implementation
#
# TWO MODES:
#   1. Manual Upload  — single invoice via file uploader.
#                       Results have: Copy to Clipboard + Download Result buttons.
#   2. Batch Upload   — multi-file uploader (entire folder contents or any
#                       selection). Processes files one-by-one with a live feed.
#                       On completion a PDF report can be downloaded.
#
# BATCH INTEGRATION:
#   batch_processor.py exposes:
#       run_batch(uploaded_files, token, base_url, delay_between, skip_errors, callbacks)
#   where callbacks = {
#       "on_start":    fn(total_files),
#       "on_file":     fn(index, filename, status, data),
#       "on_complete": fn(summary_dict),
#   }
#
#   generate_batch_pdf_report(summary) → bytes
#       Returns raw PDF bytes for st.download_button().
#
# NEW FEATURES (this revision):
#   • Manual mode  → "Copy to Clipboard" button (JS clipboard API via st.components)
#                  → "Download Result (JSON)" button
#   • Batch mode   → Multi-file uploader (user selects all files from a folder)
#                  → Live processing feed (unchanged UX)
#                  → "Download PDF Report" button on completion
# ═══════════════════════════════════════════════════════════════════════════════

import json
import streamlit as st
import time
import os

from utils.api import process_invoice, BASE_URL
from utils.auth import is_authenticated
from components.cards import result_card
from components.illustrations import upload_illustration, render_illustration
from utils.formatters import fmt_inr
from utils.cleaner import clean_amount

ALLOWED_TYPES = ["png", "jpg", "jpeg", "webp", "bmp", "tiff"]

PIPELINE = [
    ("📡", "Transmit",  "Sending to Render server"),
    ("🔍", "OCR",       "Tesseract text extraction"),
    ("✅", "Validate",  "GSTIN & amount checks"),
    ("💾", "Persist",   "MongoDB + Cloudinary"),
]

# ─────────────────────────────────────────────────────────────────────────────
# PAGE-LEVEL STYLES
# ─────────────────────────────────────────────────────────────────────────────
_UPLOAD_CSS = """
<style>
/* ── Upload Zone ── */
.upload-zone {
    position: relative;
    border: 2px dashed rgba(0,212,170,0.35);
    border-radius: 20px;
    padding: 2.5rem 2rem;
    text-align: center;
    background: linear-gradient(135deg,
        rgba(0,212,170,0.03) 0%,
        rgba(0,168,150,0.06) 100%);
    transition: border-color 0.3s, background 0.3s, transform 0.2s;
    overflow: hidden;
}
.upload-zone::before {
    content: '';
    position: absolute;
    inset: -2px;
    border-radius: 20px;
    background: linear-gradient(90deg,
        transparent 0%, rgba(0,212,170,0.15) 50%, transparent 100%);
    background-size: 200% 100%;
    animation: border-shimmer 3s linear infinite;
    pointer-events: none;
}
@keyframes border-shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position:  200% 0; }
}
.upload-zone:hover {
    border-color: rgba(0,212,170,0.7);
    background: linear-gradient(135deg,
        rgba(0,212,170,0.06) 0%, rgba(0,168,150,0.10) 100%);
    transform: translateY(-2px);
}
.upload-icon {
    font-size: 3.5rem;
    line-height: 1;
    margin-bottom: 0.75rem;
    filter: drop-shadow(0 0 16px rgba(0,212,170,0.5));
    animation: float-icon 3s ease-in-out infinite;
}
@keyframes float-icon {
    0%, 100% { transform: translateY(0);    }
    50%      { transform: translateY(-8px); }
}
.upload-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #EDF2F7;
    margin-bottom: 0.3rem;
    letter-spacing: -0.01em;
}
.upload-sub {
    font-size: 0.75rem;
    color: #718096;
    line-height: 1.5;
}
.format-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    justify-content: center;
    margin-top: 1rem;
}
.format-chip {
    font-size: 0.62rem;
    padding: 0.2rem 0.55rem;
    border-radius: 20px;
    background: rgba(0,212,170,0.08);
    border: 1px solid rgba(0,212,170,0.2);
    color: #00D4AA;
    font-family: 'DM Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* ── File Preview Card ── */
.file-preview-card {
    background: rgba(0,212,170,0.04);
    border: 1px solid rgba(0,212,170,0.18);
    border-radius: 14px;
    padding: 1rem 1.25rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 0.75rem 0;
    transition: border-color 0.2s;
}
.file-preview-card:hover { border-color: rgba(0,212,170,0.4); }
.file-icon-box {
    width: 44px; height: 44px;
    border-radius: 10px;
    background: linear-gradient(135deg,#00D4AA,#00A896);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.4rem;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(0,212,170,0.3);
}
.file-meta-name {
    font-weight: 700;
    font-size: 0.88rem;
    color: #EDF2F7;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 240px;
}
.file-meta-sub {
    font-size: 0.7rem;
    color: #718096;
    margin-top: 2px;
    font-family: 'DM Mono', monospace;
}
.file-badge {
    margin-left: auto;
    font-size: 0.62rem;
    padding: 0.25rem 0.6rem;
    border-radius: 20px;
    background: rgba(0,212,170,0.12);
    border: 1px solid rgba(0,212,170,0.3);
    color: #00D4AA;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    flex-shrink: 0;
}

/* ── Pipeline Stepper ── */
.pipeline-wrap {
    display: flex;
    align-items: center;
    gap: 0;
    padding: 1rem 0;
    position: relative;
}
.pipe-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    flex: 1;
    position: relative;
    z-index: 1;
}
.pipe-dot {
    width: 38px; height: 38px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    border: 2px solid rgba(0,212,170,0.2);
    background: rgba(0,212,170,0.05);
    color: #4A5568;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    transition: all 0.4s;
    position: relative;
    z-index: 2;
}
.pipe-dot.done {
    background: rgba(0,212,170,0.15);
    border-color: #00D4AA;
    color: #00D4AA;
}
.pipe-dot.active {
    background: rgba(0,212,170,0.2);
    border-color: #00D4AA;
    color: #00D4AA;
    box-shadow: 0 0 0 4px rgba(0,212,170,0.15), 0 0 20px rgba(0,212,170,0.3);
    animation: pulse-step 1.2s ease-in-out infinite;
}
@keyframes pulse-step {
    0%, 100% { box-shadow: 0 0 0 4px rgba(0,212,170,0.15), 0 0 20px rgba(0,212,170,0.3); }
    50%       { box-shadow: 0 0 0 8px rgba(0,212,170,0.08), 0 0 35px rgba(0,212,170,0.5); }
}
.pipe-label {
    font-size: 0.62rem;
    color: #4A5568;
    text-align: center;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    transition: color 0.4s;
}
.pipe-label.active { color: #00D4AA; }
.pipe-label.done   { color: #718096; }
.pipe-connector {
    flex: 1;
    height: 2px;
    background: rgba(0,212,170,0.1);
    margin-bottom: 1.4rem;
    position: relative;
    overflow: hidden;
}
.pipe-connector.done {
    background: linear-gradient(90deg,#00D4AA,#00A896);
}
.pipe-connector.active::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg,transparent,rgba(0,212,170,0.6),transparent);
    animation: scan-line 1s linear infinite;
}
@keyframes scan-line {
    0%   { transform: translateX(-100%); }
    100% { transform: translateX(100%);  }
}

/* ── Stage Status Box ── */
.stage-box {
    background: rgba(0,212,170,0.06);
    border: 1px solid rgba(0,212,170,0.18);
    border-left: 3px solid #00D4AA;
    border-radius: 10px;
    padding: 0.85rem 1.1rem;
    margin-top: 0.5rem;
    animation: slide-in 0.3s ease;
}
@keyframes slide-in {
    from { opacity:0; transform:translateY(6px); }
    to   { opacity:1; transform:translateY(0);   }
}
.stage-label {
    font-weight: 700;
    font-size: 0.88rem;
    color: #EDF2F7;
}
.stage-desc {
    font-size: 0.72rem;
    color: #718096;
    margin-top: 2px;
}

/* ── Result Card Overrides ── */
.result-success-banner {
    background: linear-gradient(135deg,
        rgba(0,212,170,0.12) 0%, rgba(0,168,150,0.06) 100%);
    border: 1px solid rgba(0,212,170,0.3);
    border-left: 4px solid #00D4AA;
    border-radius: 14px;
    padding: 1rem 1.25rem;
    display: flex;
    align-items: center;
    gap: 0.85rem;
    margin-bottom: 1rem;
    animation: slide-in 0.4s ease;
}
.result-field-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
    margin: 1rem 0;
}
.result-field {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 0.65rem 0.85rem;
    transition: border-color 0.2s, background 0.2s;
}
.result-field:hover {
    border-color: rgba(0,212,170,0.25);
    background: rgba(0,212,170,0.04);
}
.result-field-key {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #4A5568;
    font-weight: 700;
    margin-bottom: 0.3rem;
}
.result-field-val {
    font-size: 0.85rem;
    color: #EDF2F7;
    font-family: 'DM Mono', monospace;
    word-break: break-all;
}
.result-field-val.accent { color: #00D4AA; font-weight: 700; }

/* ── Mode Toggle ── */
.mode-toggle-wrap {
    display: flex;
    gap: 0;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 4px;
    margin-bottom: 1.5rem;
    width: fit-content;
}
.mode-btn {
    padding: 0.45rem 1.25rem;
    border-radius: 9px;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}
.mode-btn.active {
    background: linear-gradient(135deg,#00D4AA,#00A896);
    color: #060D1F;
    box-shadow: 0 4px 12px rgba(0,212,170,0.3);
}
.mode-btn.inactive { color: #718096; background: transparent; }

/* ── Batch / Agent Progress ── */
.agent-file-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.55rem 0.75rem;
    border-radius: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    font-size: 0.8rem;
    transition: background 0.15s;
    animation: slide-in 0.25s ease;
}
.agent-file-row:hover { background: rgba(255,255,255,0.02); }
.agent-file-idx {
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    color: #4A5568;
    width: 24px;
    text-align: right;
    flex-shrink: 0;
}
.agent-file-name {
    flex: 1;
    color: #CBD5E0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.agent-status-ok   { color: #00D4AA; font-size: 0.72rem; font-weight: 700; flex-shrink:0; }
.agent-status-err  { color: #FF4D6D; font-size: 0.72rem; font-weight: 700; flex-shrink:0; }
.agent-status-spin { color: #F5C842; font-size: 0.72rem; font-weight: 700; flex-shrink:0; }

.agent-summary-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin-top: 1rem;
}
.agent-summary-cell {
    background: rgba(0,212,170,0.05);
    border: 1px solid rgba(0,212,170,0.15);
    border-radius: 10px;
    padding: 0.85rem;
    text-align: center;
}
.agent-summary-val {
    font-size: 1.3rem;
    font-weight: 700;
    font-family: 'DM Mono', monospace;
    color: #00D4AA;
}
.agent-summary-lbl {
    font-size: 0.65rem;
    color: #4A5568;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-top: 3px;
}

/* ── Batch uploader hint ── */
.batch-hint-card {
    background: rgba(0,212,170,0.04);
    border: 1px solid rgba(0,212,170,0.18);
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}
.batch-hint-title {
    font-size: 0.78rem;
    font-weight: 700;
    color: #A0AEC0;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.75rem;
}

/* ── Section Title ── */
.upload-section-title {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #4A5568;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 1rem;
}

/* ── Image Preview Wrapper ── */
.img-preview-wrap {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid rgba(0,212,170,0.18);
    margin: 0.75rem 0;
    max-height: 320px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.3);
}

/* ── Validation Badges ── */
.val-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.3rem 0.75rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
}
.val-badge.ok  { background: rgba(0,212,170,0.12); border:1px solid rgba(0,212,170,0.3); color:#00D4AA; }
.val-badge.bad { background: rgba(255,77,109,0.12); border:1px solid rgba(255,77,109,0.3); color:#FF4D6D; }

/* ── Action buttons row ── */
.action-btn-row {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 0.75rem;
}
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ext_icon(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "?"
    return {"png": "🖼️", "jpg": "🖼️", "jpeg": "🖼️",
            "webp": "🌐", "bmp": "🗃️", "tiff": "📷"}.get(ext, "📄")


def _render_pipeline(active_step: int) -> None:
    """Animated multi-step pipeline stepper."""
    steps_html = ""
    for i, (icon, label, _) in enumerate(PIPELINE):
        if i < active_step:
            dot_cls, label_cls, dot_inner = "done", "done", "✓"
        elif i == active_step:
            dot_cls, label_cls, dot_inner = "active", "active", icon
        else:
            dot_cls, label_cls, dot_inner = "", "", str(i + 1)

        steps_html += f"""
        <div class="pipe-step">
            <div class="pipe-dot {dot_cls}">{dot_inner}</div>
            <div class="pipe-label {label_cls}">{label}</div>
        </div>"""

        if i < len(PIPELINE) - 1:
            conn_cls = "done" if i < active_step else ("active" if i == active_step else "")
            steps_html += f'<div class="pipe-connector {conn_cls}"></div>'

    st.markdown(f'<div class="pipeline-wrap">{steps_html}</div>', unsafe_allow_html=True)


def _build_clipboard_text(data: dict) -> str:
    """Produce a clean plain-text copy of the extracted invoice data."""
    extracted   = data.get("extracted") or data
    validation  = data.get("validation") or data.get("extracted", {}).get("validation") or {}

    lines = [
        "── GST Intelligence Platform · Invoice Result ──",
        f"Merchant       : {extracted.get('MERCHANT', '—')}",
        f"GSTIN          : {extracted.get('GSTIN', '—')}",
        f"Invoice Number : {extracted.get('INVOICE_NO', '—')}",
        f"Invoice Date   : {extracted.get('INVOICE_DATE', '—')}",
        f"Total Amount   : {extracted.get('TOTAL_AMOUNT', '—')}",
        f"Taxable Amount : {extracted.get('TAXABLE_AMOUNT', '—')}",
        f"GST Amount     : {extracted.get('GST_AMOUNT', '—')}",
        f"GSTIN Valid    : {'Yes' if validation.get('gst_valid') else 'No'}",
        f"Amounts Match  : {'Yes' if validation.get('amounts_match') else 'No'}",
    ]
    cloud_url = data.get("cloudinary_url")
    if cloud_url:
        lines.append(f"Cloudinary URL : {cloud_url}")
    return "\n".join(lines)


def _inject_clipboard_js(text: str) -> None:
    """
    Inject a small JS snippet that calls navigator.clipboard.writeText().
    Rendered via st.components.v1.html so it executes immediately.
    Uses JSON.dumps for safe escaping — no backtick or template-literal issues.
    """
    import streamlit.components.v1 as components
    safe_js_str = json.dumps(text)  # produces a properly escaped JS string literal
    js = f"""
    <script>
    (function() {{
        var txt = {safe_js_str};
        navigator.clipboard.writeText(txt).then(function() {{
            // success — no visible feedback needed; Streamlit shows st.toast
        }}, function(err) {{
            console.error('Clipboard write failed', err);
        }});
    }})();
    </script>
    """
    components.html(js, height=0, scrolling=False)


def _build_client_report(data: dict) -> str:
    """Generate a professional plain-text invoice report for client readability."""
    extracted  = data.get("extracted") or data
    validation = data.get("validation") or data.get("extracted", {}).get("validation") or {}

    merchant    = extracted.get("MERCHANT",       "—")
    gstin       = extracted.get("GSTIN",          "—")
    inv_no      = extracted.get("INVOICE_NO",     "—")
    inv_date    = extracted.get("INVOICE_DATE",   "—")
    total_amt   = extracted.get("TOTAL_AMOUNT",   "—")
    taxable_amt = extracted.get("TAXABLE_AMOUNT", "—")
    gst_amt     = extracted.get("GST_AMOUNT",     "—")
    gst_valid   = "Yes" if validation.get("gst_valid") else "No"
    amt_match   = "Yes" if validation.get("amounts_match") else "No"

    separator = "=" * 48
    thin_sep  = "-" * 48

    lines = [
        separator,
        "  GST INTELLIGENCE PLATFORM -- INVOICE REPORT",
        separator,
        "",
        f"  Merchant Name   : {merchant}",
        f"  GSTIN           : {gstin}",
        "",
        thin_sep,
        "  INVOICE DETAILS",
        thin_sep,
        f"  Invoice Number  : {inv_no}",
        f"  Invoice Date    : {inv_date}",
        "",
        thin_sep,
        "  AMOUNTS",
        thin_sep,
        f"  Total Amount    : {total_amt}",
        f"  Taxable Amount  : {taxable_amt}",
        f"  GST Amount      : {gst_amt}",
        "",
        thin_sep,
        "  VALIDATION",
        thin_sep,
        f"  GSTIN Valid     : {gst_valid}",
        f"  Amounts Match   : {amt_match}",
        "",
        separator,
        "  Generated by GST Intelligence Platform",
        separator,
    ]
    return "\n".join(lines)


def _render_result(data: dict) -> None:
    """Rich extracted-data result panel."""
    validation  = data.get("validation") or data.get("extracted", {}).get("validation") or {}
    extracted   = data.get("extracted") or data
    gstin       = extracted.get("GSTIN",          data.get("GSTIN",          "—"))
    merchant    = extracted.get("MERCHANT",        data.get("MERCHANT",       "—"))
    total_amt   = extracted.get("TOTAL_AMOUNT",    data.get("TOTAL_AMOUNT",   "—"))
    taxable_amt = extracted.get("TAXABLE_AMOUNT",  data.get("TAXABLE_AMOUNT", "—"))
    gst_amt     = extracted.get("GST_AMOUNT",      data.get("GST_AMOUNT",     "—"))
    inv_date    = extracted.get("INVOICE_DATE",    data.get("INVOICE_DATE",   "—"))
    inv_no      = extracted.get("INVOICE_NO",      data.get("INVOICE_NO",     "—"))
    gst_valid   = validation.get("gst_valid",    False)
    amt_match   = validation.get("amounts_match", False)

    gst_badge = (
        '<span class="val-badge ok">✓ GSTIN Valid</span>'
        if gst_valid else
        '<span class="val-badge bad">✗ GSTIN Invalid</span>'
    )
    amt_badge = (
        '<span class="val-badge ok">✓ Amounts Match</span>'
        if amt_match else
        '<span class="val-badge bad">✗ Amount Mismatch</span>'
    )

    total_fmt = fmt_inr(clean_amount(total_amt))   if total_amt   not in ("—", None, "") else "—"
    tax_fmt   = fmt_inr(clean_amount(taxable_amt)) if taxable_amt not in ("—", None, "") else "—"
    gst_fmt   = fmt_inr(clean_amount(gst_amt))     if gst_amt     not in ("—", None, "") else "—"

    st.markdown(f"""
    <div class="result-success-banner">
        <div style="width:40px;height:40px;border-radius:50%;
                    background:rgba(0,212,170,0.15);border:2px solid #00D4AA;
                    display:flex;align-items:center;justify-content:center;
                    font-size:1.3rem;flex-shrink:0;">✅</div>
        <div>
            <div style="font-weight:700;color:#EDF2F7;font-size:0.9rem;">
                {data.get("message", "Invoice processed successfully")}
            </div>
            <div style="font-size:0.72rem;color:#718096;margin-top:2px;">
                Data extracted · GSTIN validated · Saved to MongoDB + Cloudinary
            </div>
        </div>
        <div style="margin-left:auto;display:flex;gap:0.4rem;flex-wrap:wrap;justify-content:flex-end;">
            {gst_badge}&nbsp;{amt_badge}
        </div>
    </div>

    <div class="upload-section-title">Extracted Invoice Data</div>

    <div class="result-field-grid">
        <div class="result-field">
            <div class="result-field-key">Merchant</div>
            <div class="result-field-val">{merchant}</div>
        </div>
        <div class="result-field">
            <div class="result-field-key">GSTIN</div>
            <div class="result-field-val" style="font-size:0.75rem;">{gstin}</div>
        </div>
        <div class="result-field">
            <div class="result-field-key">Invoice Number</div>
            <div class="result-field-val">{inv_no}</div>
        </div>
        <div class="result-field">
            <div class="result-field-key">Invoice Date</div>
            <div class="result-field-val">{inv_date}</div>
        </div>
        <div class="result-field">
            <div class="result-field-key">Total Amount</div>
            <div class="result-field-val accent">{total_fmt}</div>
        </div>
        <div class="result-field">
            <div class="result-field-key">Taxable Amount</div>
            <div class="result-field-val">{tax_fmt}</div>
        </div>
        <div class="result-field" style="grid-column:1/-1;">
            <div class="result-field-key">GST Amount</div>
            <div class="result-field-val accent">{gst_fmt}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Action buttons — Copy to Clipboard + Download JSON ────────────────────
    st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
    st.markdown('<div class="upload-section-title">Actions</div>', unsafe_allow_html=True)

    btn_col1, btn_col2 = st.columns(2)

    # Copy to clipboard
    with btn_col1:
        if st.button("📋  Copy to Clipboard", use_container_width=True,
                     key="copy_result_btn"):
            clip_text = _build_clipboard_text(data)
            _inject_clipboard_js(clip_text)
            st.toast("✅ Result copied to clipboard!", icon="📋")

    # Download as plain-text client report
    with btn_col2:
        report_bytes = _build_client_report(data).encode("utf-8")
        st.download_button(
            label="⬇  Download Result (JSON)",
            data=report_bytes,
            file_name="invoice_report.txt",
            mime="text/plain",
            use_container_width=True,
            key="download_result_btn",
        )


# ─────────────────────────────────────────────────────────────────────────────
# MANUAL UPLOAD MODE
# ─────────────────────────────────────────────────────────────────────────────

def _render_manual_mode() -> None:
    col_left, col_right = st.columns([1.05, 1], gap="large")

    with col_left:
        st.markdown("""
        <div class="upload-zone">
            <div class="upload-icon">🧾</div>
            <div class="upload-title">Drop your invoice here</div>
            <div class="upload-sub">
                Supports PNG, JPG, WEBP, BMP, TIFF · Up to 10 MB<br>
                OCR extraction starts immediately after upload
            </div>
            <div class="format-chips">
                <span class="format-chip">PNG</span>
                <span class="format-chip">JPG</span>
                <span class="format-chip">WEBP</span>
                <span class="format-chip">BMP</span>
                <span class="format-chip">TIFF</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Choose invoice image",
            type=ALLOWED_TYPES,
            label_visibility="collapsed",
            key="manual_uploader",
        )

        if uploaded_file:
            st.markdown(f"""
            <div class="file-preview-card">
                <div class="file-icon-box">{_ext_icon(uploaded_file.name)}</div>
                <div>
                    <div class="file-meta-name">{uploaded_file.name}</div>
                    <div class="file-meta-sub">{uploaded_file.size / 1024:.1f} KB · {uploaded_file.type}</div>
                </div>
                <div class="file-badge">Ready</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="img-preview-wrap">', unsafe_allow_html=True)
            st.image(uploaded_file, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("🚀  Process Invoice", use_container_width=True,
                         type="primary", key="manual_process_btn"):
                _run_manual_pipeline(uploaded_file)

        elif "last_result" not in st.session_state:
            st.markdown("""
            <div style="text-align:center;padding:1.5rem 0;color:#4A5568;font-size:0.8rem;">
                No file selected yet — use the chooser above
            </div>
            """, unsafe_allow_html=True)

        if "last_result" in st.session_state:
            if st.button("↩ Clear & Upload Another", use_container_width=True,
                         key="clear_result_btn"):
                del st.session_state["last_result"]
                st.rerun()

    with col_right:
        last = st.session_state.get("last_result")
        if last:
            _render_result(last)
        else:
            st.markdown("""
            <div style="height:2rem"></div>
            <div class="upload-section-title">What happens after upload</div>
            """, unsafe_allow_html=True)
            for icon, step, detail in [
                ("📡", "1 · Transmit",  "Image bytes sent securely to Render backend over HTTPS"),
                ("🔍", "2 · OCR",       "Tesseract engine extracts all text fields from the invoice"),
                ("✅", "3 · Validate",  "GSTIN format check + taxable + GST = total reconciliation"),
                ("💾", "4 · Persist",   "Record saved flat into MongoDB; image stored on Cloudinary CDN"),
            ]:
                st.markdown(f"""
                <div style="display:flex;gap:1rem;padding:0.9rem;
                            border-bottom:1px solid rgba(255,255,255,0.04);
                            transition:background 0.15s;border-radius:8px;"
                     onmouseover="this.style.background='rgba(0,212,170,0.04)'"
                     onmouseout="this.style.background='transparent'">
                    <span style="font-size:1.3rem;flex-shrink:0;">{icon}</span>
                    <div>
                        <div style="font-weight:700;font-size:0.8rem;color:#CBD5E0;
                                    margin-bottom:3px;">{step}</div>
                        <div style="font-size:0.72rem;color:#4A5568;line-height:1.5;">{detail}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)


def _run_manual_pipeline(uploaded_file) -> None:
    """Runs the 4-step pipeline animation then calls the API."""
    prog_ph    = st.empty()
    stepper_ph = st.empty()
    stage_ph   = st.empty()

    for i, (icon, label, desc) in enumerate(PIPELINE):
        pct = int((i + 1) / len(PIPELINE) * 80)
        prog_ph.progress(pct, text=f"{label} …")
        with stepper_ph.container():
            _render_pipeline(i)
        stage_ph.markdown(f"""
        <div class="stage-box">
            <div class="stage-label">{icon} &nbsp;{label}</div>
            <div class="stage-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        time.sleep(0.45)

    try:
        status, data = process_invoice(uploaded_file.getvalue(), uploaded_file.name)
    except Exception as e:
        prog_ph.empty(); stepper_ph.empty(); stage_ph.empty()
        st.error(f"🔴 Connection error: {e}")
        return

    prog_ph.progress(100, text="Complete!")
    time.sleep(0.3)
    prog_ph.empty(); stepper_ph.empty(); stage_ph.empty()

    if status == 200:
        st.session_state["last_result"] = data
        st.rerun()
    elif status == 422:
        st.error(f"🔴 OCR Failed: {data.get('detail', 'Extraction failed — try a clearer image.')}")
    elif status == 503:
        st.error("🔴 Backend unreachable. The server may be waking up — wait 30 s and retry.")
    elif status == 401:
        st.error("🔴 Session expired. Please log out and log back in.")
    else:
        st.error(f"🔴 Error {status}: {data}")


# ─────────────────────────────────────────────────────────────────────────────
# BATCH UPLOAD MODE
# ─────────────────────────────────────────────────────────────────────────────

def _render_batch_mode() -> None:
    """
    UI for Batch Upload.

    Users select multiple image files (or all files from a folder) via the
    Streamlit multi-file uploader.  Files are sent to the backend one-by-one
    with a live progress feed.  On completion a PDF report can be downloaded.
    """
    # ── Info / how-to panel ───────────────────────────────────────────────────
    st.markdown("""
    <div class="batch-hint-card">
        <div class="batch-hint-title">📁 Batch Upload — How To Select a Folder</div>
        <div style="font-size:0.78rem;color:#718096;line-height:1.7;">
            <b style="color:#A0AEC0;">Windows:</b>
            Open File Explorer → navigate to your invoices folder →
            press <code>Ctrl + A</code> to select all → drag into the uploader below, or click
            <i>Browse files</i> and use <code>Ctrl + A</code> inside the folder.<br>
            <b style="color:#A0AEC0;">Mac:</b>
            Open Finder → navigate to the folder → press <code>Cmd + A</code> →
            drag into the uploader, or use <i>Browse files</i> with <code>Cmd + A</code>.<br>
            <b style="color:#A0AEC0;">Supported formats:</b>
            PNG · JPG · JPEG · WEBP · BMP · TIFF
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Multi-file uploader ───────────────────────────────────────────────────
    st.markdown("""
    <div class="upload-zone" style="margin-bottom:1rem;">
        <div class="upload-icon">📂</div>
        <div class="upload-title">Select invoice images</div>
        <div class="upload-sub">
            Choose multiple files or all files from a folder<br>
            Each image will be processed individually
        </div>
        <div class="format-chips">
            <span class="format-chip">PNG</span>
            <span class="format-chip">JPG</span>
            <span class="format-chip">WEBP</span>
            <span class="format-chip">BMP</span>
            <span class="format-chip">TIFF</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Select invoice images for batch processing",
        type=ALLOWED_TYPES,
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="batch_uploader",
    )

    if uploaded_files:
        total_size = sum(f.size for f in uploaded_files)
        st.markdown(f"""
        <div class="file-preview-card">
            <div class="file-icon-box">📦</div>
            <div>
                <div class="file-meta-name">{len(uploaded_files)} file(s) selected</div>
                <div class="file-meta-sub">{total_size / 1024:.1f} KB total</div>
            </div>
            <div class="file-badge">Queued</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Settings ──────────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    delay_s = col_a.slider(
        "Delay between files (seconds)",
        min_value=0.5, max_value=5.0, value=1.0, step=0.5,
        key="batch_delay",
        help="Prevents rate-limiting on the Render free tier.",
    )
    skip_errors = col_b.checkbox(
        "Skip errors and continue",
        value=True,
        key="batch_skip_errors",
        help="If unchecked the batch stops on the first API error.",
    )

    # ── Info strip ────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:rgba(245,200,66,0.06);border:1px solid rgba(245,200,66,0.2);
                border-radius:10px;padding:0.75rem 1rem;font-size:0.75rem;
                color:#A0AEC0;line-height:1.6;margin-bottom:1rem;">
        <b style="color:#F5C842;">ℹ️ Batch Mode</b>&nbsp; Each selected image is submitted
        individually to the <code>/process</code> endpoint — the same pipeline used by
        Manual Upload.  Results stream live below.  A full PDF report can be downloaded
        once the batch completes.  Your JWT session token is forwarded automatically.
    </div>
    """, unsafe_allow_html=True)

    # ── Launch button ─────────────────────────────────────────────────────────
    if st.button("⚡ Start Batch Processing", use_container_width=True,
                 type="primary", key="batch_launch_btn"):
        if not uploaded_files:
            st.error("Please select at least one image file before starting.")
            return
        _run_batch(uploaded_files, delay_s=delay_s, skip_errors=skip_errors)


def _run_batch(uploaded_files: list, delay_s: float, skip_errors: bool) -> None:
    """
    Imports batch_processor and runs it with live Streamlit callbacks.
    On completion, stores the summary in session_state for PDF download.
    """
    try:
        from batch_processor import run_batch, generate_batch_pdf_report
    except ImportError as e:
        st.error(
            f"🔴 batch_processor.py not found or has an import error: `{e}`\n\n"
            "Make sure `batch_processor.py` is in the project root."
        )
        return

    token = st.session_state.get("token", "")
    if not token:
        st.error("🔴 No auth token found. Please log in first.")
        return

    # ── Live progress containers ──────────────────────────────────────────────
    header_ph  = st.empty()
    prog_ph    = st.empty()
    feed_ph    = st.container()
    summary_ph = st.empty()

    file_rows: list[dict] = []
    total_files: list[int] = [0]   # mutable container for closure

    def on_start(total: int) -> None:
        total_files[0] = total
        header_ph.markdown(f"""
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
            <div style="width:36px;height:36px;border-radius:50%;
                        background:rgba(0,212,170,0.15);border:2px solid #00D4AA;
                        display:flex;align-items:center;justify-content:center;
                        font-size:1rem;">⚡</div>
            <div>
                <div style="font-weight:700;color:#EDF2F7;">Batch Processing Running</div>
                <div style="font-size:0.72rem;color:#718096;">
                    {total} invoice{'s' if total != 1 else ''} queued · processing sequentially
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        prog_ph.progress(0, text="Starting …")

    def on_file(index: int, filename: str, status: str, data) -> None:
        file_rows.append({"index": index, "filename": filename,
                          "status": status, "data": data})
        with feed_ph:
            _render_batch_feed(file_rows)

        total_known = total_files[0] or max(r["index"] for r in file_rows)
        done_count  = sum(1 for r in file_rows if r["status"] in ("ok", "error"))
        if total_known > 0:
            pct = int(done_count / total_known * 100)
            prog_ph.progress(min(pct, 99), text=f"Processing {filename} …")

    def on_complete(summary: dict) -> None:
        prog_ph.progress(100, text="Done!")
        _render_batch_summary(summary_ph, summary)
        # Store summary and PDF bytes for the download button
        st.session_state["batch_summary"] = summary
        try:
            pdf_bytes = generate_batch_pdf_report(summary)
            st.session_state["batch_pdf"] = pdf_bytes
        except Exception as pdf_err:
            st.session_state["batch_pdf"] = None
            st.warning(f"⚠️ PDF report generation failed: {pdf_err}")

    callbacks = {
        "on_start":    on_start,
        "on_file":     on_file,
        "on_complete": on_complete,
    }

    try:
        run_batch(
            uploaded_files=uploaded_files,
            token=token,
            base_url=BASE_URL,
            delay_between=delay_s,
            skip_errors=skip_errors,
            callbacks=callbacks,
        )
    except Exception as e:
        st.error(f"🔴 Batch error: {e}")
        return

    # ── PDF download button (rendered after run completes) ────────────────────
    pdf_bytes = st.session_state.get("batch_pdf")
    if pdf_bytes:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        st.download_button(
            label="📄  Download PDF Report",
            data=pdf_bytes,
            file_name="batch_invoice_report.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
            key="batch_pdf_download_btn",
        )


def _render_batch_feed(rows: list) -> None:
    """Renders the live per-file status feed in a single compact fixed-height window."""
    rows_html = ""
    for r in rows[-50:]:
        idx, fname, status = r["index"], r["filename"], r["status"]
        if status == "processing":
            icon, color = "⟳", "#F5C842"
        elif status == "ok":
            icon, color = "✓", "#00D4AA"
        else:
            icon, color = "✗", "#FF4D6D"

        rows_html += (
            f'<div style="display:flex;align-items:center;gap:0.6rem;'
            f'padding:0.3rem 0.5rem;border-bottom:1px solid rgba(255,255,255,0.04);'
            f'font-size:0.75rem;">'
            f'<span style="color:#4A5568;font-family:monospace;width:20px;text-align:right;flex-shrink:0;">#{idx}</span>'
            f'<span style="flex:1;color:#CBD5E0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{fname}</span>'
            f'<span style="color:{color};font-weight:700;flex-shrink:0;">{icon}</span>'
            f'</div>'
        )

    html = (
        '<div style="border:1px solid rgba(0,212,170,0.18);border-radius:10px;'
        'overflow:hidden;margin-top:0.5rem;">'
        '<div style="background:rgba(0,212,170,0.06);padding:0.4rem 0.75rem;'
        'font-size:0.62rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;'
        'color:#4A5568;border-bottom:1px solid rgba(255,255,255,0.06);">Live Feed</div>'
        f'<div style="max-height:160px;overflow-y:auto;padding:0.25rem 0.5rem;">{rows_html}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_batch_summary(placeholder, summary: dict) -> None:
    """Renders the batch completion summary card."""
    total    = summary.get("total",    0)
    ok_count = summary.get("ok",       0)
    err_cnt  = summary.get("errors",   0)
    skipped  = summary.get("skipped",  0)
    duration = summary.get("duration_s", 0)
    err_col  = "#FF4D6D" if err_cnt > 0 else "#00D4AA"

    with placeholder.container():
        st.markdown(f"""
        <div class="glass-card" style="margin-top:1rem;">
            <div class="upload-section-title">Batch Complete · Summary</div>
            <div class="agent-summary-grid">
                <div class="agent-summary-cell">
                    <div class="agent-summary-val">{total}</div>
                    <div class="agent-summary-lbl">Files Processed</div>
                </div>
                <div class="agent-summary-cell">
                    <div class="agent-summary-val" style="color:#00D4AA;">{ok_count}</div>
                    <div class="agent-summary-lbl">Uploaded OK</div>
                </div>
                <div class="agent-summary-cell">
                    <div class="agent-summary-val" style="color:{err_col};">{err_cnt}</div>
                    <div class="agent-summary-lbl">Errors</div>
                </div>
            </div>
            <div style="margin-top:0.75rem;font-size:0.75rem;color:#4A5568;text-align:center;">
                {skipped} file(s) skipped &nbsp;·&nbsp; completed in {duration:.1f}s
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def show() -> None:
    if not is_authenticated():
        st.warning("Please log in.")
        return

    st.markdown(_UPLOAD_CSS, unsafe_allow_html=True)

    # ── Page Header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="page-header">
        <div class="page-title">📤 Upload Invoice</div>
        <div class="page-sub">
            Upload → OCR → Validate → Store &nbsp;·&nbsp; Manual or Batch Processing
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Mode selector ─────────────────────────────────────────────────────────
    if "upload_mode" not in st.session_state:
        st.session_state["upload_mode"] = "Manual Upload"

    mode_col, _ = st.columns([2, 3])
    with mode_col:
        chosen = st.radio(
            "Upload mode",
            ["Manual Upload", "Batch Upload"],
            horizontal=True,
            label_visibility="collapsed",
            key="upload_mode_radio",
        )
    st.session_state["upload_mode"] = chosen

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if chosen == "Manual Upload":
        _render_manual_mode()
    else:
        _render_batch_mode()