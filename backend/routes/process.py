from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from PIL import Image
import io

from backend.services.validation import validate_gst, validate_amounts
from backend.services.extract_invoice import extract_invoice_from_image
from backend.services.upload_service import upload_to_cloudinary
from backend.db import collection

router = APIRouter()

@router.post("/process")
async def process_invoice(files: List[UploadFile] = File(...)):  # ✅ List
    results = []

    for file in files:
        file_bytes = await file.read()

        # 1. OCR extraction
        try:
            image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            extracted = extract_invoice_from_image(image)
        except Exception as e:
            results.append({"filename": file.filename, "error": f"OCR failed: {str(e)}"})
            continue

        # 2. Validate
        extracted["validation"] = {
            "gst_valid":     validate_gst(extracted.get("GSTIN")),
            "amounts_match": validate_amounts(
                                 extracted.get("TOTAL_AMOUNT"),
                                 extracted.get("TAXABLE_AMOUNT"),
                                 extracted.get("GST_AMOUNT")
                             )
        }

        # 3. Upload to Cloudinary
        try:
            result = upload_to_cloudinary(io.BytesIO(file_bytes))
        except Exception as e:
            results.append({"filename": file.filename, "error": f"Upload failed: {str(e)}"})
            continue

        # 4. Save to MongoDB
        doc = {
            "filename":       file.filename,
            "cloudinary_url": result["url"],
            "public_id":      result["public_id"],
            "status":         "processed",
            **extracted
        }
        insert_result = collection.insert_one(doc)

        results.append({
            "message":        "✅ Invoice processed successfully",
            "filename":       file.filename,
            "cloudinary_url": result["url"],
            "record_id":      str(insert_result.inserted_id),
            "extracted":      extracted
        })

    return {"total": len(files), "results": results}