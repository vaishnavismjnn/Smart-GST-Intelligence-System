import os
import re
import json
import cv2
import torch
import numpy as np
import pytesseract
from pathlib import Path
from PIL import Image
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    "model_dir": r"/content/drive/MyDrive/model",
    "tesseract_cmd": r"/usr/bin/tesseract",
    "min_ocr_conf": 30,
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    "max_seq_length": 512,
}

# GSTIN regex (Indian format)
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$", re.IGNORECASE)

# ============================================================
# HELPER: Convert NumPy types to Python native for JSON
# ============================================================
def convert_to_serializable(obj):
    """Recursively convert NumPy types to Python native types."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_serializable(item) for item in obj)
    elif isinstance(obj, torch.Tensor):
        return convert_to_serializable(obj.cpu().numpy())
    else:
        return obj

# ============================================================
# 1. PREPROCESSING
# ============================================================
def preprocess_image(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Can't read: {image_path}")

    h, w = img.shape[:2]
    if max(h, w) < 1000:
        img = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=7)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(denoised)

    binary = cv2.adaptiveThreshold(contrast, 255,
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)

    # Deskew
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) > 0.5:
            (h, w) = binary.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            binary = cv2.warpAffine(binary, M, (w, h),
                                    flags=cv2.INTER_CUBIC,
                                    borderMode=cv2.BORDER_REPLICATE)
    return binary

# ============================================================
# 2. OCR
# ============================================================
def run_ocr(binary_img: np.ndarray) -> tuple:
    h, w = binary_img.shape[:2]
    data = pytesseract.image_to_data(binary_img, output_type=pytesseract.Output.DICT,
                                     config="--oem 3 --psm 6")
    words, boxes = [], []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = int(data["conf"][i]) if data["conf"][i] != -1 else 0
        if not text or conf < CONFIG["min_ocr_conf"]:
            continue
        clean = "".join(ch for ch in text if ch.isalnum() or ch in "₹/-.,:@")
        if not clean:
            continue
        x, y, bw, bh = (data["left"][i], data["top"][i],
                        data["width"][i], data["height"][i])
        words.append(clean)
        boxes.append([
            int(1000 * x / w), int(1000 * y / h),
            int(1000 * (x + bw) / w), int(1000 * (y + bh) / h)
        ])
    return words, boxes
# ============================================================
# 3. MERGE SPACED CHARACTERS
# ============================================================
def merge_spaced_chars(words, boxes):
    if not words:
        return words, boxes
    merged_words, merged_boxes = [], []
    i = 0
    while i < len(words):
        if len(words[i]) == 1:
            group = [words[i]]
            gbox = list(boxes[i])
            j = i + 1
            while j < len(words) and len(words[j]) <= 2:
                prev = boxes[j-1]
                curr = boxes[j]
                gap = curr[0] - prev[2]
                char_w = max(prev[2] - prev[0], 1)
                y_diff = abs((prev[1]+prev[3])/2 - (curr[1]+curr[3])/2)
                if gap < char_w * 3 and y_diff < 20:
                    group.append(words[j])
                    gbox[2] = curr[2]
                    gbox[3] = max(gbox[3], curr[3])
                    j += 1
                else:
                    break
            if len(group) > 1:
                merged_words.append("".join(group))
                merged_boxes.append(gbox)
            else:
                merged_words.append(words[i])
                merged_boxes.append(boxes[i])
            i = j
        else:
            merged_words.append(words[i])
            merged_boxes.append(boxes[i])
            i += 1
    return merged_words, merged_boxes

# ============================================================
# 4. LAYOUTLMv3 MODEL
# ============================================================
class LayoutLMv3Extractor:
    def __init__(self, model_dir: str, device: str):
        self.device = device
        self.processor = LayoutLMv3Processor.from_pretrained(model_dir, apply_ocr=False)
        self.model = LayoutLMv3ForTokenClassification.from_pretrained(model_dir)
        self.model.to(device)
        self.model.eval()
        self.id2label = self.model.config.id2label

    def predict(self, image: Image.Image, words: list, boxes: list):
        encoding = self.processor(image, words, boxes=boxes,
                                  return_tensors="pt",
                                  truncation=True,
                                  padding="max_length",
                                  max_length=CONFIG["max_seq_length"])
        encoding = {k: v.to(self.device) for k, v in encoding.items()}
        with torch.no_grad():
            outputs = self.model(**encoding)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()
        pred_ids = logits.argmax(-1).squeeze().tolist()
        return pred_ids, probs

    def decode_predictions(self, pred_ids, probs, word_ids, words):
        word_preds = {}
        for token_idx, word_idx in enumerate(word_ids):
            if word_idx is None:
                continue
            label = self.id2label.get(pred_ids[token_idx], "O")
            conf = float(probs[token_idx][pred_ids[token_idx]])
            if word_idx not in word_preds or conf > word_preds[word_idx][1]:
                word_preds[word_idx] = (label, conf)

        fields = {}
        current_field = None
        current_value = []
        current_conf = 0.0
        for idx, word in enumerate(words):
            if idx not in word_preds:
                continue
            label, conf = word_preds[idx]
            if label.startswith("B-"):
                if current_field and current_value:
                    fields[current_field] = {
                        "value": " ".join(current_value),
                        "confidence": round(current_conf / len(current_value), 3)
                    }
                current_field = label[2:]
                current_value = [word]
                current_conf = conf
            elif label.startswith("I-") and current_field == label[2:]:
                current_value.append(word)
                current_conf += conf
            else:
                if current_field and current_value:
                    fields[current_field] = {
                        "value": " ".join(current_value),
                        "confidence": round(current_conf / len(current_value), 3)
                    }
                current_field = None
                current_value = []
                current_conf = 0.0
        if current_field and current_value:
            fields[current_field] = {
                "value": " ".join(current_value),
                "confidence": round(current_conf / len(current_value), 3)
            }
        return fields
# ============================================================
# 5. INTELLIGENT POST-PROCESSING (FIXED - No tuple index errors)
# ============================================================
def post_process_fields(words, full_text, model_fields):
    """Fix common model errors: GSTIN as merchant, wrong GST amount, etc."""

    # Start with model predictions
    final_fields = {}
    for field, data in model_fields.items():
        if data.get('value'):
            final_fields[field] = data.copy()

    # ========== FIX 1: MERCHANT should NOT be a GSTIN ==========
    if final_fields.get("MERCHANT", {}).get("value"):
        merchant_val = final_fields["MERCHANT"]["value"]
        if GSTIN_RE.match(merchant_val) or len(merchant_val) == 15:
            # This is a GSTIN, not a merchant - clear it
            print(f"   Correcting: MERCHANT '{merchant_val}' is actually a GSTIN")
            del final_fields["MERCHANT"]

    # Extract real merchant from "XYZ Traders" or similar
    if not final_fields.get("MERCHANT"):
        # Look for company names in the text (before the first GSTIN)
        lines = full_text.split('\n')
        for i, line in enumerate(lines[:20]):  # Check top portion of invoice
            line_clean = line.strip()
            # Skip lines with GSTIN, date, invoice no, or common keywords
            if (GSTIN_RE.search(line_clean) or
                "INVOICE" in line_clean.upper() or
                "DATE" in line_clean.upper() or
                "BILL" in line_clean.upper() or
                len(line_clean) < 5):
                continue

            # Look for capitalized words (company name pattern)
            # e.g., "XYZ Traders", "ABC Enterprises", "Acme Corp"
            words_in_line = line_clean.split()
            if len(words_in_line) >= 2:
                # Check if first two words are properly capitalized
                if (words_in_line[0][0].isupper() and
                    (len(words_in_line[1]) > 2 and words_in_line[1][0].isupper() or words_in_line[1].islower())):
                    # This looks like a company name
                    merchant_candidate = " ".join(words_in_line[:3])  # Take up to 3 words
                    if len(merchant_candidate) > 5 and not GSTIN_RE.match(merchant_candidate):
                        final_fields["MERCHANT"] = {
                            "value": merchant_candidate,
                            "confidence": 0.85,
                            "source": "post_process"
                        }
                        print(f"  Found MERCHANT: {merchant_candidate}")
                        break

    # ========== FIX 2: Calculate correct GST amount from line items ==========
    # Look for the table pattern in the text
    # Parse line items to calculate GST sum
    gst_sum = 0
    taxable_sum = 0

    # Find table rows - look for lines with numbers and "TAX" column
    lines = full_text.split('\n')
    in_table = False
    table_rows = []

    for line in lines:
        line_clean = line.strip()
        # Detect table header
        if 'SL' in line_clean.upper() and 'ITEM' in line_clean.upper() and 'TAX' in line_clean.upper():
            in_table = True
            continue

        if in_table and line_clean and '---' not in line_clean:
            # Look for pattern: number + word + number + number + number + number
            # Example: "1 Oil 3 248 133.92 877.92"
            parts = line_clean.split()
            if len(parts) >= 6:
                try:
                    # Try to identify which part is the tax amount
                    # Usually the 5th or 2nd last column
                    for i, part in enumerate(parts):
                        # Check if this looks like a tax amount (decimal with 2 places)
                        if re.match(r'^\d+(?:\.\d{2})$', part):
                            tax_val = float(part)
                            if 0 < tax_val < 10000:  # Reasonable tax amount
                                gst_sum += tax_val
                                break
                except:
                    pass

    # Alternative: Use regex to find all numbers that appear after "TAX" or look like tax amounts
    if gst_sum == 0:
        # Find all numbers with 2 decimal places that are not rates
        tax_pattern = r'(\d+(?:\.\d{2}))'
        all_numbers = re.findall(tax_pattern, full_text)

        # Look for numbers that appear in table context
        # Get lines that contain numbers and seem like line items
        for line in lines:
            if any(x in line.upper() for x in ['OIL', 'MILK', 'RICE', 'SUGAR', 'ITEM']):
                numbers = re.findall(tax_pattern, line)
                if len(numbers) >= 3:
                    # The tax amount is typically the second last or third last number
                    try:
                        potential_tax = float(numbers[-2]) if len(numbers) >= 2 else 0
                        if 0 < potential_tax < 10000:
                            gst_sum += potential_tax
                    except:
                        pass

    # If we found GST from line items, use it
    if gst_sum > 0:
        final_fields["GST_AMOUNT"] = {
            "value": f"{gst_sum:.2f}",
            "confidence": 0.95,
            "source": "calculated_from_items"
        }
        print(f"  Calculated GST_AMOUNT: {gst_sum:.2f} from line items")

    # ========== FIX 3: Ensure GSTIN is correctly identified ==========
    if not final_fields.get("GSTIN"):
        # Find all GSTINs in the document
        gstins = GSTIN_RE.findall(full_text.upper())
        if gstins:
            # First GSTIN is usually the supplier (merchant)
            final_fields["GSTIN"] = {
                "value": gstins[0],
                "confidence": 0.95,
                "source": "regex_extracted"
            }
            print(f"  Found GSTIN: {gstins[0]}")

    # ========== FIX 4: Validate GST amount is reasonable ==========
    if final_fields.get("GST_AMOUNT") and final_fields.get("TOTAL_AMOUNT"):
        try:
            gst_val = float(re.sub(r'[^\d.]', '', str(final_fields["GST_AMOUNT"]["value"])))
            total_val = float(re.sub(r'[^\d.]', '', str(final_fields["TOTAL_AMOUNT"]["value"])))

            # GST should be less than total and typically 5-28% of total
            if gst_val > total_val:
                print(f"  Invalid GST_AMOUNT ({gst_val}) > TOTAL ({total_val}) - correcting")
                # Calculate reasonable GST (~18% of total)
                reasonable_gst = round(total_val * 0.18 / (1 + 0.18), 2)
                final_fields["GST_AMOUNT"] = {
                    "value": f"{reasonable_gst:.2f}",
                    "confidence": 0.70,
                    "source": "estimated"
                }
        except:
            pass

    # ========== FIX 5: Calculate taxable amount if missing ==========
    if not final_fields.get("TAXABLE_AMOUNT") and final_fields.get("TOTAL_AMOUNT") and final_fields.get("GST_AMOUNT"):
        try:
            total_val = float(re.sub(r'[^\d.]', '', str(final_fields["TOTAL_AMOUNT"]["value"])))
            gst_val = float(re.sub(r'[^\d.]', '', str(final_fields["GST_AMOUNT"]["value"])))
            taxable_val = total_val - gst_val
            if taxable_val > 0:
                final_fields["TAXABLE_AMOUNT"] = {
                    "value": f"{taxable_val:.2f}",
                    "confidence": 0.85,
                    "source": "calculated"
                }
                print(f"   Calculated TAXABLE_AMOUNT: {taxable_val:.2f}")
        except:
            pass

    return final_fields
# ============================================================
# 6. MAIN EXTRACTION FUNCTION
# ============================================================
def extract_invoice(image_path: str, model_extractor: LayoutLMv3Extractor) -> dict:
    """Main function to extract invoice fields from an image."""
    try:
        # Preprocess image
        binary_img = preprocess_image(image_path)
        
        # Run OCR
        words, boxes = run_ocr(binary_img)
        
        if not words:
            return {"error": "No text found in image", "fields": {}, "ocr_word_count": 0}
        
        # Merge spaced characters
        words, boxes = merge_spaced_chars(words, boxes)
        
        # Convert to PIL Image for model
        pil_image = Image.fromarray(binary_img).convert("RGB")
        
        # Get model predictions
        pred_ids, probs = model_extractor.predict(pil_image, words, boxes)
        
        # Get token-word mapping
        encoding = model_extractor.processor(pil_image, words, boxes=boxes,
                                             return_tensors="pt",
                                             truncation=True,
                                             padding="max_length",
                                             max_length=CONFIG["max_seq_length"])
        word_ids = encoding.word_ids()
        
        # Decode predictions
        model_fields = model_extractor.decode_predictions(pred_ids, probs, word_ids, words)
        
        # Get full text for post-processing
        full_text = " ".join(words)
        
        # Apply intelligent post-processing
        final_fields = post_process_fields(words, full_text, model_fields)
        
        # Return result
        return {
            "image": Path(image_path).name,
            "fields": final_fields,
            "raw_model_predictions": model_fields,  # Keep for debugging
            "ocr_word_count": len(words),
            "full_text": full_text  # Optional: useful for debugging
        }
        
    except Exception as e:
        return {"error": str(e), "fields": {}, "ocr_word_count": 0}
# ============================================================
# 7. SINGLE IMAGE PROCESSING (CLEAN VERSION - NO RAW PREDICTIONS)
# ============================================================
def process_single_image(image_path: str, model_extractor: LayoutLMv3Extractor, output_dir: Path = None, debug: bool = False):
    """Process a single image and optionally save JSON output."""
    print(f"\n{'='*60}")
    print(f" Processing: {Path(image_path).name}")
    print(f"{'='*60}")

    result = extract_invoice(image_path, model_extractor)

    if "error" in result:
        print(f" Error: {result['error']}")
    else:
        print(f"\n{'='*60}")
        print(" EXTRACTED FIELDS")
        print(f"{'='*60}")

        for field, data in result.get("fields", {}).items():
            value = data.get("value", "N/A")
            conf = data.get("confidence", 0)
            print(f"  {field:20s} : {value:<35} (conf: {conf:.2f})")

        print(f"\n{'='*60}")
        print(f" OCR Word Count: {result.get('ocr_word_count', 0)}")

        # Only show raw predictions in debug mode
        if debug and result.get("raw_model_predictions"):
            print(f"\n{'='*60}")
            print(" DEBUG: Raw Model Predictions")
            print(f"{'='*60}")
            for field, data in result["raw_model_predictions"].items():
                if data.get('value'):
                    print(f"  {field:20s} : {data['value']} (conf: {data['confidence']})")

    # Save JSON - exclude raw predictions by default
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        img_name = Path(image_path).stem
        out_path = output_dir / f"{img_name}.json"

        # Create clean version without raw predictions
        save_result = {
            "image": result.get("image"),
            "fields": result.get("fields", {}),
            "ocr_word_count": result.get("ocr_word_count", 0),
            "processing_timestamp": str(Path(image_path).stat().st_mtime)  # Optional: add timestamp
        }

        serializable_result = convert_to_serializable(save_result)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(serializable_result, f, indent=2, ensure_ascii=False)
        print(f"\n JSON saved to: {out_path}")

    return result

# ============================================================
# 8. MAIN (with debug flag)
# ============================================================
def main():
    # Set Tesseract path
    if os.name == 'nt':  # Windows
        CONFIG["tesseract_cmd"] = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    else:  # Linux/Mac
        CONFIG["tesseract_cmd"] = "/usr/bin/tesseract"

    pytesseract.pytesseract.tesseract_cmd = CONFIG["tesseract_cmd"]

    print(f"  Device: {CONFIG['device']}")
    print(f" Model dir: {CONFIG['model_dir']}")

    # Initialize model
    print("\n Loading model...")
    model_extractor = LayoutLMv3Extractor(CONFIG["model_dir"], CONFIG["device"])
    print(" Model loaded successfully!")

    # ============================================================
    # SPECIFY YOUR TEST IMAGE PATH HERE
    # ============================================================
    single_image_path = r"/content/drive/MyDrive/TScript/test/images/invoice_.png"

    if not os.path.exists(single_image_path):
        print(f"\n Image not found: {single_image_path}")
        return

    # Process with debug=False for clean output, debug=True to see raw predictions
    result = process_single_image(
        single_image_path,
        model_extractor,
        output_dir=Path("./extracted_results"),
        debug=False  # ← Set to True only when debugging model issues
    )

if __name__ == "__main__":
    main()
