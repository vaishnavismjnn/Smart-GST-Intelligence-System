import os
import re
import json
import time
import hashlib
import traceback
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytesseract
from PIL import Image
from tqdm import tqdm

# ──────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────
CONFIG = {
    "image_dir"      : r"F:\Dataset processed",
    "txt_dir"        : r"F:\ocr_output\printed",
    "json_output_dir": r"F:\layout_json_output",
    "tesseract_cmd"  : r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "workers"        : 6,
    "skip_existing"  : True,
    "min_confidence" : 20,
    "img_extensions" : {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"},
}

BBOX_NORM = 1000  # LayoutLMv3 normalisation

# ──────────────────────────────────────────────────────────────────
# EXPENSE CATEGORY KEYWORDS
# ──────────────────────────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    "Meals"         : ["restaurant", "hotel", "cafe", "food", "dining",
                       "swiggy", "zomato", "biryani", "meals", "catering"],
    "Travel"        : ["travel", "flight", "railway", "cab", "uber",
                       "ola", "taxi", "bus", "irctc", "transport"],
    "Accommodation" : ["lodge", "inn", "resort", "stay", "accommodation",
                       "oyo", "makemytrip", "booking"],
    "Fuel"          : ["petrol", "diesel", "fuel", "hp", "bharat petroleum",
                       "indian oil", "pump"],
    "Stationery"    : ["stationery", "paper", "pen", "office", "supplies",
                       "printer", "ink"],
    "Medical"       : ["pharmacy", "medical", "hospital", "clinic",
                       "medicine", "apollo", "diagnostic"],
    "Utilities"     : ["electricity", "water", "internet", "broadband",
                       "airtel", "jio", "bsnl"],
    "Shopping"      : ["mart", "store", "shop", "mall", "amazon",
                       "flipkart", "retail"],
}

GST_SLABS = {0, 5, 12, 18, 28}

GSTIN_RE = re.compile(
    r"^\d{2}[A-Za-z]{5}\d{4}[A-Za-z][A-Za-z\d]Z[A-Za-z\d]$", re.IGNORECASE
)


# ──────────────────────────────────────────────────────────────────
# STEP 1 — TESSERACT TSV EXTRACTION
# ──────────────────────────────────────────────────────────────────
def run_tesseract_tsv(img_path: str) -> tuple:
    img  = Image.open(img_path)
    w, h = img.size
    tsv  = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = []
    for i in range(len(tsv["text"])):
        text = tsv["text"][i].strip()
        conf = int(tsv["conf"][i])
        if not text or conf < CONFIG["min_confidence"]:
            continue
        x0 = tsv["left"][i];  y0 = tsv["top"][i]
        x1 = x0 + tsv["width"][i]; y1 = y0 + tsv["height"][i]
        words.append({
            "text"      : text,
            "bbox"      : [
                int(x0 * BBOX_NORM / w), int(y0 * BBOX_NORM / h),
                int(x1 * BBOX_NORM / w), int(y1 * BBOX_NORM / h),
            ],
            "bbox_raw"  : [x0, y0, x1, y1],
            "confidence": round(conf / 100, 2),
            "block_num" : tsv["block_num"][i],
        })
    return words, w, h


