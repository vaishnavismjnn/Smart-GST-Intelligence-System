import pytesseract
from PIL import Image
import re
import os

from model import load_model, load_processor

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


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
# GSTIN
# ─────────────────────────────────────────
def extract_gstin(line_text):
    f = flat(line_text)

    standard = re.findall(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b', f, re.IGNORECASE)
    if standard:
        return standard[0].upper()

    relaxed = re.findall(r'\b\d{2}[A-Z0-9]{13}\b', f, re.IGNORECASE)
    for c in relaxed:
        if re.search(r'[A-Z]', c, re.IGNORECASE) and re.search(r'\d', c):
            return c.upper()

    return None


# ─────────────────────────────────────────
# INVOICE NUMBER
# ─────────────────────────────────────────
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
        r'(?:Invoice\s*No\.?|Inv\s*No\.?|Invoice\s*Number)'
        r'\s*[:\-\.\s]\s*(\d{3,6})',
        f, re.IGNORECASE
    )
    if m:
        return m.group(1)

    return None


# ─────────────────────────────────────────
# DATE
# ─────────────────────────────────────────
def extract_date(f):
    m = re.search(
        r'(?:Invoice\s*Date|Bill\s*Date|Date\s*:)[^\d]{0,5}(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        f, re.IGNORECASE
    )
    if m:
        return m.group(1)

    for d in re.findall(r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b', f):
        parts = re.split(r'[\/\-]', d)
        if len(parts) == 3 and 1 <= int(parts[1]) <= 12 and 1 <= int(parts[0]) <= 31:
            return d
    return None


# ─────────────────────────────────────────
# MERCHANT
# ─────────────────────────────────────────
def extract_merchant(line_text, words):
    noise_triggers  = {"tax", "invoice", "receipt", "bill", "gstin", "gst",
                       "date", "no", "number", "total", "amount"}
    person_labels   = {"name", "phone", "email", "contact", "mob", "mobile"}
    leading_fillers = {"for", "by", "from", "to", "dear"}
    biz_kw          = {"pvt", "ltd", "limited", "private", "solutions", "stores",
                       "trading", "industries", "enterprises", "services",
                       "hardware", "media", "parts", "auto", "fashion",
                       "house", "medical", "cloudprint"}

    lines = [l.strip().lstrip("'\"`\u2018\u2019") for l in line_text.split('\n') if l.strip()]

    def clean_line(line):
        noise_triggers_local = {"tax", "invoice", "receipt", "bill", "gstin", "gst",
                                 "date", "no", "number", "total", "amount", "services"}
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
        if not tokens:
            return None

        clean = []
        for i, t in enumerate(tokens):
            if t == '&':
                next_t = tokens[i+1].lower() if i + 1 < len(tokens) else ''
                if next_t in noise_triggers_local or next_t in {'group', 'associates', 'co'}:
                    break
                clean.append(t)
                continue
            if t.lower().rstrip('.:,&') in noise_triggers_local:
                break
            if re.search(r'\d', t):
                break
            clean.append(t)
        name = " ".join(clean[:6]).rstrip('& ').strip()
        return name if name else None

    for line in lines[:20]:
        if any(ch.isdigit() for ch in line):
            continue
        result = clean_line(line)
        if result and len(result) > 3:
            return result

    for line in lines[:20]:
        low_set = {t.lower().strip('.:,&—–-') for t in line.split()}
        if not (low_set & biz_kw):
            continue
        gstin_idx = re.search(r'\bGSTIN\b', line, re.IGNORECASE)
        trimmed = line[:gstin_idx.start()].strip() if gstin_idx else line
        result = clean_line(trimmed)
        if result and len(result) > 3:
            return result

    noise = {"invoice","proforma","tax","bill","date","due","gst","gstin",
             "total","amount","cgst","sgst","igst","no","number","ref",
             "order","challan","transport","phone","email","name","original",
             "customer","detail","address","shop","sales","for","the","and"}
    clean = []
    for w in words[:25]:
        if not re.match(r'^[A-Za-z]+$', w): continue
        if len(w) <= 2 or w.lower() in noise: continue
        if len(set(w.lower())) < 3: continue
        if w not in clean:
            clean.append(w)
    return " ".join(clean[:3]) if clean else None


# ─────────────────────────────────────────
# TOTAL AMOUNT
# ─────────────────────────────────────────
def extract_total(f):
    patterns = [
        r'Total\s*Amount\s*After\s*Tax[^\d]{0,15}([\d,]+\.\d{2})',
        r'NET\s*PAYABLE[^\d]{0,15}([\d,]+\.\d{2})',
        r'Balance\s*Due[^\d]{0,15}([\d,]+\.\d{2})',
        r'Gross\s*Total[^\d]{0,10}([\d,]+\.\d{2})',
        r'Grand\s*Total[^\d]{0,10}([\d,]+\.\d{2})',
        r'Total\s*[Aa]mount(?!\s*\(in\s*words\))(?!\s*After)(?!\s*\(GST\))[^\d]{0,10}([\d,]+\.\d{2})',
        r'\bTOTAL\b[^\d]{0,5}([\d,]+\.\d{2})',
    ]
    for pat in patterns:
        matches = re.findall(pat, f, re.IGNORECASE)
        if matches:
            return float(matches[-1].replace(",", ""))
    return None


# ─────────────────────────────────────────
# TAXABLE AMOUNT
# ─────────────────────────────────────────
def extract_taxable(f):
    patterns = [
        r'Taxable\s*Amount[^\d]{0,10}([\d,]+\.\d{2})',
        r'Sub\s*Total[^\d]{0,10}(?:Rs\.?)?\s*([\d,]+\.\d{2})',
        r'Total\s*Amount[^\d]{0,10}([\d,]+\.\d{2})(?=.{0,300}Taxes\s*\(GST\))',
    ]
    for pat in patterns:
        m = re.search(pat, f, re.IGNORECASE | re.DOTALL)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


# ─────────────────────────────────────────
# GST AMOUNT
# ─────────────────────────────────────────
def extract_gst(f):
    total_gst = 0.0
    found = False

    igst_vals = re.findall(
        r'\bIGST\b\s*(?:@\s*\d+%?|[\(\d%\)]+)?\s*[:\s]+(?:Rs\.?)?\s*([\d,]+\.\d{2})',
        f, re.IGNORECASE
    )
    if igst_vals:
        total_gst += max(float(v.replace(",", "")) for v in igst_vals)
        found = True

    cgst = re.findall(r'(?:Add\s*[:\-]?\s*)?CGST\b[^\d%]{0,10}([\d,]+\.\d{2})', f, re.IGNORECASE)
    sgst = re.findall(r'(?:Add\s*[:\-]?\s*)?SGST\b[^\d%]{0,10}([\d,]+\.\d{2})', f, re.IGNORECASE)
    if cgst and sgst and not found:
        total_gst += float(cgst[-1].replace(",", "")) + float(sgst[-1].replace(",", ""))
        found = True

    if not found:
        tl = re.findall(
            r'(?:Total\s*Tax|Taxes\s*\(GST\)|Tax\s*Amount)[^\d]{0,10}([\d,]+\.\d{2})',
            f, re.IGNORECASE
        )
        if tl:
            total_gst = float(tl[-1].replace(",", ""))
            found = True

    return round(total_gst, 2) if found else None


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def extract_invoice(image_path):
    image     = Image.open(image_path).convert("RGB")
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


# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────
if __name__ == "__main__":
    image_paths = [
        r"F:\newdataset\images\extra_017_fmt9.png",
        r"F:\newdataset\images\synth_001_fmt1.png",
        r"F:\newdataset\images\synth_015_fmt2.png",
        r"F:\newdataset\images\synth_021_fmt3.png",
        r"F:\newdataset\images\invoice_16.png",
    ]

    fields = [
        ("GSTIN",          "  GSTIN"),
        ("INVOICE_NO",     " Invoice No"),
        ("INVOICE_DATE",   " Invoice Date"),
        ("MERCHANT",       " Merchant"),
        ("TOTAL_AMOUNT",   " Total Amount"),
        ("TAXABLE_AMOUNT", " Taxable Amount"),
        ("GST_AMOUNT",     " Total GST"),
    ]

    for path in image_paths:
        fname = os.path.basename(path)
        if not os.path.exists(path):
            print(f"\n  File not found: {path}")
            continue

        print(f"\n{'='*50}")
        print(f" FILE: {fname}")
        print('='*50)

        result = extract_invoice(path)

        for key, label in fields:
            val = result.get(key, " NOT FOUND")
            print(f"  {label:<22}: {val}")
