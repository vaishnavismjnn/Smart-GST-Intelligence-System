from fastapi import FastAPI
import time
import re
from transformers import pipeline

app = FastAPI()

# LLM SETUP

generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-base",
    framework="pt"
)


# SAFE LLM

def ask_llm(question, text):
    prompt = f"{question}\nReturn only short answer.\n{text}"
    result = generator(prompt, max_length=30)[0]["generated_text"].strip()

    if result.isdigit():
        return None

    return result.split("\n")[0].strip()



# DATE (NO LLM)

def extract_date(text):
    match = re.search(r'\b\d{2}[-/]\d{2}[-/]\d{4}\b', text)
    return match.group(0) if match else None



# CLEAN NUMBER

def clean_number(num):
    try:
        return float(num.replace(",", ""))
    except:
        return None



# MAIN EXTRACTION

def extract_structured(text):

    total_patterns = [
        r'(grand total|total amount|amount payable|total)[^\d]{0,20}([\d,]+\.?\d*)'
    ]

    taxable_patterns = [
        r'(taxable amount|subtotal|sub total|net amount)[^\d]{0,20}([\d,]+\.?\d*)'
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


    # FIXED GST EXTRACTION 
    
    cgst = re.findall(r'CGST.*?:\s*₹?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    sgst = re.findall(r'SGST.*?:\s*₹?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    igst = re.findall(r'IGST.*?:\s*₹?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)

    cgst_val = sum([clean_number(x) or 0 for x in cgst])
    sgst_val = sum([clean_number(x) or 0 for x in sgst])
    igst_val = sum([clean_number(x) or 0 for x in igst])

    total_gst = cgst_val + sgst_val + igst_val

    if gst is None and total_gst > 1:
        gst = total_gst

 
    # GSTIN
   
    gstin_match = re.search(gstin_pattern, text)
    gstin = gstin_match.group(0) if gstin_match else None

 
    # SAFE NUMBER FALLBACK
   
    if total is None or taxable is None:

        numbers = re.findall(r'[\d,]+\.?\d*', text)
        numbers = [clean_number(n) for n in numbers if clean_number(n)]

        # remove year values
        numbers = [n for n in numbers if not (1900 <= n <= 2100)]

        #remove small values (like 9%, 18, etc.)
        numbers = [n for n in numbers if n >= 100]

        if numbers:
            numbers.sort(reverse=True)

            if total is None:
                total = numbers[0]

            if taxable is None:
                if len(numbers) > 1:
                    taxable = numbers[1]
                else:
                    taxable = total


    # DERIVE GST
   
    if total and taxable and gst is None:
        diff = total - taxable

        if 0 < diff < (0.5 * total):
            gst = diff
        else:
            gst = None

    # FINAL SAFETY
   
    if gst == 0:
        gst = None

    return {
        "gstin": gstin,
        "total": total,
        "gst_amount": gst,
        "taxable": taxable
    }

# VALIDATION
def validate_gst(gst):
    if not gst:
        return False
    pattern = r'\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]'
    return bool(re.match(pattern, gst))


def validate_amounts(total, taxable, gst):
    if total and taxable and gst:
        return abs((taxable + gst) - total) < 2
    return False



# API
@app.post("/process-text")
def process_text(data: dict):
    start_time = time.time()

    text = data.get("text", "")

    merchant = ask_llm("Merchant name?", text)
    date = extract_date(text)
    category = ask_llm("Expense category?", text)

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