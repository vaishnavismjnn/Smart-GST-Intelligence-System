import requests
from PIL import Image
from io import BytesIO
import pytesseract
import re
import os

if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# ─────────────────────────────────────────
# OCR  –  TWO MODES
# ─────────────────────────────────────────
def ocr_lines(image):
    """Full text preserving line order (used for ALL regex matching)."""
    return pytesseract.image_to_string(image, config="--psm 6")


def ocr_words(image):
    """Raw word list (used only for merchant fallback scan)."""
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    return [w.strip() for w in data["text"] if w.strip()]


def flat(text):
    """Collapse newlines/tabs to single spaces — keeps label+value on one string."""
    return " ".join(text.split())

# ─────────────────────────────────────────
# NORMALIZE
# ─────────────────────────────────────────
def normalize_amounts(text):
    text = re.sub(r'[₹$€£]', '', text)
    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    return text

# ─────────────────────────────────────────
# EXTRACTION FUNCTIONS
# ─────────────────────────────────────────

def extract_gstin(line_text):
    f = " ".join(line_text.split())
    standard = re.findall(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b', f, re.IGNORECASE)
    if standard:
        return standard[0].upper()
    f_clean = f
    f_clean = re.sub(r'(?<=[A-Z]{5})O', '0', f_clean)
    f_clean = re.sub(r'(?<=\d{2}[A-Z]{4})I', '1', f_clean)
    standard2 = re.findall(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b', f_clean, re.IGNORECASE)
    if standard2:
        return standard2[0].upper()
    relaxed = re.findall(r'\b[0-9]{2}[A-Z0-9]{10}[0-9][A-Z0-9]{2}\b', f, re.IGNORECASE)
    for c in relaxed:
        if re.search(r'[A-Z]', c, re.IGNORECASE) and re.search(r'\d', c):
            return c.upper()
    m = re.search(r'GSTIN[^\w]{0,10}([A-Z0-9]{15})', f, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def extract_invoice_number(f):
    m = re.search(r'\b(?:INV|AAP|[A-Z]{2,5})[\/\-]\d{4}[-\/]\d{2,4}[\/\-]\d+', f, re.IGNORECASE)
    if m:
        return m.group()
    m = re.search(r'Bill\s*#\s*(\d{4,5})', f, re.IGNORECASE)
    if m:
        val = m.group(1)
        if len(val) == 5:
            val = val[1:]
        return val
    m = re.search(
        r'(?:Invoice\s*No\.?|Inv\s*No\.?|Invoice\s*Number)\s*[:\-\.\s]\s*([A-Z0-9\/\-]{3,20})',
        f, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    return None


def extract_date(f):
    MONTHS = (
        r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    )
    m = re.search(
        r'(?:Invoice\s*Date|Bill\s*Date|Date\s*of\s*Issue|Date)[^\d]{0,10}'
        r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        f, re.IGNORECASE
    )
    if m:
        return m.group(1)
    m = re.search(
        r'(?:Invoice\s*Date|Bill\s*Date|Date\s*of\s*Issue|Date)\s*[:\-\.]*\s*'
        r'(?:'
            r'(\d{1,2}[\s\-\/]' + MONTHS + r'[\s\-\/,]*\d{2,4})'
            r'|'
            r'(' + MONTHS + r'[\s\-\/,]*\d{1,2}[\s\-\/,]*\d{2,4})'
        r')',
        f, re.IGNORECASE
    )
    if m:
        return (m.group(1) or m.group(2)).strip()
    m = re.search(
        r'\b(?:'
            r'(\d{1,2}[\s\-\/]' + MONTHS + r'[\s\-\/,]*\d{2,4})'
            r'|'
            r'(' + MONTHS + r'[\s\-\/,]*\d{1,2}[\s\-\/,]*\d{2,4})'
        r')\b',
        f, re.IGNORECASE
    )
    if m:
        return (m.group(1) or m.group(2)).strip()
    for d in re.findall(r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b', f):
        parts = re.split(r'[\/\-\.]', d)
        try:
            if len(parts) == 3 and 1 <= int(parts[1]) <= 12 and 1 <= int(parts[0]) <= 31:
                return d
        except ValueError:
            continue
    return None


ADDRESS_NOISE = {
    "okhla", "industrial", "area", "phase", "sector", "street", "road",
    "nagar", "colony", "delhi", "mumbai", "bangalore", "bengaluru", "hyderabad",
    "chennai", "kolkata", "pune", "pin", "state", "city", "village",
    "district", "taluk", "near", "opposite", "behind", "floor", "building",
    "plot", "block", "flat", "shop", "office", "warehouse", "godown"
}

def extract_merchant(line_text, words):
    noise_triggers  = {"tax","invoice","receipt","bill","gstin","gst","date","no","number",
                       "total","amount","original","duplicate","triplicate"}
    person_labels   = {"name","phone","email","contact","mob","mobile"}
    leading_fillers = {"for","by","from","to","dear"}
    biz_kw          = {"pvt","ltd","limited","private","solutions","stores","trading",
                       "industries","enterprises","services","hardware","media","parts",
                       "auto","fashion","house","medical","cloudprint","agency","co",
                       "corporation","group","associates","works","suppliers","distributors"}

    lines = [l.strip().lstrip("'\"`") for l in line_text.split('\n') if l.strip()]

    def is_address_line(line):
        tokens = {t.lower().strip('.:,&—–-') for t in line.split()}
        return bool(tokens & ADDRESS_NOISE)

    def clean_line(line):
        tokens = line.split()
        if not tokens:
            return None
        while tokens and tokens[0].lower().rstrip('.:,') in leading_fillers:
            tokens = tokens[1:]
        if not tokens:
            return None
        result = []
        for t in tokens:
            if t.lower().rstrip('.:,') in person_labels:
                break
            result.append(t)
        tokens = result
        clean = []
        for i, t in enumerate(tokens):
            if t == '&':
                next_t = tokens[i+1].lower() if i+1 < len(tokens) else ''
                if next_t in noise_triggers or next_t in {'group','associates','co'}:
                    break
                clean.append(t)
                continue
            if t.lower().rstrip('.:,&') in noise_triggers:
                break
            if re.search(r'\d', t):
                break
            clean.append(t)
        name = " ".join(clean[:6]).rstrip('& ').strip()
        return name if name else None

    for line in lines[:20]:
        if any(ch.isdigit() for ch in line):
            continue
        if is_address_line(line):
            continue
        result = clean_line(line)
        if result and len(result) > 3:
            return result

    for line in lines[:20]:
        low_set = {t.lower().strip('.:,&—–-') for t in line.split()}
        if not (low_set & biz_kw):
            continue
        if is_address_line(line):
            continue
        gstin_idx = re.search(r'\bGSTIN\b', line, re.IGNORECASE)
        trimmed = line[:gstin_idx.start()].strip() if gstin_idx else line
        result = clean_line(trimmed)
        if result and len(result) > 3:
            return result

    noise = {"invoice","proforma","tax","bill","date","due","gst","gstin","total","amount",
             "cgst","sgst","igst","no","number","ref","order","challan","transport",
             "phone","email","name","original","customer","detail","address","shop",
             "sales","for","the","and"}
    clean = []
    for w in words[:25]:
        if not re.match(r'^[A-Za-z]+$', w):
            continue
        if len(w) <= 2 or w.lower() in noise:
            continue
        if w.lower() in ADDRESS_NOISE:
            continue
        if len(set(w.lower())) < 3:
            continue
        if w not in clean:
            clean.append(w)
    return " ".join(clean[:3]) if clean else None


def extract_total(f):
    patterns = [
        r'Total\s*Amount\s*After\s*Tax[^\d]{0,15}([\d,]+\.\d{2})',
        r'NET\s*PAYABLE[^\d]{0,15}([\d,]+\.\d{2})',
        r'Balance\s*Due[^\d]{0,15}([\d,]+\.\d{2})',
        r'Gross\s*Total[^\d]{0,10}([\d,]+\.\d{2})',
        r'Grand\s*Total[^\d]{0,10}([\d,]+\.\d{2})',
        r'Invoice\s*Total[^\d]{0,10}([\d,]+\.\d{2})',
        r'Amount\s*Payable[^\d]{0,10}([\d,]+\.\d{2})',
        r'Total\s*[Aa]mount(?!\s*\(in\s*words\))(?!\s*After)(?!\s*\(GST\))[^\d]{0,10}([\d,]+\.\d{2})',
        r'\bTOTAL\b[^\d]{0,5}([\d,]+\.\d{2})',
        r'Grand\s*Total[^\d]{0,10}([\d,]+)',
        r'\bTOTAL\b[^\d]{0,5}([\d,]+)',
    ]
    for pat in patterns:
        matches = re.findall(pat, f, re.IGNORECASE)
        if matches:
            return float(matches[-1].replace(",", ""))
    return None


def extract_taxable(f):
    patterns = [
        r'Taxable\s*(?:Value|Amount)[^\d]{0,10}([\d,]+\.\d{2})',
        r'Sub\s*[Tt]otal[^\d]{0,10}(?:Rs\.?)?\s*([\d,]+\.\d{2})',
        r'Total\s*Amount[^\d]{0,10}([\d,]+\.\d{2})(?=.{0,300}Taxes\s*\(GST\))',
        r'Basic\s*Amount[^\d]{0,10}([\d,]+\.\d{2})',
    ]
    for pat in patterns:
        m = re.search(pat, f, re.IGNORECASE | re.DOTALL)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def extract_gst(f):
    total_gst = 0.0
    found = False
    igst_vals = re.findall(
        r'\bIGST\b\s*(?:@\s*[\d\.]+%?)?\s*[:\s]+(?:Rs\.?)?\s*([\d,]+\.\d{2})',
        f, re.IGNORECASE
    )
    if igst_vals:
        total_gst += max(float(v.replace(",", "")) for v in igst_vals)
        found = True
    cgst = re.findall(r'(?:Add\s*[:\-]?\s*)?CGST\b[^\d%]{0,10}([\d,]+\.\d{2})', f, re.IGNORECASE)
    sgst = re.findall(r'(?:Add\s*[:\-]?\s*)?(?:SGST|UTGST)\b[^\d%]{0,10}([\d,]+\.\d{2})', f, re.IGNORECASE)
    if cgst and sgst and not found:
        total_gst += float(cgst[-1].replace(",", "")) + float(sgst[-1].replace(",", ""))
        found = True
    if not found:
        tl = re.findall(
            r'(?:Total\s*Tax|Taxes\s*\(GST\)|Tax\s*Amount|Total\s*GST)[^\d]{0,10}([\d,]+\.\d{2})',
            f, re.IGNORECASE
        )
        if tl:
            total_gst = float(tl[-1].replace(",", ""))
            found = True
    return round(total_gst, 2) if found else None


# ─────────────────────────────────────────
# CORE FUNCTION: works for both URL & file
# ─────────────────────────────────────────
def extract_invoice(source):
    """
    Accept either:
      - a local file path  (str ending in image extension, or os.path.exists)
      - a URL              (str starting with http/https)
    Returns a dict with extracted fields.
    """
    # ── Load image ──
    if str(source).lower().startswith("http"):
        print(f"📥 Downloading: {source}")
        response = requests.get(source, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code} — could not download: {source}")
            return {}
        content_type = response.headers.get("Content-Type", "")
        if "image" not in content_type:
            print(f"❌ Not an image. Content-Type: {content_type}")
            return {}
        try:
            img = Image.open(BytesIO(response.content)).convert("RGB")
            print("✅ Image loaded successfully")
        except Exception as e:
            print(f"❌ PIL could not open image: {e}")
            return {}
    else:
        if not os.path.exists(source):
            print(f"❌ File not found: {source}")
            return {}
        try:
            img = Image.open(source).convert("RGB")
            print(f"✅ Image loaded: {os.path.basename(source)}")
        except Exception as e:
            print(f"❌ PIL could not open image: {e}")
            return {}

    # ── OCR ──
    line_text = pytesseract.image_to_string(img, config="--psm 6")
    data      = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words     = [w.strip() for w in data["text"] if w.strip()]

    print("\n===== RAW OCR OUTPUT =====")
    print(line_text[:3000])
    print("==========================\n")

    f = normalize_amounts(" ".join(line_text.split()))

    # ── Extract ──
    gstin    = extract_gstin(line_text)
    inv      = extract_invoice_number(f)
    date     = extract_date(f)
    merchant = extract_merchant(line_text, words)
    total    = extract_total(f)
    taxable  = extract_taxable(f)
    gst      = extract_gst(f)

    if total is not None and taxable is not None and taxable >= total:
        taxable = None

    result = {}
    if gstin    is not None: result["GSTIN"]          = gstin
    if inv      is not None: result["INVOICE_NO"]     = inv
    if date     is not None: result["INVOICE_DATE"]   = date
    if merchant is not None: result["MERCHANT"]       = merchant
    if total    is not None: result["TOTAL_AMOUNT"]   = total
    if taxable  is not None: result["TAXABLE_AMOUNT"] = taxable
    if gst is not None:
        result["GST_AMOUNT"] = gst
    elif total is not None and taxable is not None:
        result["GST_AMOUNT"] = round(total - taxable, 2)

    return result


# ─────────────────────────────────────────
# DISPLAY HELPER
# ─────────────────────────────────────────
FIELDS = [
    ("GSTIN",          "GSTIN"),
    ("INVOICE_NO",     "Invoice No"),
    ("INVOICE_DATE",   "Invoice Date"),
    ("MERCHANT",       "Merchant"),
    ("TOTAL_AMOUNT",   "Total Amount"),
    ("TAXABLE_AMOUNT", "Taxable Amount"),
    ("GST_AMOUNT",     "Total GST"),
]

def print_result(label, result):
    print(f"\n{'='*50}")
    print(f"  SOURCE: {label}")
    print('='*50)
    for key, display in FIELDS:
        val = result.get(key, "NOT FOUND")
        print(f"  {display:<22}: {val}")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":

    # ── Single URL mode ──
    url = "https://www.mybillplease.com/_next/image?url=%2Fimages%2Ftemplates%2Fprofessional.webp&w=3840&q=75"
    result = extract_invoice(url)
    print_result(url[-40:], result)

    # ── Batch local files mode ──
    image_paths = [
        r"F:\newdataset\images\extra_017_fmt9.png",
        r"F:\newdataset\images\synth_001_fmt1.png",
        r"F:\newdataset\images\synth_015_fmt2.png",
        r"F:\newdataset\images\synth_021_fmt3.png",
        r"F:\newdataset\images\invoice_16.png",
    ]

    for path in image_paths:
        result = extract_invoice(path)
        print_result(os.path.basename(path), result)
# ─────────────────────────────────────────
# BACKEND API ENTRY POINT
# ─────────────────────────────────────────
def extract_invoice_from_image(image):
    """
    Called by FastAPI /process endpoint.
    Accepts a PIL Image object directly (no file path needed).
    """
    line_text = ocr_lines(image)
    words     = ocr_words(image)
    f         = flat(line_text)

    result = {}

    gstin = extract_gstin(line_text)
    if gstin:
        result["GSTIN"] = gstin

    inv = extract_invoice_number(f)
    if inv:
        result["INVOICE_NO"] = inv

    date = extract_date(f)
    if date:
        result["INVOICE_DATE"] = date

    merchant = extract_merchant(line_text, words)
    if merchant:
        result["MERCHANT"] = merchant

    total   = extract_total(f)
    taxable = extract_taxable(f)
    gst     = extract_gst(f)

    if total is not None and taxable is not None and taxable >= total:
        taxable = None

    if total   is not None: result["TOTAL_AMOUNT"]   = total
    if taxable is not None: result["TAXABLE_AMOUNT"]  = taxable
    if gst is not None:
        result["GST_AMOUNT"] = gst
    elif total is not None and taxable is not None:
        result["GST_AMOUNT"] = round(total - taxable, 2)

    return result
