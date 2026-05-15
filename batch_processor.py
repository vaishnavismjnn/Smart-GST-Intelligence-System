# ═══════════════════════════════════════════════════════════════════════════════
# batch_processor.py
# ═══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE:
#   Batch-process every invoice image that a user uploads through the Streamlit
#   UI — no local folder path required.  Files are uploaded as a multi-file
#   selection directly in the browser and are sent to the GST Intelligence
#   Platform backend (/process endpoint) one-by-one, exactly as the manual
#   single-upload path in pages/upload.py does.
#
# REPLACES:  folder_upload_agent.py
#   The "agent" concept (server-side filesystem discovery) is removed in favour
#   of browser-based batch upload so the app works correctly when deployed to
#   Streamlit Cloud, Render, or any container that has no access to the user's
#   local file-system.
#
# INTEGRATION WITH upload.py:
#   upload.py imports and calls:
#
#       from batch_processor import run_batch
#
#       summary = run_batch(
#           uploaded_files = st.session_state["batch_files"],   # list[UploadedFile]
#           token          = st.session_state["token"],          # JWT from auth
#           base_url       = BASE_URL,                           # from utils/api.py
#           delay_between  = 1.0,                                # seconds between files
#           skip_errors    = True,                               # continue on failure
#           callbacks      = {
#               "on_start":    fn(total_files: int),
#               "on_file":     fn(index, filename, status, data),
#               "on_complete": fn(summary_dict),
#           },
#       )
#
# CALLBACK CONTRACT:
#   on_start(total: int)
#       Called once before processing begins.  `total` = number of queued files.
#
#   on_file(index: int, filename: str, status: str, data: dict | str)
#       Called twice per file:
#         1. status="processing" — just before the HTTP request is fired
#         2. status="ok"         — succeeded; `data` = API response dict
#            status="error"      — failed;    `data` = error message string
#
#   on_complete(summary: dict)
#       Called once when all files have been processed.
#       summary keys: total, ok, errors, skipped, duration_s, results
#
# SUPPORTED FORMATS:
#   PNG, JPG, JPEG, WEBP, BMP, TIFF — mirrors ALLOWED_TYPES in pages/upload.py
#
# MIME-TYPE MAPPING:
#   Mirrors what process_invoice() in utils/api.py sends so the backend always
#   receives the identical Content-Type header regardless of upload path.
#
# ERROR HANDLING:
#   • Individual file errors are caught and reported via on_file("error").
#   • If skip_errors=False the batch stops at the first failure.
#   • All unexpected exceptions are re-raised to the caller — never swallowed.
#
# PDF REPORT:
#   generate_batch_pdf_report(summary) → bytes
#       Generates a professional PDF report for a completed batch run.
#       Returns raw PDF bytes that can be passed to st.download_button().
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import logging
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

import requests

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BatchProcessor] %(message)s",
)
logger = logging.getLogger("BatchProcessor")

# ── Supported extensions (must match pages/upload.py ALLOWED_TYPES) ───────────
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
)

# ── MIME-type map (mirrors what process_invoice() in utils/api.py sends) ──────
MIME_MAP: dict[str, str] = {
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp":  "image/bmp",
    ".tiff": "image/tiff",
}


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def filter_valid_files(uploaded_files: list) -> tuple[list, list]:
    """
    Partition `uploaded_files` into (valid, rejected) based on extension.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects.

    Returns:
        (valid_files, rejected_files) — both lists of UploadedFile objects.
    """
    valid, rejected = [], []
    for f in uploaded_files:
        ext = "." + f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
        (valid if ext in SUPPORTED_EXTENSIONS else rejected).append(f)
    return valid, rejected


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-FILE UPLOAD
# ─────────────────────────────────────────────────────────────────────────────

def _upload_single(
    uploaded_file,
    token: str,
    base_url: str,
    timeout: int = 120,
) -> tuple[int, dict]:
    """
    Upload one Streamlit UploadedFile to the backend /process endpoint.

    Replicates the behaviour of utils/api.py::process_invoice() so both manual
    uploads and batch uploads produce identical MongoDB records.

    Args:
        uploaded_file: Streamlit UploadedFile instance.
        token:         JWT bearer token from st.session_state.
        base_url:      Backend root URL.
        timeout:       HTTP timeout in seconds (default 120 for cold-start).

    Returns:
        (http_status_code, response_json_as_dict)
    """
    filename = uploaded_file.name
    ext      = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime     = MIME_MAP.get(ext, "image/jpeg")
    headers  = {"Authorization": f"Bearer {token}"}

    try:
        file_bytes = uploaded_file.getvalue()

        response = requests.post(
            url=f"{base_url.rstrip('/')}/process",
            headers=headers,
            files={"file": (filename, file_bytes, mime)},
            timeout=timeout,
        )

        try:
            data = response.json()
        except Exception:
            data = {"detail": response.text or "Non-JSON response from server"}

        return response.status_code, data

    except requests.exceptions.ConnectionError as exc:
        logger.error("Connection error for %s: %s", filename, exc)
        return 503, {"detail": f"Connection error: {exc}"}
    except requests.exceptions.Timeout:
        logger.error("Timeout uploading %s", filename)
        return 408, {"detail": "Request timed out — backend may be waking up, retry later."}
    except Exception as exc:
        logger.error("Unexpected error uploading %s: %s", filename, exc)
        return 500, {"detail": f"Unexpected error: {exc}"}


