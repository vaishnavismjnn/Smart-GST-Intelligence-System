from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from backend.core.security import SECRET_KEY, ALGORITHM
from PIL import Image
import io, base64, httpx, json, re, os, asyncio

from backend.services.validation import validate_gst
from backend.services.extract_invoice import extract_invoice_from_image
from backend.services.upload_service import upload_to_cloudinary
from backend.db import collection

router        = APIRouter()
bearer_scheme = HTTPBearer()

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ─────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email   = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _to_float(val):
    if val in (None, "", "null"):
        return None
    try:
        return float(str(val).replace(",", "").replace("₹", "").strip())
    except:
        return None


def _safe_float(x):
    try:
        return float(x) if x is not None else None
    except:
        return None


def _groq_result_is_good(data):
    if not data:
        return False
    if data.get("total_final_amount") in (None, "", "null"):
        return False
    if data.get("merchant_name") in (None, "", "null"):
        return False

    missing_amounts = sum(
        1 for f in ["tax_amount", "total_gst", "total_final_amount"]
        if data.get(f) in (None, "", "null")
    )
    return missing_amounts < 2


def _normalize_groq(data):
    return {
        "GSTIN":          data.get("gstin"),
        "INVOICE_NO":     data.get("invoice_number"),
        "INVOICE_DATE":   data.get("invoice_date"),
        "MERCHANT":       data.get("merchant_name"),
        "TOTAL_AMOUNT":   _to_float(data.get("total_final_amount")),
        "TAXABLE_AMOUNT": _to_float(data.get("tax_amount")),
        "GST_AMOUNT":     _to_float(data.get("total_gst")),
    }


# ─────────────────────────────────────────────────────────────
# GROQ EXTRACTION
# ─────────────────────────────────────────────────────────────

async def _extract_with_groq(file_bytes, mime_type):
    if not GROQ_API_KEY:
        return None

    try:
        b64 = base64.b64encode(file_bytes).decode()

        prompt = (
            "Extract data from this invoice image and return ONLY a JSON object:\n"
            "{\n"
            '  "merchant_name": "",\n'
            '  "invoice_number": "",\n'
            '  "invoice_date": "",\n'
            '  "gstin": "",\n'
            '  "tax_amount": "",\n'
            '  "total_gst": "",\n'
            '  "total_final_amount": ""\n'
            "}\n"
            "Rules:\n"
            "- total_final_amount = final bill (including tax)\n"
            "- tax_amount = subtotal BEFORE tax\n"
            "- total_gst = ONLY GST (CGST + SGST + IGST)\n"
            "- tax_amount + total_gst MUST equal total_final_amount\n"
            "- Return ONLY JSON"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:{mime_type};base64,{b64}"
                            }},
                        ],
                    }],
                    "max_tokens": 1000,
                },
            )

        result = response.json()
        if "choices" not in result:
            return None

        raw = result["choices"][0]["message"]["content"]
        raw = re.sub(r"```json|```", "", raw).strip()

        data = json.loads(raw)

        if not _groq_result_is_good(data):
            return None

        return _normalize_groq(data)

    except:
        return None


# ─────────────────────────────────────────────────────────────
# MAIN ENDPOINT
# ─────────────────────────────────────────────────────────────

@router.post("/process")
async def process_invoice(
    file: UploadFile = File(...),
    user_email: str  = Depends(get_current_user),
):

    # file type check
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    # 1. Try Groq
    extracted = await _extract_with_groq(file_bytes, file.content_type)

    # 2. OCR fallback
    if extracted is None:
        try:
            image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            loop = asyncio.get_event_loop()
            extracted = await loop.run_in_executor(
                None, extract_invoice_from_image, image
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"OCR failed: {str(e)}")

    # ─────────────────────────────────────────────────────────────
    # 🔥 VALIDATE + CORRECT (MAIN FIX)
    # ─────────────────────────────────────────────────────────────

    total   = _safe_float(extracted.get("TOTAL_AMOUNT"))
    taxable = _safe_float(extracted.get("TAXABLE_AMOUNT"))
    gst     = _safe_float(extracted.get("GST_AMOUNT"))

    # Fix: GST == TAXABLE
    if gst is not None and taxable is not None:
        if abs(gst - taxable) < 1:
            if total is not None:
                if total > gst:
                    taxable = total - gst
                else:
                    gst = total - taxable

    # Fill missing
    if total is not None:
        if taxable is None and gst is not None:
            taxable = total - gst
        elif gst is None and taxable is not None:
            gst = total - taxable

    # Final validation
    amounts_match = False
    if total and taxable and gst:
        amounts_match = abs((taxable + gst) - total) < 10

    # overwrite corrected values
    extracted["TOTAL_AMOUNT"]   = total
    extracted["TAXABLE_AMOUNT"] = taxable
    extracted["GST_AMOUNT"]     = gst

    extracted["validation"] = {
        "gst_valid": validate_gst(extracted.get("GSTIN")),
        "amounts_match": amounts_match,
    }

    # ─────────────────────────────────────────────────────────────
    # Upload
    # ─────────────────────────────────────────────────────────────

    result = upload_to_cloudinary(io.BytesIO(file_bytes))

    doc = {
        "filename": file.filename,
        "cloudinary_url": result["url"],
        "public_id": result["public_id"],
        "status": "processed",
        "user_email": user_email,
        **extracted,
    }

    insert_result = collection.insert_one(doc)

    return {
        "message": "✅ Invoice processed successfully",
        "record_id": str(insert_result.inserted_id),
        "cloudinary_url": result["url"],
        "extracted": extracted,
    }