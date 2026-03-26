from fastapi import FastAPI
import re

app = FastAPI()

def structure_data(text):
    invoice = re.search(r'Invoice No[:\s]*(\w+)', text)
    gst = re.search(r'GSTIN[:\s]*([A-Z0-9]+)', text)
    total = re.search(r'Total[:\s]*₹?(\d+)', text)

    return {
        "invoice_number": invoice.group(1) if invoice else None,
        "gst_number": gst.group(1) if gst else None,
        "total_amount": int(total.group(1)) if total else None
    }

def validate_gst(gst):
    if not gst:
        return False
    pattern = r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}'
    return bool(re.match(pattern, gst))

@app.post("/process-text")
def process_text(data: dict):
    text = data["text"]

    structured = structure_data(text)
    structured["gst_valid"] = validate_gst(structured["gst_number"])

    return structured