#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from database import PaymentDatabase
from ocr_parser import parse_payment_screenshot


def process_folder(folder: str, db_path: str = "payments_scan.db") -> None:
    root = Path(folder)
    images = sorted(
        p
        for p in root.rglob("*")
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )

    db = PaymentDatabase(db_path)
    results = {
        "total_images": len(images),
        "parsed": [],
        "failed": [],
        "duplicates": [],
    }

    for image_path in images:
        try:
            image_bytes = image_path.read_bytes()
            parsed, raw_text = parse_payment_screenshot(image_bytes)
        except Exception as exc:
            results["failed"].append(
                {"file": str(image_path.name), "reason": str(exc)}
            )
            continue

        if parsed is None:
            results["failed"].append(
                {
                    "file": str(image_path.name),
                    "reason": "UTR/amount not detected",
                    "preview": raw_text[:120],
                }
            )
            continue

        if db.utr_exists(parsed.utr):
            results["duplicates"].append(
                {
                    "file": str(image_path.name),
                    "utr": parsed.utr,
                    "amount": parsed.amount,
                }
            )
            continue

        db.add_payment(parsed.utr, parsed.amount)
        results["parsed"].append(
            {
                "file": str(image_path.name),
                "utr": parsed.utr,
                "amount": parsed.amount,
            }
        )

    results["saved_count"] = db.get_count()
    results["total_amount"] = db.get_total()
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    process_folder(folder)
