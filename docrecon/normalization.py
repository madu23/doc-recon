from __future__ import annotations
import re
import unicodedata
from rapidfuzz import fuzz

ADDRESS_EQUIVALENTS = {
    "road": "rd", "street": "st", "avenue": "ave", "close": "cl",
    "junction": "jct", "estate": "est", "building": "bldg",
    "number": "no", "state": "", "nigeria": ""
}

def text_basic(value) -> str:
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value))
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def normalize_reference(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

def normalize_phone(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return ""
    if digits.startswith("234") and len(digits) >= 13:
        return digits
    if digits.startswith("0") and len(digits) == 11:
        return "234" + digits[1:]
    if len(digits) == 10 and digits.startswith(("7", "8", "9")):
        return "234" + digits
    return digits

def normalize_name(value) -> str:
    return text_basic(value)

def name_similarity(expected: str, actual: str) -> float:
    e, a = normalize_name(expected), normalize_name(actual)
    if not e or not a:
        return 0.0
    # token_set_ratio naturally handles swapped/misarranged names.
    return float(max(fuzz.ratio(e, a), fuzz.token_sort_ratio(e, a), fuzz.token_set_ratio(e, a)))

def normalize_address(value) -> str:
    tokens = text_basic(value).split()
    out = []
    for token in tokens:
        replacement = ADDRESS_EQUIVALENTS.get(token, token)
        if replacement:
            out.append(replacement)
    return " ".join(out)

def address_similarity(expected: str, actual: str) -> float:
    e, a = normalize_address(expected), normalize_address(actual)
    if not e or not a:
        return 0.0
    return float(max(fuzz.token_set_ratio(e, a), fuzz.token_sort_ratio(e, a), fuzz.partial_ratio(e, a)))
