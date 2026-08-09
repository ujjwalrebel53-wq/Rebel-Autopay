import unittest

from payment_utils import is_valid_utr, parse_amount, parse_manual_entry


class TestPaymentUtils(unittest.TestCase):
    def test_parse_manual_entry(self):
        self.assertEqual(parse_manual_entry("123456789012 500"), ("123456789012", 500.0))
        self.assertEqual(parse_manual_entry("123456789012 1,250.50"), ("123456789012", 1250.5))

    def test_parse_manual_entry_invalid(self):
        self.assertIsNone(parse_manual_entry("abc 500"))
        self.assertIsNone(parse_manual_entry("123 500"))

    def test_parse_amount(self):
        self.assertEqual(parse_amount("500"), 500.0)
        self.assertEqual(parse_amount("₹1,250"), 1250.0)
        self.assertEqual(parse_amount("Rs 99.50"), 99.5)

    def test_is_valid_utr(self):
        self.assertTrue(is_valid_utr("123456789012"))
        self.assertFalse(is_valid_utr("12345"))


if __name__ == "__main__":
    unittest.main()
