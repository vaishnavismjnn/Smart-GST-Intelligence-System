from fastapi import APIRouter, Depends
import time

from backend.core.security import get_current_user
from backend.services.extractor import (
    extract_date,
    extract_structured,
    validate_gst,
    validate_amounts
)

router= APIRouter()


@router.post("/process-text")
def process_text(
    data: dict,
    current_user: str = Depends(get_current_user)
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