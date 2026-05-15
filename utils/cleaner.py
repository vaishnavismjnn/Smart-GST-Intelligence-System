# --- file: utils/cleaner.py ---
# ═══════════════════════════════════════════════════════════════════════════
# DATA INTEGRITY LAYER
# Single source of truth for cleaning, normalization, deduplication, validation.
# All pages MUST rely on this to keep numbers consistent across the app.
# ═══════════════════════════════════════════════════════════════════════════

import pandas as pd


# ── clean_amount ─────────────────────────────────────────────────────────────
def clean_amount(x) -> float:
    """
    Safely convert any value to float.
    Handles: None, NaN, bool, int, float, strings like "1,23,000", "₹ 500".
    Never crashes. Returns 0.0 on failure.
    """
    if x is None:
        return 0.0

    if not isinstance(x, str):
        try:
            if pd.isna(x):
                return 0.0
        except Exception:
            pass

    if isinstance(x, bool):
        return 0.0

    if isinstance(x, (int, float)):
        return float(x)

    if isinstance(x, str):
        cleaned = x.replace(",", "").replace("₹", "").strip()
        if not cleaned:
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    return 0.0


# Alias
safe_num = clean_amount


# ── clean_text ───────────────────────────────────────────────────────────────
def clean_text(x) -> str:
    if x is None or str(x).strip() == "":
        return "—"
    return str(x)


# ── clean_validation ─────────────────────────────────────────────────────────
def clean_validation(v) -> dict:
    v = v or {}
    return {
        "gst_valid": bool(v.get("gst_valid", False)),
        "amounts_match": bool(v.get("amounts_match", False)),
    }


# ── normalize_record ─────────────────────────────────────────────────────────
def normalize_record(r: dict) -> dict:
    """
    Converts raw MongoDB record into clean, consistent structure.
    Used heavily in records.py.
    """
    v = clean_validation(r.get("validation"))

    return {
        "_id":            r.get("_id"),
        "MERCHANT":       clean_text(r.get("MERCHANT")),
        "GSTIN":          clean_text(r.get("GSTIN")),
        "INVOICE_NO":     clean_text(r.get("INVOICE_NO")),
        "INVOICE_DATE":   r.get("INVOICE_DATE"),

        "TOTAL_AMOUNT":   clean_amount(r.get("TOTAL_AMOUNT")),
        "TAXABLE_AMOUNT": clean_amount(r.get("TAXABLE_AMOUNT")),
        "GST_AMOUNT":     clean_amount(r.get("GST_AMOUNT")),

        "validation":     v,
        "status":         r.get("status", "—"),
        "cloudinary_url": r.get("cloudinary_url"),
    }


# ── deduplicate_records ──────────────────────────────────────────────────────
def deduplicate_records(records: list) -> list:
    """
    Removes duplicate invoices.

    Tier 1: INVOICE_NO
    Tier 2: GSTIN + TOTAL_AMOUNT + DATE

    Safe for all pages:
    - dashboard
    - records
    - itc_forecaster
    """

    if not records or not isinstance(records, list):
        return []

    seen = set()
    unique = []

    for r in records:
        if not isinstance(r, dict):
            continue

        inv = str(r.get("INVOICE_NO", "")).strip().upper()

        if inv and inv not in ("—", "NONE", "NULL", "N/A", ""):
            key = ("INV", inv)
        else:
            gst   = str(r.get("GSTIN", "")).strip().upper()
            amt   = round(clean_amount(r.get("TOTAL_AMOUNT")), 2)
            date  = str(r.get("INVOICE_DATE", "")).strip()
            key   = ("FALLBACK", gst, amt, date)

        if key in seen:
            continue

        seen.add(key)
        unique.append(r)

    return unique


# ── get_valid_processed ──────────────────────────────────────────────────────
def get_valid_processed(records: list) -> list:
    """
    Returns ONLY valid + processed + deduplicated records.

    Used by:
    - dashboard (financial summary)
    - itc_forecaster (ITC calculation)

    Ensures:
    ✔ No duplicates
    ✔ Only processed invoices
    ✔ GSTIN valid
    ✔ Amounts match
    ✔ TOTAL_AMOUNT > 0
    """

    if not records or not isinstance(records, list):
        return []

    processed = [
        r for r in records
        if isinstance(r, dict) and r.get("status") == "processed"
    ]

    deduped = deduplicate_records(processed)

    valid = []
    for r in deduped:
        v = r.get("validation") or {}

        if (
            v.get("gst_valid") is True
            and v.get("amounts_match") is True
            and clean_amount(r.get("TOTAL_AMOUNT")) > 0
        ):
            valid.append(r)

    return valid