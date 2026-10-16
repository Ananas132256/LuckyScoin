import sqlite3
import unittest

from db import DB


class DatabaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.db = DB.__new__(DB)
        self.db.conn = sqlite3.connect(":memory:")
        self.db.conn.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                sc INTEGER DEFAULT 0,
                lc INTEGER DEFAULT 15,
                total_bets INTEGER DEFAULT 0,
                total_won INTEGER DEFAULT 0,
                total_lost INTEGER DEFAULT 0
            )
        """)
        self.db.conn.execute(
            "INSERT INTO users (user_id, sc, lc) VALUES (1, 100, 200)"
        )

    def tearDown(self):
        self.db.conn.close()

    def test_balance_subtraction_is_atomic_and_never_negative(self):
        self.assertFalse(
            self.db.subtract_balance_if_available(1, "sc", 101)
        )
        self.assertEqual(self.db.get_balance(1, "sc"), 100)

        self.assertTrue(
            self.db.subtract_balance_if_available(1, "sc", 100)
        )
        self.assertEqual(self.db.get_balance(1, "sc"), 0)

    def test_balance_subtraction_rejects_invalid_currency_or_amount(self):
        with self.assertRaises(ValueError):
            self.db.subtract_balance_if_available(1, "gold", 1)
        with self.assertRaises(ValueError):
            self.db.subtract_balance_if_available(1, "lc", -1)
        self.assertEqual(self.db.get_balance(1, "lc"), 200)

    def test_loss_stats_do_not_count_the_bet_twice(self):
        self.db.add_bet_stats(1, 50, -70)

        row = self.db.conn.execute(
            "SELECT total_bets, total_lost FROM users WHERE user_id=1"
        ).fetchone()
        self.assertEqual(row, (50, 70))

    def test_zero_balance_subtraction_is_valid(self):
        self.assertTrue(
            self.db.subtract_balance_if_available(1, "sc", 0)
        )
        self.assertEqual(self.db.get_balance(1, "sc"), 100)


if __name__ == "__main__":
    unittest.main()
