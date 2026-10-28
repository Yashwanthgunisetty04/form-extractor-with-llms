import re
from datetime import date

ILLEGIBLE = "ILLEGIBLE"
LOW_CONFIDENCE = 70

NUMERIC_TYPES = ("date", "phone", "zip")
# letters handwriting OCR often returns for digits
DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"})
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")


def normalize(value, field):
    # cleaned value used for comparing and for the output; "" / [] means blank
    ftype = field["type"]
    if value is None:
        return [] if ftype == "multi_choice" else ""
    if isinstance(value, list):
        return sorted(v.strip() for v in value)
    value = " ".join(value.split())
    if ftype in ("choice", "multi_choice"):
        return match_options(value, field)
    if ftype in NUMERIC_TYPES:
        # only in words that already hold a digit, so "Month" stays "Month"
        value = " ".join(w.translate(DIGIT_FIXES) if re.search(r"\d", w) else w
                         for w in value.split())
    if ftype == "date":
        return normalize_date(value)
    if ftype in ("phone", "zip"):
        digits = re.sub(r"\D", "", value)
        if ftype == "phone" and len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        return digits
    if ftype == "email":
        return value.replace(" ", "").lower()
    return value


def match_options(text, field):
    # Textract answers a checkbox query with label text, e.g. "Adverse Event, Product Problem";
    # map it onto the field's options, or keep the text if any part matches none
    options = {o.casefold(): o for o in field["options"]}
    parts = [p.strip() for p in re.split(r"[,;\n]|\band\b", text) if p.strip()]
    matched = [options.get(p.casefold()) for p in parts]
    if not parts or None in matched:
        return text
    if field["type"] == "multi_choice":
        return sorted(set(matched))
    return matched[0] if len(matched) == 1 else text


def normalize_date(value):
    # the form prints dates as mm/dd/yyyy; returns YYYY-MM-DD, or the input if it can't be read
    parts = re.findall(r"\d+", value)
    if len(parts) != 3:
        return value
    m, d, y = (int(p) for p in parts)
    if y < 100:
        y += 2000
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return value


def key(value):
    # comparison key: case-insensitive text, order-free lists
    if isinstance(value, list):
        return [v.casefold() for v in value]
    return value.casefold()


def is_valid(value, field):
    if value in ("", []):
        return True
    ftype = field["type"]
    if ftype == "date":
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
    if ftype == "phone":
        return len(value) == 10
    if ftype == "zip":
        return len(value) in (5, 9)
    if ftype == "email":
        return bool(EMAIL_RE.match(value))
    if ftype == "choice":
        return value in field["options"]
    if ftype == "multi_choice":
        return all(v in field["options"] for v in value)
    return True


def compare_field(field, llm, textract):
    llm_value = normalize(llm["raw_value"], field)
    reasons = []
    if llm["illegible"]:
        reasons.append("illegible")
    else:
        if key(llm_value) != key(normalize(textract["raw_value"], field)):
            reasons.append("engines disagree")
        conf = textract["confidence"]
        if conf is not None and conf < LOW_CONFIDENCE:
            reasons.append(f"low confidence (<{LOW_CONFIDENCE})")
        if not is_valid(llm_value, field):
            reasons.append("failed validation")
    return {
        "field": field["name"],
        "llm": llm["raw_value"],
        "textract": textract["raw_value"],
        "textract_confidence": textract["confidence"],
        "value": None if reasons else llm_value,
        "status": "review" if reasons else "accepted",
        "reason": "; ".join(reasons) or None,
    }


def compare(llm_readings, textract_readings, fields):
    llm = {r["field"]: r for r in llm_readings}
    textract = {r["field"]: r for r in textract_readings}
    no_answer = {"raw_value": None, "confidence": None}
    return [compare_field(f, llm[f["name"]], textract.get(f["name"], no_answer))
            for f in fields]
