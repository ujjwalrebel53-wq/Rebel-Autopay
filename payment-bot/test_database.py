import unittest

from database import PaymentDatabase


class TestPaymentDatabase(unittest.TestCase):
    def setUp(self):
        self.db = PaymentDatabase(":memory:")

    def test_add_and_total(self):
        self.db.add_payment("123456789012", 500.0)
        self.db.add_payment("987654321098", 250.5)
        self.assertEqual(self.db.get_count(), 2)
        self.assertEqual(self.db.get_total(), 750.5)

    def test_duplicate_utr(self):
        self.db.add_payment("123456789012", 100.0)
        self.assertTrue(self.db.utr_exists("123456789012"))
        self.assertFalse(self.db.utr_exists("000000000000"))

    def test_recent_payments(self):
        self.db.add_payment("111111111111", 10.0)
        self.db.add_payment("222222222222", 20.0)
        recent = self.db.get_recent(1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].utr, "222222222222")


if __name__ == "__main__":
    unittest.main()
