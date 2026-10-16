import sqlite3
import unittest

from db import DB


class UserRankTests(unittest.TestCase):
    def setUp(self):
        self.db = DB.__new__(DB)
        self.db.conn = sqlite3.connect(":memory:")
        self.db.conn.execute(
            "CREATE TABLE users ("
            "user_id INTEGER PRIMARY KEY, sc INTEGER, lc INTEGER, "
            "level INTEGER, games INTEGER, wins INTEGER)"
        )
        self.db.conn.executemany(
            "INSERT INTO users (user_id, sc, lc, level, games, wins) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (10, 100, 500, 5, 20, 15),
                (20, 100, 700, 6, 10, 8),
                (30, 50, 900, 6, 10, 8),
                (40, 0, 1000, 1, 5, 4),
            ],
        )

    def tearDown(self):
        self.db.conn.close()

    def test_rank_uses_value_then_user_id_and_counts_all_users(self):
        self.assertEqual(self.db.get_user_rank(20, "sc"), (2, 100, 4))

    def test_rank_returns_none_for_missing_users_without_creating_them(self):
        self.assertIsNone(self.db.get_user_rank(99, "sc"))
        self.assertIsNone(self.db.conn.execute(
            "SELECT 1 FROM users WHERE user_id=99"
        ).fetchone())

    def test_winrate_rank_returns_rounded_rate_and_qualified_total(self):
        self.assertEqual(
            self.db.get_user_rank_winrate(20),
            (1, 80.0, 8, 10, 3),
        )

    def test_winrate_rank_returns_none_below_minimum_games(self):
        self.assertIsNone(self.db.get_user_rank_winrate(40))


if __name__ == "__main__":
    unittest.main()
