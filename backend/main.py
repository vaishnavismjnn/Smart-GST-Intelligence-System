from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import FastAPI, Depends, HTTPException
from fastapi.openapi.utils import get_openapi
from backend.core.security import get_current_user
import time
import re
from backend.routes.auth import router as auth_router

app = FastAPI()
app.include_router(auth_router, prefix="/auth")

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Receipt API",
        version="1.0.0",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer"
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.post("/process-text")
def process_text(
    data: dict,
    current_user: str = Depends(get_current_user)  # ✅ auth
):
    start_time = time.time()

    text = data.get("text", "")

    if not text.strip():
        return {"error": "Empty input"}

    lines = text.split("\n")
    merchant = lines[0] if lines else None
    category = "General"

    date = extract_date(text)
    structured = extract_structured(text)

    gst_valid = validate_gst(structured["gstin"])
    amounts_valid = validate_amounts(
        structured["total"],
        structured["taxable"],
        structured["gst_amount"]
    )

    return {
        "merchant": {"value": merchant, "confidence": 0.9},
        "invoice_date": {"value": date, "confidence": 0.9},
        "gstin": {"value": structured["gstin"], "confidence": 0.95},
        "taxable_amount": {"value": structured["taxable"]},
        "gst_amount": {"value": structured["gst_amount"]},
        "total_amount": {"value": structured["total"]},
        "expense_category": category,
        "validation": {
            "gst_valid": gst_valid,
            "amounts_match": amounts_valid,
            "duplicate_found": False,
            "audit_score": 95 if amounts_valid else 75
        },
        "processing": {
            "latency_seconds": round(time.time() - start_time, 2)
        }
    }
# -----------------------------
# DATE
# -----------------------------
def extract_date(text):
    match = re.search(r'\b\d{2}[-/]\d{2}[-/]\d{4}\b', text)
    return match.group(0) if match else None


# -----------------------------
# CLEAN NUMBER
# -----------------------------
def clean_number(num):
    try:
        return float(num.replace(",", ""))
    except:
        return None


# -----------------------------
# MAIN EXTRACTION
# -----------------------------
def extract_structured(text):

    # 🔥 remove percentage
    text = re.sub(r'\d+%', '', text)

    total_patterns = [
        r'(grand total|total amount|amount payable|total)[^\d]{0,20}([\d,]+\.?\d*)'
    ]

    taxable_patterns = [
    r'(taxable amount|taxable amt|taxable|subtotal|sub total|net amount)[^\d]{0,20}([\d,]+\.?\d*)'
    ]

    gst_patterns = [
        r'(gst amount|total gst|tax amount)[^\d]{0,20}([\d,]+\.?\d*)'
    ]

    gstin_pattern = r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b'

    def extract(patterns):
        for p in patterns:
            matches = re.findall(p, text, re.IGNORECASE)
            if matches:
                values = []
                for m in matches:
                    num = clean_number(m[1])
                    if num:
                        values.append(num)
                if values:
                    return max(values)
        return None

    total = extract(total_patterns)
    taxable = extract(taxable_patterns)
    gst = extract(gst_patterns)

    # -----------------------------
    # GST COMPONENTS
    # -----------------------------
    cgst = re.findall(r'CGST.*?:?\s*₹?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    sgst = re.findall(r'SGST.*?:?\s*₹?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    igst = re.findall(r'IGST.*?:?\s*₹?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)

    cgst_val = sum([clean_number(x) or 0 for x in cgst])
    sgst_val = sum([clean_number(x) or 0 for x in sgst])
    igst_val = sum([clean_number(x) or 0 for x in igst])

    total_gst = cgst_val + sgst_val + igst_val

    if total_gst > 1:
        gst = total_gst

    # -----------------------------
    # GSTIN
    # -----------------------------
    gstin_match = re.search(gstin_pattern, text)
    gstin = gstin_match.group(0) if gstin_match else None

    # -----------------------------
    # SAFE FALLBACK
    # -----------------------------
    if total is None or taxable is None:

        text_clean = text

        # remove date
        text_clean = re.sub(r'\b\d{2}[-/]\d{2}[-/]\d{4}\b', '', text_clean)

        # remove GSTIN
        text_clean = re.sub(gstin_pattern, '', text_clean)

        numbers = re.findall(r'[\d,]+\.?\d*', text_clean)
        numbers = [clean_number(n) for n in numbers if clean_number(n)]

        numbers = [n for n in numbers if not (1900 <= n <= 2100)]
        numbers = [n for n in numbers if n >= 50]

        if numbers:
            numbers = sorted(numbers)

            if total is None:
                total = max(numbers)

            if taxable is None:
                candidates = [n for n in numbers if n < total]
                candidates = [n for n in candidates if n >= 0.1 * total]

                if candidates:
                    taxable = max(candidates)
                else:
                    taxable = total

    # -----------------------------
    # FIX SWAPPED VALUES
    # -----------------------------
    if total and taxable and taxable > total:
        total, taxable = taxable, total

    # -----------------------------
    # FINAL GST LOGIC
    # -----------------------------
    if total and taxable:
        diff = total - taxable

        # if GST explicitly present, keep it
        if gst is None:
            if 0.05 * total <= diff <= 0.3 * total:
                gst = diff
            elif diff == 0:
                gst = None
            else:
                gst = None
        else:
            # validate GST
            if abs((taxable + gst) - total) > 5:
                gst = diff if diff > 0 else None

    return {
        "gstin": gstin,
        "total": total,
        "gst_amount": gst,
        "taxable": taxable
    }


# -----------------------------
# VALIDATION
# -----------------------------
def validate_gst(gst):
    if not gst:
        return False
    pattern = r'\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]'
    return bool(re.match(pattern, gst))


def validate_amounts(total, taxable, gst):
    if total and taxable and gst:
        return abs((taxable + gst) - total) < 2
    return True


# -----------------------------
# API
# -----------------------------
@app.post("/process-text")
def process_text(data: dict):
    start_time = time.time()

    text = data.get("text", "")

    if not text.strip():
        return {"error": "Empty input"}

    lines = text.split("\n")
    merchant = lines[0] if lines else None
    category = "General"

    date = extract_date(text)
    structured = extract_structured(text)

    gst_valid = validate_gst(structured["gstin"])
    amounts_valid = validate_amounts(
        structured["total"],
        structured["taxable"],
        structured["gst_amount"]
    )

    return {
        "merchant": {"value": merchant, "confidence": 0.9},
        "invoice_date": {"value": date, "confidence": 0.9},
        "gstin": {"value": structured["gstin"], "confidence": 0.95},
        "taxable_amount": {"value": structured["taxable"]},
        "gst_amount": {"value": structured["gst_amount"]},
        "total_amount": {"value": structured["total"]},
        "expense_category": category,
        "validation": {
            "gst_valid": gst_valid,
            "amounts_match": amounts_valid,
            "duplicate_found": False,
            "audit_score": 95 if amounts_valid else 75
        },
        "processing": {
            "latency_seconds": round(time.time() - start_time, 2)
        }
    }