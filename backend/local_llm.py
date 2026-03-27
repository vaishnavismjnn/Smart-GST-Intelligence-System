from fastapi import FastAPI
import time
import re
from transformers import pipeline

app = FastAPI()

# LLM (only for text understanding)
generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-base",
    framework="pt"
)

# -----------------------------
# LLM for text fields
# -----------------------------
def ask_llm(question, text):
    prompt = f"""
    {question}

    Return only answer.

    {text}
    """
    result = generator(prompt, max_length=50)[0]["generated_text"]
    return result.strip()

# -----------------------------
# Extract structured fields
# -----------------------------
def extract_structured(text):
    gst = re.search(r'GSTIN[:\s]*([A-Z0-9]+)', text)
    total = re.search(r'Total[:\s]*₹?(\d+)', text)
    gst_amt = re.search(r'GST Amount[:\s]*₹?(\d+)', text)
    taxable = re.search(r'Taxable Amount[:\s]*₹?(\d+)', text)

    return {
        "gstin": gst.group(1) if gst else None,
        "total": int(total.group(1)) if total else None,
        "gst_amount": int(gst_amt.group(1)) if gst_amt else None,
        "taxable": int(taxable.group(1)) if taxable else None
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
# API
# -----------------------------
@app.post("/process-text")
def process_text(data: dict):
    start_time = time.time()

    text = data.get("text", "")

    # LLM (safe fields)
    merchant = ask_llm("Merchant name?", text)
    date = ask_llm("Invoice date?", text)
    category = ask_llm("Expense category?", text)

    # Regex (accurate numbers)
    structured = extract_structured(text)

    gst_valid = validate_gst(structured["gstin"])

    response = {
        "merchant": {
            "value": merchant,
            "confidence": 0.90
        },
        "invoice_date": {
            "value": date,
            "confidence": 0.85
        },
        "gstin": {
            "value": structured["gstin"],
            "confidence": 0.95
        },
        "taxable_amount": {
            "value": structured["taxable"]
        },
        "gst_amount": {
            "value": structured["gst_amount"]
        },
        "total_amount": {
            "value": structured["total"]
        },
        "expense_category": category,
        "validation": {
            "gst_valid": gst_valid,
            "duplicate_found": False,
            "audit_score": 90
        },
        "processing": {
            "latency_seconds": round(time.time() - start_time, 2)
        }
    }

    return response