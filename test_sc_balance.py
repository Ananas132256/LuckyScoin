import sqlite3
import unittest

from db import DB
from utils import format_sc


class SCBalanceTests(unittest.TestCase):
    def setUp(self):
        self.db = DB.__new__(DB)
        self.db.conn = sqlite3.connect(":memory:")
        self.db.conn.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                sc INTEGER DEFAULT 0,
                lc INTEGER DEFAULT 15
            )
        """)
        self.db.conn.execute(
            "INSERT INTO users (user_id, sc, lc) VALUES (1, 100, 200)"
        )

    def tearDown(self):
        self.db.conn.close()

    def test_sc_add_set_and_subtract_round_to_two_places(self):
        self.db.add_balance(1, "sc", 0.1)
        self.db.add_balance(1, "sc", 0.2)
        self.assertEqual(self.db.get_balance(1, "sc"), 100.3)

        self.db.set_balance(1, "sc", 2.345)
        self.assertEqual(self.db.get_balance(1, "sc"), 2.35)
        self.assertTrue(self.db.subtract_balance_if_available(1, "sc", 0.1))
        self.assertEqual(self.db.get_balance(1, "sc"), 2.25)
        self.assertFalse(self.db.subtract_balance_if_available(1, "sc", 2.26))
        self.assertEqual(self.db.get_balance(1, "sc"), 2.25)

    def test_legacy_integer_sc_is_read_as_float(self):
        self.assertEqual(self.db.get_balance(1, "sc"), 100.0)
        self.assertIsInstance(self.db.get_balance(1, "sc"), float)

    def test_new_user_receives_starting_lc_even_with_legacy_default(self):
        self.db._ensure(2)
        self.assertEqual(
            self.db.conn.execute(
                "SELECT lc FROM users WHERE user_id=2"
            ).fetchone()[0],
            25,
        )

    def test_sc_formatting_omits_trailing_zeroes_and_preserves_decimals(self):
        self.assertEqual(format_sc(1234.5), "1 234.5")
        self.assertEqual(format_sc(1234.0), "1 234")
        self.assertEqual(format_sc(0.25), "0.25")


if __name__ == "__main__":
    unittest.main()