# ──────────────────────────────────────────────────────────────────
# STEP 2 — LOAD + CLEAN EXISTING TXT
# ──────────────────────────────────────────────────────────────────
def load_txt(txt_path: str) -> str:
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        text = re.sub(r"[''`]", "'", text)
        text = re.sub(r"[;]+(?=\s)", "", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()
    except Exception:
        return ""


def clean_word(word: str) -> str:
    return re.sub(r"^['\-;:,\.]+|['\-;:,\.]+$", "", word) or word


# ──────────────────────────────────────────────────────────────────
# STEP 3 — LAYOUT REGION DETECTION
# ──────────────────────────────────────────────────────────────────
REGION_KEYWORDS = {
    "HEADER"      : ["invoice", "bill", "receipt", "tax invoice",
                     "invoice no", "invoice number", "date of issue"],
    "SELLER"      : ["seller", "from", "vendor", "supplier", "sold by",
                     "gstin", "iban", "tax id", "ship from"],
    "BUYER"       : ["buyer", "client", "customer", "bill to", "ship to",
                     "sold to", "consignee"],
    "ITEMS_TABLE" : ["description", "qty", "quantity", "unit price",
                     "net price", "net worth", "vat", "gross", "hsn",
                     "sac", "item", "particulars", "rate", "um", "tax",
                     "sl", "item", "total"],
    "SUMMARY"     : ["total", "subtotal", "sub total", "grand total",
                     "amount payable", "amount due", "summary",
                     "cgst", "sgst", "igst", "taxable"],
}


def classify_region(block_words: list) -> str:
    block_text = " ".join(w["text"] for w in block_words).lower()
    block_y    = min(w["bbox"][1] for w in block_words)
    scores = {r: 0 for r in REGION_KEYWORDS}
    for region, keywords in REGION_KEYWORDS.items():
        for kw in keywords:
            if kw in block_text:
                scores[region] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        if block_y < BBOX_NORM * 0.15:
            return "HEADER"
        elif block_y > BBOX_NORM * 0.75:
            return "SUMMARY"
        return "OTHER"
    return best


def assign_regions(words: list) -> list:
    blocks = {}
    for w in words:
        blocks.setdefault(w.get("block_num", 0), []).append(w)
    block_regions = {bn: classify_region(bw) for bn, bw in blocks.items()}
    for w in words:
        w["region"] = block_regions.get(w.get("block_num", 0), "OTHER")
        w.pop("block_num", None)
    return words


# ──────────────────────────────────────────────────────────────────
# STEP 4 — FIELD EXTRACTION
# ──────────────────────────────────────────────────────────────────

def _eu_float(s: str):
    s = re.sub(r"[₹$€£°\s]", "", s).lstrip(".")
    if re.search(r",\d{2}$", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def _is_valid_amount_token(text: str) -> bool:
    cleaned = re.sub(r"[₹$€£\s]", "", text)
    return bool(re.match(r"^[\d,\.]+$", cleaned)) and bool(re.search(r"\d", cleaned))


def _clean_amount(text: str):
    return _eu_float(text)


# ── 4b. Merchant ──────────────────────────────────────────────────

def extract_merchant(words: list) -> dict:
    """
    Four-pass merchant extraction with explicit BUYER exclusion.

    Pass 1 : SELLER region, any x
    Pass 2 : HEADER region, right side (x > 400)
    Pass 3 : ANY region except BUYER, right side (x > 400), top 35%
    Pass 4 : ANY region except BUYER, top 20% — last resort

    BUYER words are blacklisted by object id so they can never become
    the merchant regardless of which pass runs or their position.
    """
    noise = {"invoice", "bill", "tax", "gst", "receipt", "gstin", "seller",
             "date", "no", "number", "from", "to", "buyer", "client",
             "iban", "id", "issue", "original", "copy", "duplicate",
             "print", "printed", "authorized", "signature", "total",
             "bangalore", "chennai", "mumbai", "delhi", "hyderabad",
             "kolkata", "pune", "ahmedabad", "bengaluru", "mysuru"}

    # Tag every word in the BUYER region — never use these as merchant
    buyer_ids = {id(w) for w in words if w.get("region") == "BUYER"}

    def is_valid(w):
        return (
            id(w) not in buyer_ids
            and w.get("bbox") is not None
            and len(w["text"]) > 2
            and not re.match(r"^[\d\W]+$", w["text"])
            and w["text"].lower() not in noise
            and not GSTIN_RE.match(w["text"])
            and w["bbox"][0] > BBOX_NORM * 0.3
        )

    # Pass 1: SELLER region, any x
    seller_words = [w for w in words if w.get("region") == "SELLER" and is_valid(w)]
    seller_words = sorted(seller_words, key=lambda w: (w["bbox"][1], w["bbox"][0]))

    # Pass 2: HEADER region, right side (x > 400)
    if not seller_words:
        seller_words = [
            w for w in words
            if w.get("region") == "HEADER"
            and w["bbox"][0] > BBOX_NORM * 0.4
            and is_valid(w)
        ]
        seller_words = sorted(seller_words, key=lambda w: (w["bbox"][1], w["bbox"][0]))

    # Pass 3: any region except BUYER, right side, top 35%
    if not seller_words:
        seller_words = [
            w for w in words
            if w.get("bbox") is not None
            and w["bbox"][0] > BBOX_NORM * 0.4
            and w["bbox"][1] < BBOX_NORM * 0.35
            and is_valid(w)
        ]
        seller_words = sorted(seller_words, key=lambda w: (w["bbox"][1], w["bbox"][0]))

    # Pass 4: any region except BUYER, top 20% — last resort
    if not seller_words:
        seller_words = [
            w for w in words
            if w.get("bbox") is not None
            and w["bbox"][1] < BBOX_NORM * 0.20
            and is_valid(w)
        ]
        seller_words = sorted(seller_words, key=lambda w: (w["bbox"][1], w["bbox"][0]))

    candidates = [w["text"] for w in seller_words][:4]
    if candidates:
        name = " ".join(candidates[:3]).title()
        conf = round(min(0.70 + 0.05 * len(candidates), 0.90), 2)
        return {"value": name, "confidence": conf, "raw_token": name}

    return {"value": None, "confidence": 0.0, "raw_token": None}


# ── 4c. Date ──────────────────────────────────────────────────────

def extract_date(full_text: str) -> dict:
    patterns = [
        (r"\b(\d{2}[\/\-]\d{2}[\/\-]\d{4})\b",   ["%d/%m/%Y", "%d-%m-%Y",
                                                    "%m/%d/%Y", "%m-%d-%Y"]),
        (r"\b(\d{4}[\/\-]\d{2}[\/\-]\d{2})\b",   ["%Y-%m-%d", "%Y/%m/%d"]),
        (r"\b(\d{1,2}[-/ ]\w{3,9}[-/ ]\d{4})\b", ["%d %B %Y", "%d %b %Y",
                                                    "%d-%b-%Y", "%d-%B-%Y"]),
    ]
    for pat, fmts in patterns:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            raw_token = m.group(1)
            for fmt in fmts:
                try:
                    dt = datetime.strptime(raw_token, fmt)
                    return {"value": dt.strftime("%Y-%m-%d"),
                            "raw_token": raw_token, "confidence": 0.98}
                except ValueError:
                    continue
            return {"value": raw_token, "raw_token": raw_token, "confidence": 0.75}
    return {"value": None, "raw_token": None, "confidence": 0.0}


# ── 4d. GSTIN ─────────────────────────────────────────────────────

def extract_gstin(full_text: str) -> dict:
    pattern = r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1})\b"
    matches = re.findall(pattern, full_text.upper())
    if matches:
        return {"value": matches[0], "raw_token": matches[0], "confidence": 0.95}
    return {"value": None, "raw_token": None, "confidence": 0.0}


