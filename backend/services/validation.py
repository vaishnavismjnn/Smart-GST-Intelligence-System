import re

def validate_gst(gst):
    """
    Validate a 15-character Indian GSTIN.
    Uses a strict full-string match (^ and $) to reject wrong-length strings.
    Also fixes common OCR misreads in the state-code digits (O -> 0).
    """
    if not gst:
        return False
    # Fix common OCR substitution in the first 2 digit positions
    cleaned = gst.upper()
    cleaned = re.sub(r'O', '0', cleaned[:2]) + cleaned[2:]
    # Strict 15-char pattern with anchors
    pattern = r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]$'
    return bool(re.match(pattern, cleaned))


def validate_amounts(total, taxable, gst):
    """
    Check that taxable + gst ~ total.
    """
    if total is not None and taxable is not None and gst is not None:
        return abs((taxable + gst) - total) < 10
    return True
