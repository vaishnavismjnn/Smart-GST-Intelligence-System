import pandas as pd

def clean_amount(x):
    if x is None or pd.isna(x):
        return 0
    return float(x)

def clean_text(x):
    if x is None or str(x).strip() == "":
        return "—"
    return str(x)

def clean_validation(v):
    v = v or {}
    return {
        "gst_valid": bool(v.get("gst_valid", False)),
        "amounts_match": bool(v.get("amounts_match", False))
    }

def normalize_record(r):
    v = clean_validation(r.get("validation"))

    return {
        "_id": r.get("_id"),
        "MERCHANT": clean_text(r.get("MERCHANT")),
        "GSTIN": clean_text(r.get("GSTIN")),
        "INVOICE_DATE": r.get("INVOICE_DATE"),
        "TOTAL_AMOUNT": clean_amount(r.get("TOTAL_AMOUNT")),
        "GST_AMOUNT": clean_amount(r.get("GST_AMOUNT")),
        "validation": v,
        "status": r.get("status", "—")
    }