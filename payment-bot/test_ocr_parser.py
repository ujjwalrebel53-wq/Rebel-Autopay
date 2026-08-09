import unittest

from ocr_parser import _extract_amounts, _extract_utrs, _pick_amount, _pick_utr, _normalize_text


class TestOcrParser(unittest.TestCase):
    def test_gpay_style_text(self):
        text = _normalize_text(
            "Payment successful\n"
            "Paid to Merchant Store\n"
            "Amount Rs 500.00\n"
            "UPI transaction ID 123456789012\n"
            "From your account"
        )
        utrs = _extract_utrs(text)
        amounts = _extract_amounts(text)
        self.assertEqual(_pick_utr(text, utrs), "123456789012")
        self.assertEqual(_pick_amount(text, amounts), 500.0)

    def test_phonepe_style_text(self):
        text = _normalize_text(
            "Transaction Successful\n"
            "Paid Rs 1,250.00\n"
            "UTR: 987654321098\n"
            "To John Doe"
        )
        utrs = _extract_utrs(text)
        amounts = _extract_amounts(text)
        self.assertEqual(_pick_utr(text, utrs), "987654321098")
        self.assertEqual(_pick_amount(text, amounts), 1250.0)

    def test_paytm_style_text(self):
        text = _normalize_text(
            "Money sent successfully\n"
            "Amount Paid Rs 99\n"
            "UPI Ref No: 112233445566"
        )
        utrs = _extract_utrs(text)
        amounts = _extract_amounts(text)
        self.assertEqual(_pick_utr(text, utrs), "112233445566")
        self.assertEqual(_pick_amount(text, amounts), 99.0)

    def test_duplicate_utr_extraction(self):
        text = "UTR 123456789012 and again 123456789012"
        utrs = _extract_utrs(text)
        self.assertEqual(len(utrs), 1)


if __name__ == "__main__":
    unittest.main()
