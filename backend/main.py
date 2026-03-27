from fastapi import FastAPI
import re
import time

app = FastAPI()

# -----------------------------
# Extract data from text
# -----------------------------
def structure_data(text):
    invoice = re.search(r'Invoice No[:\s]*(\w+)', text)
    gst = re.search(r'GSTIN[:\s]*([A-Z0-9]+)', text)
    total = re.search(r'Total[:\s]*₹?(\d+)', text)

    return {
        "invoice_number": invoice.group(1) if invoice else None,
        "gst_number": gst.group(1) if gst else None,
        "total_amount": int(total.group(1)) if total else None
    }

# -----------------------------
# GST validation
# -----------------------------
def validate_gst(gst):
    if not gst:
        return False
    pattern = r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}'
    return bool(re.match(pattern, gst))

# -----------------------------
# API endpoint
# -----------------------------
@app.get("/")
def home():
    return {"message": "Backend API running"}

@app.post("/process-text")
def process_text(data: dict):
    start_time = time.time()

    text = data.get("text", "")

    structured = structure_data(text)
    gst_valid = validate_gst(structured["gst_number"])

    # Dummy values for now (can improve later)
    merchant_name = "ABC Store"
    invoice_date = "2026-03-25"

    response = {
        "merchant": {
            "value": merchant_name,
            "confidence": 0.90
        },
        "invoice_date": {
            "value": invoice_date,
            "confidence": 0.90
        },
        "gstin": {
            "value": structured["gst_number"],
            "confidence": 0.95
        },
        "taxable_amount": {
            "value": structured["total_amount"]
        },
        "gst_amount": {
            "value": 0
        },
        "total_amount": {
            "value": structured["total_amount"]
        },
        "expense_category": "General",
        "validation": {
            "gst_valid": gst_valid,
            "duplicate_found": False,
            "audit_score": 85
        },
        "processing": {
            "latency_seconds": round(time.time() - start_time, 2)
        }
    }

    return response