import re
from typing import Optional, Tuple


MANUAL_PATTERN = re.compile(
    r"^\s*(\d{10,20})\s+([\d,]+(?:\.\d{1,2})?)\s*$"
)


def parse_manual_entry(text: str) -> Optional[Tuple[str, float]]:
    match = MANUAL_PATTERN.match(text.strip())
    if not match:
        return None

    utr = match.group(1)
    amount_str = match.group(2).replace(",", "")
    try:
        amount = float(amount_str)
    except ValueError:
        return None

    if amount <= 0:
        return None

    return utr, amount


def parse_amount(text: str) -> Optional[float]:
    cleaned = text.strip().replace("₹", "").replace("Rs", "").replace("rs", "")
    cleaned = cleaned.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        amount = float(cleaned)
    except ValueError:
        return None
    if amount <= 0:
        return None
    return amount


def is_valid_utr(text: str) -> bool:
    return bool(re.fullmatch(r"\d{10,20}", text.strip()))
