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
    r"upi\s*transaction\s*id",
    r"transaction\s*id",
    r"upi\s*ref(?:erence)?(?:\s*no)?",
    r"ref(?:erence)?\.?\s*no",
    r"ref(?:erence)?\s*(?:no|number|id)",
    r"txn\s*id",
    r"payment\s*id",
]

AMOUNT_LABELS = [
    r"amount\s*paid",
    r"paid\s*amount",
    r"amount",
    r"total",
    r"debited",
    r"credited",
    r"sent",
    r"received",
]

MAX_AMOUNT = 100_000
MIN_AMOUNT = 50


def _normalize_text(text: str) -> str:
    text = text.replace("₹", " Rs ")
    text = text.replace("INR", " Rs ")
    text = re.sub(r"[%&™~®=]", " Rs ", text)
    text = text.replace("z", "5").replace("Z", "5")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_amount(value: str) -> Optional[float]:
    cleaned = value.replace(",", "").replace(" ", "").strip()
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    if not cleaned:
        return None
    # Fix OCR like 725000 -> 2500, 325000 -> 2500
    if len(cleaned) == 6 and cleaned.endswith("000") and cleaned[0] in "237":
        cleaned = cleaned[1:]
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", cleaned):
        return None
    try:
        amount = float(cleaned)
    except ValueError:
        return None
    if MIN_AMOUNT <= amount <= MAX_AMOUNT:
        return amount
    # GPay sometimes OCRs 900 as 7900/79000
    if amount > MAX_AMOUNT:
        for trim in (1, 2):
            fixed = _clean_amount(cleaned[trim:])
            if fixed is not None:
                return fixed
    return None


def _fix_rupee_ocr_amount(amount: float) -> float:
    # OCR often prepends '7' from rupee symbol: 71,700 -> 1,700
    if amount > MAX_AMOUNT and "," in f"{amount:,.0f}":
        fixed = _clean_amount(str(int(amount))[1:])
        if fixed is not None:
            return fixed
    text = f"{int(amount)}"
    if len(text) >= 5 and text.startswith("7"):
        fixed = _clean_amount(text[1:])
        if fixed is not None:
            return fixed
    return amount


def _extract_amounts(text: str) -> List[float]:
    amounts: List[float] = []
    patterns = [
        r"(?:Rs\.?|INR)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)",
        r"([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)\s*(?:Rs\.?|INR)",
        r"(?:payment\s+successful!?|paid\s+successfully|transaction\s+successful)\s+[^0-9]{0,40}([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{2,6})",
        r"(?:payment\s+success)\s+[^0-9]{0,40}([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{2,6})",
        r"amount\s+Rs\s+([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{2,6})",
        r"(?:debited|credited)\s+[^0-9]{0,20}([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{2,6})",
        r"(?:amount|paid|sent)\s*[:\s]*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{2,6})",
        r"\b([0-9]{1,3}(?:,[0-9]{2,3})+)\b",
        r"\bRs\s+([0-9]{2,6})\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            amount = _clean_amount(match.group(1))
            if amount is not None:
                amounts.append(_fix_rupee_ocr_amount(amount))

    # Standalone 2-5 digit amounts near @ upi lines: "axis 1,700 @"
    for match in re.finditer(
        r"\b([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{3,6})\s*@\s*\d",
        text,
        re.IGNORECASE,
    ):
        amount = _clean_amount(match.group(1))
        if amount is not None:
            amounts.append(_fix_rupee_ocr_amount(amount))

    return amounts


def _is_upi_id_number(value: str) -> bool:
    if len(value) == 10 and value[0] in "6789":
        return True
    if "@" in value:
        return True
    if re.search(r"gpay-\d+@|@okbizaxis|@okaxis|@fbpe", value, re.IGNORECASE):
        return True
    return False


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

    ref_no = re.finditer(
        r"ref\.?\s*no\.?\s*[:\-]?\s*([0-9]{10,20})",
        text,
        re.IGNORECASE,
    )
    for match in ref_no:
        utrs.append(match.group(1))

    # GPay footer UTR often at end before Copy/Help
    footer = re.search(
        r"([0-9]{12})\s*(?:copy|get help|repeat|share|view history)",
        text,
        re.IGNORECASE,
    )
    if footer:
        utrs.append(footer.group(1))

    standalone = re.finditer(r"\b(0[0-9]{11}|[2-6][0-9]{11})\b", text)
    for match in standalone:
        utrs.append(match.group(1))

    seen = set()
    unique: List[str] = []
    for utr in utrs:
        if utr not in seen and not _is_upi_id_number(utr):
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
        amount = _clean_amount(match.group(1))
        if amount is not None:
            labeled_amounts.append(_fix_rupee_ocr_amount(amount))

    if labeled_amounts:
        return labeled_amounts[0]

    success_match = re.search(
        r"(?:payment\s+successful!?|paid\s+successfully|transaction\s+successful|payment\s+success)",
        text,
        re.IGNORECASE,
    )
    if success_match:
        after = text[success_match.end() : success_match.end() + 100]
        after_amounts = _extract_amounts(after)
        if after_amounts:
            return after_amounts[0]

    filtered = [a for a in amounts if MIN_AMOUNT <= a <= MAX_AMOUNT]
    if not filtered:
        return None

    # Prefer common payment sizes over outliers
    filtered.sort(key=lambda a: (a < 1000, -a))
    return filtered[0]


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
    # Upscale for better OCR on mobile screenshots
    width, height = image.size
    if width < 1200:
        image = image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
    text = pytesseract.image_to_string(image, lang="eng")
    return _normalize_text(text)


def parse_payment_screenshot(image_bytes: bytes) -> Tuple[Optional[ParsedPayment], str]:
    raw_text = extract_text_from_image(image_bytes)
    if not raw_text.strip():
        return None, raw_text

    if not re.search(
        r"payment\s+successful|paid\s+successfully|transaction\s+successful|paid\s+to|sent\s+successfully|ref\.?\s*no\.?|upi\s*transaction\s*id|check\s+balance\s+pay\s+again",
        raw_text,
        re.IGNORECASE,
    ):
        return None, raw_text

    amounts = _extract_amounts(raw_text)
    utrs = _extract_utrs(raw_text)
    amount = _pick_amount(raw_text, amounts)
    utr = _pick_utr(raw_text, utrs)

    if amount is not None and utr:
        return ParsedPayment(utr=utr, amount=amount, raw_text=raw_text), raw_text

    # Paytm success screen sometimes has amount + ref but OCR misses UTR label
    if amount is not None:
        ref = re.search(r"ref\.?\s*no\.?\s*[:\-]?\s*([0-9]{10,20})", raw_text, re.IGNORECASE)
        if ref:
            return ParsedPayment(utr=ref.group(1), amount=amount, raw_text=raw_text), raw_text

        # GPay footer UTR at end of receipt
        tail_utrs = re.findall(r"\b(0[0-9]{11}|[2-6][0-9]{11})\b", raw_text)
        if tail_utrs:
            return ParsedPayment(utr=tail_utrs[-1], amount=amount, raw_text=raw_text), raw_text

    return None, raw_text