# ── 4e. Amounts ───────────────────────────────────────────────────

def extract_amounts(words: list, full_text: str) -> dict:
    """
    Extraction order (most reliable first):

    Step 1 : total_amount extracted first — used as filter baseline
             for all subsequent steps.
    Step 2 : TAX column sum — highest priority for gst_amount.
             Runs BEFORE keyword scan. Excludes BUYER/SUMMARY regions
             and TOTAL column bleed.
    Step 3 : Keyword scan for taxable_amount and gst_amount.
             BUYER region lines skipped. Noise guard rejects values
             below 0.5% of total.
    Step 4 : CGST + SGST explicit line scan. No upper cap so large
             values like 4502.88 are accepted. Only basic sanity check
             (must be < total).
    Step 5 : Mid-size number fallback. Collects numbers between 1%
             and 60% of total from SUMMARY/OTHER regions, tries pairs
             that sum to a GST-slab-consistent amount, then singles.
    Step 6 : Infer whichever of taxable/gst is still missing.
    """
    amounts = {
        "taxable_amount": {"value": None, "raw_token": None},
        "gst_amount"    : {"value": None, "raw_token": None},
        "total_amount"  : {"value": None, "raw_token": None},
    }

    keyword_map = {
        "taxable_amount": [
            r"taxable\s*(amount|value|base)",
            r"sub\s*total",
            r"net\s*amount",
            r"basic\s*amount",
            r"assessable\s*value",
            r"taxable\s*value",
            r"amount\s*before\s*tax",
        ],
        "gst_amount": [
            r"(cgst|sgst|igst|gst)\s*(amount|tax|@[\d\.]+\s*%)?",
            r"tax\s*amount",
            r"total\s*tax",
            r"vat",
            r"output\s*tax",
        ],
        "total_amount": [
            r"(grand\s*)?total\s*(amount|due|payable)?",
            r"amount\s*(payable|due|total)",
            r"net\s*payable",
            r"invoice\s*total",
            r"bill\s*amount",
            r"total\s*bill",
            r"payable\s*amount",
            r"net\s*total",
        ],
    }

    # ── Build lines from word bboxes ──────────────────────────────
    sorted_words = sorted(words, key=lambda w: (w["bbox"][1] // 15, w["bbox"][0]))
    lines, current_line, prev_y = [], [], -1
    for w in sorted_words:
        y = w["bbox"][1]
        if prev_y == -1 or abs(y - prev_y) < 20:
            current_line.append(w)
        else:
            if current_line:
                lines.append(current_line)
            current_line = [w]
        prev_y = y
    if current_line:
        lines.append(current_line)

    def find_amount_in_line(line_words) -> tuple:
        texts = [w["text"] for w in line_words]
        for t in reversed(texts):
            if not _is_valid_amount_token(t):
                continue
            v = _eu_float(t)
            if v and v > 0:
                return v, t
        if len(texts) >= 2:
            joined = texts[-2] + texts[-1]
            if _is_valid_amount_token(joined):
                v = _eu_float(joined)
                if v and v > 0:
                    return v, f"{texts[-2]} {texts[-1]}"
        return None, None

    def line_has_buyer(line_words) -> bool:
        return any(w.get("region") == "BUYER" for w in line_words)

    # ── Step 1: Extract total first ───────────────────────────────
    for line in lines:
        if amounts["total_amount"]["value"] is not None:
            break
        if line_has_buyer(line):
            continue
        line_text = " ".join(w["text"] for w in line).lower()
        for pat in keyword_map["total_amount"]:
            if re.search(pat, line_text, re.IGNORECASE):
                val, raw = find_amount_in_line(line)
                if val:
                    amounts["total_amount"]["value"]     = val
                    amounts["total_amount"]["raw_token"] = raw
                break

    # Fallback: largest number in bottom 30%
    if amounts["total_amount"]["value"] is None:
        bottom = [w for w in words if w["bbox"][1] > BBOX_NORM * 0.70]
        cands  = [(w["text"], _eu_float(w["text"])) for w in bottom
                  if _is_valid_amount_token(w["text"])]
        cands  = [(t, n) for t, n in cands if n and n > 10]
        if cands:
            best_t, best_n = max(cands, key=lambda x: x[1])
            amounts["total_amount"]["value"]     = best_n
            amounts["total_amount"]["raw_token"] = best_t

    total_val = amounts["total_amount"]["value"]

    # ── Step 2: TAX column sum (PRIORITY) ────────────────────────
    tax_headers = [
        w for w in words
        if w["text"].upper() in ("TAX", "TAX.")
        and w.get("region") not in ("BUYER", "SUMMARY")
    ]
    tax_col_found = False

    if tax_headers:
        tax_header   = min(tax_headers, key=lambda w: w["bbox"][1])
        tax_x_center = (tax_header["bbox"][0] + tax_header["bbox"][2]) // 2
        tax_header_y = tax_header["bbox"][1]

        # Find TOTAL column x-center to exclude bleed
        total_headers = [
            w for w in words
            if w["text"].upper() in ("TOTAL", "AMOUNT", "NET")
            and w["bbox"][1] <= tax_header_y + 30
        ]
        total_x_center = None
        if total_headers:
            th = max(total_headers, key=lambda w: w["bbox"][0])
            total_x_center = (th["bbox"][0] + th["bbox"][2]) // 2

        tax_col_vals = []
        min_thresh   = (total_val * 0.01) if total_val else 0

        for w in words:
            if w.get("region") in ("BUYER", "HEADER", "SUMMARY"):
                continue
            w_x = (w["bbox"][0] + w["bbox"][2]) // 2
            if total_x_center and abs(w_x - total_x_center) < 60:
                continue
            if (abs(w_x - tax_x_center) < 90
                    and w["bbox"][1] > tax_header_y
                    and _is_valid_amount_token(w["text"])):
                v = _eu_float(w["text"])
                if v and v > min_thresh and (total_val is None or v < total_val * 0.99):
                    tax_col_vals.append((v, w["text"]))

        if tax_col_vals:
            gst_sum = round(sum(v for v, _ in tax_col_vals), 2)
            amounts["gst_amount"]["value"]     = gst_sum
            amounts["gst_amount"]["raw_token"] = "+".join(t for _, t in tax_col_vals)
            tax_col_found = True

    # ── Step 3: Keyword scan for taxable + gst ───────────────────
    for line in lines:
        if line_has_buyer(line):
            continue
        line_text = " ".join(w["text"] for w in line).lower()
        for field in ("gst_amount", "taxable_amount"):
            if amounts[field]["value"] is not None:
                continue
            # Don't override TAX column result with keyword scan
            if field == "gst_amount" and tax_col_found:
                continue
            for pat in keyword_map[field]:
                if re.search(pat, line_text, re.IGNORECASE):
                    val, raw = find_amount_in_line(line)
                    if val:
                        # Reject noise: value < 0.5% of total
                        if total_val and val < total_val * 0.005:
                            continue
                        amounts[field]["value"]     = val
                        amounts[field]["raw_token"] = raw
                    break

    # ── Step 4: CGST + SGST explicit line scan ────────────────────
    # No upper cap — large CGST/SGST values (e.g. 4502.88) must pass.
    if amounts["gst_amount"]["value"] is None:
        cgst_val = cgst_raw = sgst_val = sgst_raw = None
        for line in lines:
            if line_has_buyer(line):
                continue
            line_text = " ".join(w["text"] for w in line).lower()
            if re.search(r"\bcgst\b", line_text) and cgst_val is None:
                v, r = find_amount_in_line(line)
                if v and v > 0 and (total_val is None or v < total_val):
                    cgst_val, cgst_raw = v, r
            if re.search(r"\bsgst\b", line_text) and sgst_val is None:
                v, r = find_amount_in_line(line)
                if v and v > 0 and (total_val is None or v < total_val):
                    sgst_val, sgst_raw = v, r

        if cgst_val and sgst_val:
            amounts["gst_amount"]["value"]     = round(cgst_val + sgst_val, 2)
            amounts["gst_amount"]["raw_token"] = f"{cgst_raw}+{sgst_raw}"
        elif cgst_val:
            amounts["gst_amount"]["value"]     = cgst_val
            amounts["gst_amount"]["raw_token"] = cgst_raw
        elif sgst_val:
            amounts["gst_amount"]["value"]     = sgst_val
            amounts["gst_amount"]["raw_token"] = sgst_raw

    # ── Step 5: Mid-size number fallback ─────────────────────────
    # Collects numbers between 1% and 60% of total from SUMMARY/OTHER,
    # tries pairs that sum to a GST-slab amount, then single values.
    if amounts["gst_amount"]["value"] is None and total_val:
        mid_cands = []
        for w in words:
            if w.get("region") in ("BUYER", "HEADER", "ITEMS_TABLE"):
                continue
            if not _is_valid_amount_token(w["text"]):
                continue
            v = _eu_float(w["text"])
            if v and total_val * 0.01 < v < total_val * 0.60:
                mid_cands.append((v, w["text"]))

        best = None
        # Try pairs first (CGST + SGST style)
        for i in range(len(mid_cands)):
            for j in range(i + 1, len(mid_cands)):
                pair_sum    = round(mid_cands[i][0] + mid_cands[j][0], 2)
                taxable_est = round(total_val - pair_sum, 2)
                if taxable_est > 0:
                    pct = round((pair_sum / taxable_est) * 100)
                    if pct in GST_SLABS and pair_sum < total_val:
                        best = (pair_sum,
                                f"{mid_cands[i][1]}+{mid_cands[j][1]}")
                        break
            if best:
                break

        # Try single values matching a slab
        if not best:
            for v, raw in mid_cands:
                taxable_est = round(total_val - v, 2)
                if taxable_est > 0:
                    pct = round((v / taxable_est) * 100)
                    if pct in GST_SLABS:
                        best = (v, raw)
                        break

        if best:
            amounts["gst_amount"]["value"]     = best[0]
            amounts["gst_amount"]["raw_token"] = best[1]
        if amounts["gst_amount"]["value"] is None and total_val:
            nums = [
                _eu_float(w["text"]) for w in words
                if _is_valid_amount_token(w["text"])
            ]
            nums = [n for n in nums if n and n < total_val]

            if len(nums) >= 2:
                gst = sum(sorted(nums)[-3:])
                amounts["gst_amount"]["value"] = round(gst, 2)
                amounts["gst_amount"]["raw_token"] = "fallback_sum"

    # ── Step 6: Infer whichever field is still missing ────────────
    tax     = amounts["gst_amount"]["value"]
    taxable = amounts["taxable_amount"]["value"]
    total   = amounts["total_amount"]["value"]

    if total and taxable and not tax:
        diff = round(total - taxable, 2)
        if diff > 0:
            amounts["gst_amount"]["value"]     = diff
            amounts["gst_amount"]["raw_token"] = str(diff)

    if total and tax and not taxable:
        diff = round(total - tax, 2)
        if diff > 0:
            amounts["taxable_amount"]["value"]     = diff
            amounts["taxable_amount"]["raw_token"] = str(diff)
    return amounts


# ── 4f. Category ──────────────────────────────────────────────────

def extract_category(full_text: str, merchant: str) -> str:
    combined = (full_text + " " + (merchant or "")).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                return category
    return "Others"


# ──────────────────────────────────────────────────────────────────
# STEP 4g — INVOICE NUMBER
# ──────────────────────────────────────────────────────────────────

def extract_invoice_no(full_text: str) -> dict:
    pattern = r"Invoice\s*[;,]?\s*no\s*[;:,]?\s*[:#]?\s*(\d{5,})"
    m = re.search(pattern, full_text, re.IGNORECASE)
    if m:
        return {"value": m.group(1), "raw_token": m.group(1), "confidence": 0.97}
    m2 = re.search(r"(?:invoice|inv)[^\d]{0,10}(\d{6,})", full_text, re.IGNORECASE)
    if m2:
        return {"value": m2.group(1), "raw_token": m2.group(1), "confidence": 0.80}
    return {"value": None, "raw_token": None, "confidence": 0.0}


# ──────────────────────────────────────────────────────────────────
# STEP 5 — VALIDATION
# ──────────────────────────────────────────────────────────────────

def validate_gst(taxable, gst, total) -> bool:
    if not (taxable and gst and total):
        return False
    total_match = abs(round(taxable + gst, 2) - total) < 1.0
    gst_pct     = round((gst / taxable) * 100) if taxable else 0
    return total_match and gst_pct in GST_SLABS


def audit_score(merchant, date, gstin, invoice_no, taxable, gst, total) -> int:
    fields = [merchant, date, gstin, invoice_no, taxable, gst, total]
    filled = sum(1 for f in fields if f is not None)
    return round((filled / len(fields)) * 100)


def image_hash(img_path: str) -> str:
    h = hashlib.md5()
    with open(img_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ──────────────────────────────────────────────────────────────────
# STEP 6 — BIO LABEL ASSIGNMENT
# ──────────────────────────────────────────────────────────────────

def _tokenize_for_bio(text: str) -> list:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def assign_bio_labels(words: list, label_fields: dict) -> list:
    field_tokens: dict[str, list] = {}
    for field, value in label_fields.items():
        if not value:
            continue
        toks = _tokenize_for_bio(str(value))
        if toks:
            field_tokens[field] = toks

    flat_tokens:   list = []
    flat_word_idx: list = []
    for wi, w in enumerate(words):
        toks = _tokenize_for_bio(w["text"]) or [""]
        flat_tokens.extend(toks)
        flat_word_idx.extend([wi] * len(toks))

    flat_labels = ["O"] * len(flat_tokens)

    for field, ftoks in field_tokens.items():
        n = len(ftoks)
        for i in range(len(flat_tokens) - n + 1):
            if flat_tokens[i : i + n] == ftoks:
                matched_surface = "".join(flat_tokens[i : i + n])
                if field != "GSTIN" and GSTIN_RE.match(matched_surface):
                    continue
                flat_labels[i] = f"B-{field}"
                for j in range(1, n):
                    flat_labels[i + j] = f"I-{field}"

    word_label_map: dict = {}
    for fi, label in enumerate(flat_labels):
        wi = flat_word_idx[fi]
        if wi not in word_label_map:
            word_label_map[wi] = label
        elif label.startswith("B-") and word_label_map[wi] == "O":
            word_label_map[wi] = label

    for wi, w in enumerate(words):
        w["label"] = word_label_map.get(wi, "O")

    return words


# ──────────────────────────────────────────────────────────────────
# CORE: PROCESS SINGLE IMAGE
# ──────────────────────────────────────────────────────────────────

def process_single(args: tuple) -> dict:
    img_path, json_out_path = args
    stem = Path(img_path).stem

    if CONFIG["skip_existing"] and Path(json_out_path).exists():
        return {"status": "skipped", "file": img_path}

    t0 = time.time()
    try:
        words, img_w, img_h = run_tesseract_tsv(img_path)

        txt_path  = Path(CONFIG["txt_dir"]) / f"{stem}.txt"
        full_txt  = load_txt(str(txt_path)) if txt_path.exists() else ""

        for w in words:
            w["text"] = clean_word(w["text"])
        words = [w for w in words if w["text"]]

        words = assign_regions(words)

        full_ocr_text = full_txt or " ".join(w["text"] for w in words)

        merchant_r = extract_merchant(words)
        date_r     = extract_date(full_ocr_text)
        gstin_r    = extract_gstin(full_ocr_text)
        invoice_r  = extract_invoice_no(full_ocr_text)
        amounts    = extract_amounts(words, full_ocr_text)
        category   = extract_category(full_ocr_text, merchant_r["value"])

        taxable = amounts["taxable_amount"]["value"]
        gst     = amounts["gst_amount"]["value"]
        total   = amounts["total_amount"]["value"]

        label_fields = {
            "INVOICE_NO"    : invoice_r["raw_token"],
            "INVOICE_DATE"  : date_r["raw_token"],
            "MERCHANT"      : merchant_r["raw_token"],
            "GSTIN"         : gstin_r["raw_token"],
            "TAXABLE_AMOUNT": amounts["taxable_amount"]["raw_token"],
            "GST_AMOUNT"    : amounts["gst_amount"]["raw_token"],
            "TOTAL_AMOUNT"  : amounts["total_amount"]["raw_token"],
        }
        words = assign_bio_labels(words, label_fields)

        gst_valid    = validate_gst(taxable, gst, total)
        score        = audit_score(
            merchant_r["value"], date_r["value"], gstin_r["value"],
            invoice_r["value"], taxable, gst, total
        )
        img_hash_val = image_hash(img_path)
        latency      = round(time.time() - t0, 2)

        result = {
            "image"           : img_path,
            "image_hash"      : img_hash_val,
            "image_size"      : [img_w, img_h],
            "invoice_no"      : invoice_r,
            "merchant"        : merchant_r,
            "invoice_date"    : date_r,
            "gstin"           : gstin_r,
            "taxable_amount"  : amounts["taxable_amount"],
            "gst_amount"      : amounts["gst_amount"],
            "total_amount"    : amounts["total_amount"],
            "expense_category": category,
            "validation"      : {
                "gst_valid"      : gst_valid,
                "duplicate_found": False,
                "audit_score"    : score,
            },
            "processing"      : {"latency_seconds": latency},
            "layout"          : {
                "word_count"   : len(words),
                "regions_found": sorted(set(w["region"] for w in words)),
                "words"        : words,
            },
        }

        Path(json_out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(json_out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return {
            "status"  : "success",
            "file"    : img_path,
            "img_hash": img_hash_val,
            "result"  : result,
        }

    except Exception as e:
        return {
            "status"   : "error",
            "file"     : img_path,
            "error"    : str(e),
            "traceback": traceback.format_exc(),
        }


# ──────────────────────────────────────────────────────────────────
# POST-PROCESSING: DUPLICATE DETECTION
# ──────────────────────────────────────────────────────────────────

def flag_duplicates(all_results: list, json_dir: Path) -> int:
    seen, dup_count = {}, 0
    for r in all_results:
        h = r.get("img_hash")
        if not h:
            continue
        if h in seen:
            r["result"]["validation"]["duplicate_found"] = True
            dup_count += 1
            rel_path = Path(r["file"]).relative_to(Path(CONFIG["image_dir"]))
            jpath    = json_dir / rel_path.with_suffix(".json")
            if jpath.exists():
                with open(jpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["validation"]["duplicate_found"] = True
                with open(jpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            seen[h] = r["file"]
    return dup_count


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

def main():
    pytesseract.pytesseract.tesseract_cmd = CONFIG["tesseract_cmd"]

    image_dir  = Path(CONFIG["image_dir"])
    output_dir = Path(CONFIG["json_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*60)
    print("  Invoice Layout Detection + Field Extraction Pipeline")
    print("="*60)

    print("\n[STEP 1/5] Scanning for images...")
    all_images = [
        p for p in image_dir.rglob("*")
        if p.suffix.lower() in CONFIG["img_extensions"]
    ]
    total = len(all_images)
    print(f"           ✅ Found {total:,} images across all subfolders")

    if total == 0:
        print("[ERROR] No images found. Check image_dir in CONFIG.")
        return

    print("\n[STEP 2/5] Checking existing TXT files...")
    txt_dir     = Path(CONFIG["txt_dir"])
    txt_files   = set(p.stem for p in txt_dir.rglob("*.txt"))
    img_stems   = set(p.stem for p in all_images)
    txt_matched = len(img_stems & txt_files)
    print(f"           ✅ TXT matched : {txt_matched:,} / {total:,} images")
    if txt_matched < total:
        print(f"           ⚠️  Missing TXT : {total - txt_matched:,} (will use TSV text only)")

    print("\n[STEP 3/5] Building task list...")
    tasks, skipped_pre = [], 0
    for img_path in all_images:
        rel      = img_path.relative_to(image_dir)
        json_out = output_dir / rel.with_suffix(".json")
        if CONFIG["skip_existing"] and json_out.exists():
            skipped_pre += 1
            continue
        tasks.append((str(img_path), str(json_out)))

    to_process = len(tasks)
    print(f"           ✅ To process  : {to_process:,}")
    print(f"           ⏭  Pre-skipped : {skipped_pre:,} (already done)")

    if to_process == 0:
        print("\n[INFO] All images already processed. Delete JSONs to rerun.")
        return

    print(f"\n[STEP 4/5] OCR + Layout Detection + Field Extraction")
    print(f"           Workers: {CONFIG['workers']} | Min confidence: {CONFIG['min_confidence']}")

    counts      = {"success": 0, "skipped": 0, "error": 0}
    all_results = []
    error_log   = []

    with ThreadPoolExecutor(max_workers=CONFIG["workers"]) as executor:
        futures = {executor.submit(process_single, t): t for t in tasks}
        with tqdm(
            total=to_process, unit="img", desc="  Processing",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        ) as pbar:
            for future in as_completed(futures):
                res    = future.result()
                status = res.get("status", "error")
                counts[status] = counts.get(status, 0) + 1
                if status == "success":
                    all_results.append(res)
                elif status == "error":
                    error_log.append(res)
                    tqdm.write(f"  [ERR] {Path(res['file']).name}: {res['error']}")
                pbar.set_postfix(ok=counts["success"], skip=counts["skipped"], err=counts["error"])
                pbar.update(1)

    print(f"\n[STEP 5/5] Post-processing...")
    dup_count = flag_duplicates(all_results, output_dir)
    print(f"           ✅ Duplicate detection — {dup_count:,} duplicates flagged")

    if error_log:
        err_path = output_dir / "_error_log.json"
        with open(err_path, "w") as f:
            json.dump(error_log, f, indent=2, default=str)
        print(f"           ⚠️  Error log saved → {err_path}")

    scores    = [r["result"]["validation"]["audit_score"] for r in all_results]
    latencies = [r["result"]["processing"]["latency_seconds"] for r in all_results]
    field_hits = {
        "invoice_no"    : sum(1 for r in all_results if r["result"]["invoice_no"]["value"]),
        "merchant"      : sum(1 for r in all_results if r["result"]["merchant"]["value"]),
        "invoice_date"  : sum(1 for r in all_results if r["result"]["invoice_date"]["value"]),
        "gstin"         : sum(1 for r in all_results if r["result"]["gstin"]["value"]),
        "taxable_amount": sum(1 for r in all_results if r["result"]["taxable_amount"]["value"]),
        "gst_amount"    : sum(1 for r in all_results if r["result"]["gst_amount"]["value"]),
        "total_amount"  : sum(1 for r in all_results if r["result"]["total_amount"]["value"]),
    }

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Total images      : {total:,}")
    print(f"  ✅ Processed      : {counts['success']:,}")
    print(f"  ⏭  Skipped        : {counts['skipped'] + skipped_pre:,}")
    print(f"  ❌ Errors         : {counts['error']:,}")
    print(f"  🔁 Duplicates     : {dup_count:,}")
    if scores:
        print(f"  📊 Avg audit score: {sum(scores)/len(scores):.1f} / 100")
    if latencies:
        print(f"  ⚡ Avg latency    : {sum(latencies)/len(latencies):.2f}s per image")

    print(f"\n  Field extraction hit rate:")
    for field, count in field_hits.items():
        pct = (count / counts["success"] * 100) if counts["success"] else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"    {field:<18}: {bar} {pct:.1f}% ({count:,})")

    label_counts: dict = {}
    for r in all_results:
        for w in r["result"]["layout"]["words"]:
            lbl = w.get("label", "O")
            label_counts[lbl] = label_counts.get(lbl, 0) + 1

    total_tokens = sum(label_counts.values())
    if total_tokens:
        print(f"\n  BIO label distribution ({total_tokens:,} tokens):")
        for lbl in sorted(label_counts):
            pct = label_counts[lbl] / total_tokens * 100
            print(f"    {lbl:<22}: {pct:5.1f}%  ({label_counts[lbl]:,})")

    print(f"\n   Output dir     : {output_dir}")
    print(f"{'='*60}\n")

    if all_results:
        print("[SAMPLE] First result preview:")
        sample = {k: v for k, v in all_results[0]["result"].items()
                  if k not in ("layout", "image_hash", "image_size")}
        print(json.dumps(sample, indent=2, default=str))


if __name__ == "__main__":
    main()
