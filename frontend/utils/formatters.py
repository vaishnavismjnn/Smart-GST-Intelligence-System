# --- file: utils/formatters.py ---

def fmt_inr(amount) -> str:
    """Format as Indian Rupee: ₹ 1,23,456.78"""
    if amount is None:
        return "—"
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return "—"
    is_negative = amount < 0
    amount = abs(amount)
    integer_part = int(amount)
    decimal_part = f"{amount:.2f}".split(".")[1]
    s = str(integer_part)
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted = ",".join(groups) + "," + last3
    else:
        formatted = s
    result = f"₹ {formatted}.{decimal_part}"
    return f"-{result}" if is_negative else result

def fmt_date(date_str) -> str:
    return str(date_str) if date_str else "—"

def fmt_bool_badge(value: bool, true_label="Valid", false_label="Invalid") -> str:
    css = "badge-valid" if value else "badge-invalid"
    label = true_label if value else false_label
    return f'<span class="{css}">{label}</span>'

def fmt_gstin(gstin) -> str:
    return gstin if gstin else "—"

def short_id(record_id: str) -> str:
    return f"#{record_id[-6:].upper()}" if record_id else "—"