# --- file: utils/cleaner.py ---
# ═══════════════════════════════════════════════════════════════════════════
# DATA INTEGRITY LAYER
# Single source of truth for all data cleaning, deduplication, and validation.
# Rule: raw API data → functions here → safe Python objects → UI.
# No page should ever call float() or .get() on amounts directly.
# ═══════════════════════════════════════════════════════════════════════════

import pandas as pd


# ── clean_amount / safe_num ──────────────────────────────────────────────────
#
# WHY IT EXISTS:
#   OCR engines return amounts as strings: "1,23,000", "1800.00", "N/A", "".
#   MongoDB may also return int, float, None, or NaN. A plain float() crashes
#   on any of these. This function handles every possible type and always
#   returns a clean Python float — it never raises.
#
# LOGIC WALKTHROUGH:
#   None               → 0.0  (explicit early return)
#   Non-string types   → try pd.isna() to catch numpy NaN / pandas NA.
#                        We only call pd.isna on non-strings because calling it
#                        on a plain string raises TypeError in some pandas versions.
#   bool               → 0.0  (bool is a subclass of int; True→1.0 would be wrong)
#   int / float        → float(x) directly
#   str                → strip commas + "₹" + whitespace, then float().
#                        ValueError (e.g. "N/A", "—") returns 0.0.
#   Anything else      → 0.0
def clean_amount(x) -> float:
    """
    Safely convert any amount field to float.
    Handles: None, NaN, bool, int, float, OCR strings like '1,800' / '₹ 13,000',
    and garbage strings like 'N/A', '' — always returns 0.0 on failure.
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


# Alias so pages can use either name without diverging logic.
safe_num = clean_amount


# ── clean_text ───────────────────────────────────────────────────────────────
# Returns "—" for None/empty so the UI always has a displayable value.
def clean_text(x) -> str:
    if x is None or str(x).strip() == "":
        return "—"
    return str(x)


# ── clean_validation ─────────────────────────────────────────────────────────
# WHY IT EXISTS:
#   Backend may return validation as None, {}, or a partial dict.
#   Normalises to always a dict with both boolean keys so downstream
#   code never needs defensive .get() guards on validation fields.
def clean_validation(v) -> dict:
    v = v or {}
    return {
        "gst_valid":     bool(v.get("gst_valid",    False)),
        "amounts_match": bool(v.get("amounts_match", False)),
    }


# ── normalize_record ─────────────────────────────────────────────────────────
# WHY IT EXISTS:
#   Raw MongoDB documents have inconsistent types — amounts as strings from OCR,
#   missing fields, None values. This produces a canonical dict with guaranteed
#   types so every page works from the same clean structure.
#
# KEY FIELDS PRESERVED:
#   INVOICE_NO    — required for Tier-1 deduplication (see deduplicate_records).
#   TAXABLE_AMOUNT — required for the ₹2 integrity math check in forensic_guard
#                   and for taxable-amount display in records/financials.
#   cloudinary_url — passthrough so records.py can show the invoice image.
def normalize_record(r: dict) -> dict:
    """Canonical normalisation for a raw MongoDB record."""
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
# WHY IT EXISTS:
#   Users upload the same invoice more than once. The backend saves every upload.
#   Without deduplication, every duplicate inflates turnover, GST totals, and
#   ITC eligibility — producing numbers that are legally incorrect.
#
# TWO-TIER STRATEGY:
#
#   Tier 1 — INVOICE_NO (preferred):
#     Under GST law every invoice must carry a unique sequential number.
#     Two records with the same invoice number from the same supplier are the
#     same transaction by definition. We normalise to uppercase + strip spaces.
#     Sentinel values ("—", "NONE", "NULL", "N/A", "") fall through to Tier 2.
#
#   Tier 2 — Composite key: GSTIN | TOTAL_AMOUNT_rounded_2dp | INVOICE_DATE:
#     Used when OCR failed to extract an invoice number. Three independent fields
#     must all match for a collision — the false-positive rate is negligible.
#     CRITICAL: TOTAL_AMOUNT is routed through clean_amount() before rounding
#     so that "1,23,000" (OCR string) and 123000.0 (DB-normalised float) produce
#     the same key. Without this, the same physical invoice would not be detected
#     as a duplicate when the OCR and DB amount representations differ.
#
# ORDER: first occurrence wins. O(n) hash-set lookup.
def deduplicate_records(records: list) -> list:
    """
    Return a deduplicated list of records.
    Primary key  : INVOICE_NO (stripped, uppercased) when non-empty.
    Fallback key : GSTIN | TOTAL_AMOUNT_rounded | INVOICE_DATE.
    First occurrence wins; insertion order preserved.
    """
    seen: set = set()
    out:  list = []
    SENTINEL = {"", "—", "NONE", "NULL", "N/A"}

    for r in records:
        if not isinstance(r, dict):
            continue
        inv_no = str(r.get("INVOICE_NO") or "").strip().upper()
        if inv_no and inv_no not in SENTINEL:
            key = f"INV|{inv_no}"
        else:
            gstin = str(r.get("GSTIN") or "").strip().upper()
            amt   = round(clean_amount(r.get("TOTAL_AMOUNT")), 2)
            date  = str(r.get("INVOICE_DATE") or "").strip()
            key   = f"FB|{gstin}|{amt}|{date}"
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


# ── get_valid_processed ──────────────────────────────────────────────────────
# WHY IT EXISTS:
#   Financial figures — turnover, GST totals, ITC — must only count invoices
#   that passed every validation gate. Including invalid or duplicate invoices
#   would produce numbers that are legally incorrect for GST filing.
#
# THE FIVE GATES (applied in this exact order):
#
#   Gate 1 — status == "processed":
#     Only invoices where the OCR pipeline completed. "uploaded" records are
#     still queued — they have no extracted data to aggregate.
#
#   Gate 2 — deduplicated:
#     Run dedup BEFORE validity gates. Reason: if one copy of a duplicate is
#     invalid and the other is valid, the invalid copy must be dropped before
#     the valid one is admitted. If dedup ran after, we could admit both and
#     double-count in the valid set.
#
#   Gate 3 — gst_valid is True (strict identity check, not just truthy):
#     The backend verified the GSTIN against the Indian GST regex + check-digit.
#     We use `is True` so None or missing fails this gate. A supplier with an
#     invalid GSTIN is not GST-registered — any tax paid to them cannot be
#     reclaimed as Input Tax Credit.
#
#   Gate 4 — amounts_match is True (strict):
#     The backend verified TAXABLE_AMOUNT + GST_AMOUNT ≈ TOTAL_AMOUNT.
#     If they don't reconcile, OCR made an error — the extracted numbers are
#     unreliable and must not enter any financial aggregate.
#
#   Gate 5 — TOTAL_AMOUNT > 0:
#     Guards against a known backend validation gap where OCR fails to extract
#     any number (TOTAL_AMOUNT → None → 0.0 after clean_amount) but the backend
#     still marks gst_valid + amounts_match as True. A zero-amount invoice
#     contributes nothing financially but could inflate invoice counts.
#
# IMPORT THIS in dashboard.py, itc_forecaster.py, profile.py, cards.py.
# One function → one definition → numbers are identical across every page.
def get_valid_processed(records) -> list:
    """
    Return the canonical set of records for financial calculations.
    Applies all five gates: status → dedup → gst_valid → amounts_match → TOTAL > 0.
    """
    if not records or not isinstance(records, list):
        return []
    processed = [
        r for r in records
        if isinstance(r, dict) and r.get("status") == "processed"
    ]
    deduped = deduplicate_records(processed)
    return [
        r for r in deduped
        if (r.get("validation") or {}).get("gst_valid")      is True
        and (r.get("validation") or {}).get("amounts_match")  is True
        and clean_amount(r.get("TOTAL_AMOUNT")) > 0
    ]