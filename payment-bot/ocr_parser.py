import re
from dataclasses import dataclass
from io import BytesIO
from typing import List, Optional, Tuple

from PIL import Image
import pytesseract


@dataclass
class ParsedPayment:
    utr: str
    amount: float
    raw_text: str


UTR_LABELS = [
    r"utr",
    r"upi\s*ref(?:erence)?(?:\s*no)?",
    r"upi\s*transaction\s*id",
    r"transaction\s*id",
    r"ref(?:erence)?\s*(?:no|number|id)",
    r"txn\s*id",
    r"payment\s*id",
]

AMOUNT_LABELS = [
    r"amount\s*paid",
    r"paid\s*to",
    r"paid\s*amount",
    r"amount",
    r"total",
    r"payment\s*of",
    r"transferred",
    r"sent",
    r"received",
]


def _normalize_text(text: str) -> str:
    text = text.replace("₹", " Rs ")
    text = text.replace("INR", " Rs ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_amounts(text: str) -> List[float]:
    amounts: List[float] = []
    patterns = [
        r"(?:Rs\.?|INR)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)",
        r"([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)\s*(?:Rs\.?|INR)",
        r"(?:Rs\.?|INR)\s*([0-9]+(?:\.[0-9]{1,2})?)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(1).replace(",", "")
            try:
                amount = float(value)
                if 1 <= amount <= 10_000_000:
                    amounts.append(amount)
            except ValueError:
                continue
    return amounts


def _extract_utrs(text: str) -> List[str]:
    utrs: List[str] = []
    label_pattern = "|".join(UTR_LABELS)
    labeled = re.finditer(
        rf"(?:{label_pattern})\s*[:\-]?\s*([0-9]{{10,20}})",
        text,
        re.IGNORECASE,
    )
    for match in labeled:
        utrs.append(match.group(1))

    standalone = re.finditer(r"\b([0-9]{12})\b", text)
    for match in standalone:
        utrs.append(match.group(1))

    seen = set()
    unique: List[str] = []
    for utr in utrs:
        if utr not in seen:
            seen.add(utr)
            unique.append(utr)
    return unique


def _pick_amount(text: str, amounts: List[float]) -> Optional[float]:
    if not amounts:
        return None

    label_pattern = "|".join(AMOUNT_LABELS)
    labeled = re.finditer(
        rf"(?:{label_pattern})\s*[:\-]?\s*(?:Rs\.?|INR)?\s*([0-9]{{1,3}}(?:,[0-9]{{2,3}})*(?:\.[0-9]{{1,2}})?)",
        text,
        re.IGNORECASE,
    )
    labeled_amounts: List[float] = []
    for match in labeled:
        try:
            labeled_amounts.append(float(match.group(1).replace(",", "")))
        except ValueError:
            continue

    if labeled_amounts:
        return labeled_amounts[0]

    success_match = re.search(
        r"(?:payment\s+successful|paid\s+successfully|transaction\s+successful)",
        text,
        re.IGNORECASE,
    )
    if success_match:
        after = text[success_match.end() :]
        after_amounts = _extract_amounts(after)
        if after_amounts:
            return after_amounts[0]

    return max(amounts)


def _pick_utr(text: str, utrs: List[str]) -> Optional[str]:
    if not utrs:
        return None

    label_pattern = "|".join(UTR_LABELS)
    labeled = re.search(
        rf"(?:{label_pattern})\s*[:\-]?\s*([0-9]{{10,20}})",
        text,
        re.IGNORECASE,
    )
    if labeled:
        return labeled.group(1)

    twelve_digit = [u for u in utrs if len(u) == 12]
    if twelve_digit:
        return twelve_digit[0]

    return utrs[0]


def extract_text_from_image(image_bytes: bytes) -> str:
    image = Image.open(BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    text = pytesseract.image_to_string(image, lang="eng")
    return _normalize_text(text)


def parse_payment_screenshot(image_bytes: bytes) -> Tuple[Optional[ParsedPayment], str]:
    raw_text = extract_text_from_image(image_bytes)
    if not raw_text.strip():
        return None, raw_text

    amounts = _extract_amounts(raw_text)
    utrs = _extract_utrs(raw_text)
    amount = _pick_amount(raw_text, amounts)
    utr = _pick_utr(raw_text, utrs)

    if utr and amount is not None:
        return ParsedPayment(utr=utr, amount=amount, raw_text=raw_text), raw_text

    return None, raw_text
