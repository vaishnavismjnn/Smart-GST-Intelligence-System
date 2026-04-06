import re

def validate_gst(gst):
    if not gst:
        return False
    pattern = r'\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]'
    return bool(re.match(pattern, gst))


def validate_amounts(total, taxable, gst):
    if total and taxable and gst:
        return abs((taxable + gst) - total) < 2
    return True