# ─────────────────────────────────────────────────────────────────────────────
# NO-OP CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────

def _noop(*args, **kwargs) -> None:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — called by upload.py
# ─────────────────────────────────────────────────────────────────────────────

def run_batch(
    uploaded_files: list,
    token: str,
    base_url: str,
    delay_between: float = 1.0,
    skip_errors: bool = True,
    callbacks: Optional[Dict[str, Callable]] = None,
) -> dict:
    """
    Process a list of Streamlit UploadedFile objects one-by-one, streaming
    progress via `callbacks`.

    This is the single public entry point consumed by pages/upload.py.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects selected by the user.
        token:          JWT bearer token (from st.session_state["token"]).
        base_url:       Backend root URL (from utils/api.BASE_URL).
        delay_between:  Seconds to wait between successive uploads (default 1.0).
        skip_errors:    If True, log errors and continue; if False, stop on first failure.
        callbacks:      Dict with optional keys:
                            "on_start"    → fn(total: int)
                            "on_file"     → fn(index, filename, status, data)
                            "on_complete" → fn(summary: dict)

    Returns:
        summary dict:
            total      (int)   — files queued
            ok         (int)   — files successfully uploaded
            errors     (int)   — files that failed
            skipped    (int)   — files skipped (unsupported type)
            duration_s (float) — wall-clock seconds for the full run
            results    (list)  — per-file result dicts:
                                    filename, status, http_status, data, duration_s
    """
    if callbacks is None:
        callbacks = {}

    cb_start    = callbacks.get("on_start",    _noop)
    cb_file     = callbacks.get("on_file",     _noop)
    cb_complete = callbacks.get("on_complete", _noop)

    # ── Filter valid files ────────────────────────────────────────────────────
    valid_files, rejected_files = filter_valid_files(uploaded_files or [])

    if rejected_files:
        logger.warning(
            "Skipping %d unsupported file(s): %s",
            len(rejected_files),
            [f.name for f in rejected_files],
        )

    total   = len(valid_files)
    skipped = len(rejected_files)

    cb_start(total)

    if total == 0:
        summary = {
            "total": 0, "ok": 0, "errors": 0, "skipped": skipped,
            "duration_s": 0.0, "results": [],
        }
        cb_complete(summary)
        return summary

    # ── Batch loop ────────────────────────────────────────────────────────────
    run_start  = time.monotonic()
    ok_count   = 0
    err_count  = 0
    results: list[dict] = []

    for idx, uf in enumerate(valid_files, start=1):
        filename   = uf.name
        file_start = time.monotonic()

        logger.info("[%d/%d] Processing: %s", idx, total, filename)
        cb_file(idx, filename, "processing", {})

        http_status, data = _upload_single(uf, token, base_url)
        file_elapsed = round(time.monotonic() - file_start, 2)

        if http_status == 200:
            ok_count += 1
            status    = "ok"
            logger.info("[%d/%d] ✓ OK — %s (%.1fs)", idx, total, filename, file_elapsed)
        else:
            err_count += 1
            status     = "error"
            detail     = data.get("detail", f"HTTP {http_status}")
            logger.warning("[%d/%d] ✗ FAIL — %s: %s", idx, total, filename, detail)

            if not skip_errors:
                cb_file(idx, filename, "error", detail)
                results.append({
                    "filename":    filename,
                    "status":      "error",
                    "http_status": http_status,
                    "data":        data,
                    "duration_s":  file_elapsed,
                })
                summary = {
                    "total":      total,
                    "ok":         ok_count,
                    "errors":     err_count,
                    "skipped":    skipped,
                    "duration_s": round(time.monotonic() - run_start, 2),
                    "results":    results,
                }
                cb_complete(summary)
                raise RuntimeError(
                    f"Batch stopped at file {idx}/{total} ({filename}): {detail}"
                )

        cb_file(idx, filename, status, data if status == "ok" else data.get("detail", ""))

        results.append({
            "filename":    filename,
            "status":      status,
            "http_status": http_status,
            "data":        data,
            "duration_s":  file_elapsed,
        })

        if idx < total and delay_between > 0:
            time.sleep(delay_between)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_elapsed = round(time.monotonic() - run_start, 2)
    summary = {
        "total":      total,
        "ok":         ok_count,
        "errors":     err_count,
        "skipped":    skipped,
        "duration_s": total_elapsed,
        "results":    results,
    }

    logger.info(
        "Batch complete: %d/%d OK, %d errors, %d skipped, %.1fs total",
        ok_count, total, err_count, skipped, total_elapsed,
    )

    cb_complete(summary)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# PDF REPORT GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_batch_pdf_report(summary: dict) -> bytes:
    """
    Generate a professional PDF batch report.

    Layout: Cover page with summary stats, then invoice detail pages.
    Each page holds up to 3 invoices.  Each invoice block is split into two
    columns: left = the uploaded invoice image (fetched from Cloudinary URL
    stored in the result data), right = extracted OCR fields.

    Args:
        summary: The dict returned by run_batch().

    Returns:
        Raw PDF bytes suitable for st.download_button().
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable, Image as RLImage, PageBreak,
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
    except ImportError as exc:
        raise ImportError(
            "reportlab is required. Install with: pip install reportlab"
        ) from exc

    # ── Colour palette ────────────────────────────────────────────────────────
    TEAL       = colors.HexColor("#00D4AA")
    RED        = colors.HexColor("#FF4D6D")
    BG_DARK    = colors.HexColor("#060D1F")
    BG_CARD    = colors.HexColor("#0D1B2E")
    BG_FIELD   = colors.HexColor("#111C30")
    TEXT_LIGHT = colors.HexColor("#EDF2F7")
    TEXT_MUTED = colors.HexColor("#718096")
    BORDER     = colors.HexColor("#1A2A3F")
    WHITE      = colors.white

    # ── Styles ────────────────────────────────────────────────────────────────
    base = getSampleStyleSheet()

    s_title = ParagraphStyle("RTitle", parent=base["Normal"],
                             fontSize=20, textColor=TEAL, fontName="Helvetica-Bold",
                             spaceAfter=3, alignment=TA_LEFT)
    s_sub   = ParagraphStyle("RSub",   parent=base["Normal"],
                             fontSize=8, textColor=TEXT_MUTED, fontName="Helvetica",
                             spaceAfter=8)
    s_sec   = ParagraphStyle("RSec",   parent=base["Normal"],
                             fontSize=10, textColor=TEXT_LIGHT, fontName="Helvetica-Bold",
                             spaceBefore=10, spaceAfter=5)
    s_body  = ParagraphStyle("RBody",  parent=base["Normal"],
                             fontSize=7.5, textColor=TEXT_MUTED, fontName="Helvetica",
                             leading=11)
    s_mono  = ParagraphStyle("RMono",  parent=base["Normal"],
                             fontSize=7.5, textColor=TEXT_LIGHT, fontName="Courier",
                             leading=11)
    s_fname = ParagraphStyle("RFname", parent=base["Normal"],
                             fontSize=7, textColor=TEAL, fontName="Helvetica-Bold",
                             spaceAfter=4, alignment=TA_CENTER)
    s_lbl   = ParagraphStyle("RLbl",   parent=base["Normal"],
                             fontSize=6.5, textColor=TEXT_MUTED, fontName="Helvetica",
                             leading=9)
    s_val   = ParagraphStyle("RVal",   parent=base["Normal"],
                             fontSize=8, textColor=TEXT_LIGHT, fontName="Helvetica-Bold",
                             leading=10)

    # ── Document ──────────────────────────────────────────────────────────────
    buf    = io.BytesIO()
    PAGE_W, PAGE_H = A4
    MARGIN = 16 * mm

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
        title="GST Intelligence Platform — Batch Invoice Report",
        author="GST Intelligence Platform",
    )

    BODY_W = PAGE_W - 2 * MARGIN   # usable width

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _p(txt, style):
        return Paragraph(str(txt), style)

    def _hdr(txt):
        return _p(f'<font color="{TEAL.hexval()}"><b>{txt}</b></font>', s_body)

    def _cell(txt, col=None):
        c = col.hexval() if col and hasattr(col, "hexval") else (col or TEXT_MUTED.hexval())
        return _p(f'<font color="{c}">{txt}</font>', s_mono)

    def _fetch_image(url: str, width: float, max_height: float):
        """Fetch image from URL and return a ReportLab Image object, or None."""
        if not url:
            return None
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as resp:
                img_data = resp.read()
            img_buf = io.BytesIO(img_data)
            img = RLImage(img_buf, width=width, height=max_height, kind="bound")
            return img
        except Exception:
            return None

    def _field_table(fields: list[tuple[str, str, object]]) -> Table:
        """
        Compact two-column label/value table for extracted fields.
        fields = [(label, value, value_color), ...]
        """
        rows = []
        for lbl, val, col in fields:
            hex_c = col.hexval() if col and hasattr(col, "hexval") else TEXT_LIGHT.hexval()
            rows.append([
                _p(lbl, s_lbl),
                _p(f'<font color="{hex_c}"><b>{val}</b></font>', s_val),
            ])
        tbl = Table(rows, colWidths=[26 * mm, None])
        tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS",(0, 0), (-1, -1), [BG_DARK, BG_FIELD]),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.3, BORDER),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ]))
        return tbl

    # ── Story ─────────────────────────────────────────────────────────────────
    story = []
    now_str = datetime.now().strftime("%d %b %Y · %H:%M:%S")
    results = summary.get("results", [])
    total    = summary.get("total",      0)
    ok_count = summary.get("ok",         0)
    err_cnt  = summary.get("errors",     0)
    skipped  = summary.get("skipped",    0)
    duration = summary.get("duration_s", 0.0)
    success_rate = f"{int(ok_count / total * 100)}%" if total else "—"

    # ── Cover / Summary page ──────────────────────────────────────────────────
    story.append(_p("GST Intelligence Platform", s_title))
    story.append(_p(f"Batch Invoice Report  ·  {now_str}", s_sub))
    story.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=10))

    stat_data = [
        [_hdr("Files"), _hdr("Successful"), _hdr("Errors"), _hdr("Skipped"),
         _hdr("Success Rate"), _hdr("Duration")],
        [_cell(str(total), TEAL), _cell(str(ok_count), TEAL),
         _cell(str(err_cnt), RED if err_cnt else TEAL),
         _cell(str(skipped), TEXT_MUTED),
         _cell(success_rate, TEAL), _cell(f"{duration:.1f}s", TEXT_MUTED)],
    ]
    stat_col_w = BODY_W / 6
    stat_tbl = Table(stat_data, colWidths=[stat_col_w] * 6, rowHeights=[16, 26])
    stat_tbl.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND",    (0, 0), (-1, -1), BG_CARD),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(stat_tbl)
    story.append(Spacer(1, 12))

    # Quick per-file summary table on cover
    story.append(_p("Processing Log", s_sec))
    log_col_w = [14*mm, 72*mm, 20*mm, 22*mm, 22*mm, 24*mm]
    log_hdr = [_hdr("#"), _hdr("Filename"), _hdr("Status"), _hdr("HTTP"),
               _hdr("Duration"), _hdr("Total Amount")]
    log_rows = [log_hdr]
    for i, r in enumerate(results, 1):
        is_ok = r.get("status") == "ok"
        d = r.get("data", {})
        ext = d.get("extracted") or d
        total_a = ext.get("TOTAL_AMOUNT", "—") if is_ok else "—"
        log_rows.append([
            _cell(str(i)),
            _cell(r.get("filename", "—"), TEXT_LIGHT),
            _cell("✓ OK" if is_ok else "✗ Error", TEAL if is_ok else RED),
            _cell(str(r.get("http_status", "—")), TEAL if is_ok else RED),
            _cell(f"{r.get('duration_s', 0):.2f}s"),
            _cell(str(total_a), TEAL if is_ok else TEXT_MUTED),
        ])
    log_tbl = Table(log_rows, colWidths=log_col_w, repeatRows=1)
    log_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BG_DARK),
        ("LINEBELOW",     (0, 0), (-1, 0), 1, TEAL),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [BG_DARK, BG_CARD]),
        ("LINEBELOW",     (0, 1), (-1, -1), 0.3, BORDER),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(log_tbl)

    # ── Invoice detail pages — 3 invoices per page ────────────────────────────
    # Column widths: image col = 45% of body, results col = 55%
    IMG_COL  = BODY_W * 0.45
    DATA_COL = BODY_W * 0.55 - 4 * mm   # 4 mm gap
    # Each invoice block height = (page height - margins - header) / 3
    BLOCK_H  = (PAGE_H - 2 * MARGIN - 20 * mm) / 3
    IMG_H    = BLOCK_H - 8 * mm   # leave room for filename label + separator

    ok_results = [r for r in results if r.get("status") == "ok"]

    if ok_results:
        story.append(PageBreak())
        story.append(_p("Invoice Details", s_title))
        story.append(_p(
            "Each invoice image (left) paired with its extracted OCR data (right). "
            "Three invoices per page.", s_sub,
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=8))

        # Group into pages of 3
        for page_start in range(0, len(ok_results), 3):
            group = ok_results[page_start: page_start + 3]

            # Build one row per invoice in the group
            page_rows = []
            for r in group:
                fname = r.get("filename", "—")
                d     = r.get("data", {})
                ext   = d.get("extracted") or d
                val   = d.get("validation") or ext.get("validation") or {}

                gstin       = ext.get("GSTIN",         "—") or "—"
                merchant    = ext.get("MERCHANT",      "—") or "—"
                inv_no      = ext.get("INVOICE_NO",    "—") or "—"
                inv_date    = ext.get("INVOICE_DATE",  "—") or "—"
                total_amt   = ext.get("TOTAL_AMOUNT",  "—") or "—"
                taxable_amt = ext.get("TAXABLE_AMOUNT","—") or "—"
                gst_amt     = ext.get("GST_AMOUNT",    "—") or "—"
                gst_ok      = "✓ Valid" if val.get("gst_valid")    else "✗ Invalid"
                amt_ok      = "✓ Match" if val.get("amounts_match") else "✗ Mismatch"
                gst_col     = TEAL if val.get("gst_valid")    else RED
                amt_col     = TEAL if val.get("amounts_match") else RED
                cloud_url   = d.get("cloudinary_url", "")

                # Left cell: invoice image
                img_obj = _fetch_image(cloud_url, IMG_COL, IMG_H)
                if img_obj:
                    left_content = [
                        _p(fname, s_fname),
                        img_obj,
                    ]
                else:
                    left_content = [
                        _p(fname, s_fname),
                        _p("[Image unavailable]", s_lbl),
                    ]

                # Right cell: extracted data
                fields = [
                    ("Merchant",    merchant[:28],    TEXT_LIGHT),
                    ("GSTIN",       gstin,            TEAL),
                    ("Invoice No.", inv_no,           TEXT_LIGHT),
                    ("Date",        inv_date,         TEXT_LIGHT),
                    ("Total",       total_amt,        TEAL),
                    ("Taxable",     taxable_amt,      TEXT_LIGHT),
                    ("GST",         gst_amt,          TEXT_LIGHT),
                    ("GSTIN Check", gst_ok,           gst_col),
                    ("Amounts",     amt_ok,           amt_col),
                ]
                right_content = [
                    _p("Extracted Data", s_sec),
                    _field_table(fields),
                ]

                # Wrap each side in a single-cell Table for border styling
                left_tbl = Table(
                    [[left_content]], colWidths=[IMG_COL],
                )
                left_tbl.setStyle(TableStyle([
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
                    ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
                    ("BACKGROUND",    (0, 0), (-1, -1), BG_CARD),
                ]))

                right_tbl = Table(
                    [[right_content]], colWidths=[DATA_COL],
                )
                right_tbl.setStyle(TableStyle([
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                    ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
                    ("BACKGROUND",    (0, 0), (-1, -1), BG_DARK),
                ]))

                # Combined two-column row
                pair_tbl = Table(
                    [[left_tbl, right_tbl]],
                    colWidths=[IMG_COL + 4 * mm, DATA_COL],
                    rowHeights=[BLOCK_H - 4 * mm],
                )
                pair_tbl.setStyle(TableStyle([
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ]))
                page_rows.append(pair_tbl)
                page_rows.append(Spacer(1, 4))

            story.extend(page_rows)

            # New page after every group of 3 (except last)
            if page_start + 3 < len(ok_results):
                story.append(PageBreak())

    # ── Error section ─────────────────────────────────────────────────────────
    err_results = [r for r in results if r.get("status") == "error"]
    if err_results:
        story.append(Spacer(1, 14))
        story.append(_p("Processing Errors", s_sec))
        for r in err_results:
            d      = r.get("data", {})
            detail = d.get("detail", "Unknown error") if isinstance(d, dict) else str(d)
            story.append(_p(
                f'<font color="{RED.hexval()}"><b>{r.get("filename","?")}</b></font>'
                f'  ·  HTTP {r.get("http_status","—")}  ·  {detail}',
                s_body,
            ))
            story.append(Spacer(1, 3))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=5))
    story.append(_p(
        f"GST Intelligence Platform  ·  Batch Report  ·  {now_str}",
        s_body,
    ))

    doc.build(story)
    return buf.getvalue()