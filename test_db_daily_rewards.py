import sqlite3
import unittest
from unittest.mock import patch

from db import DB


class DailyRewardTests(unittest.TestCase):
    def setUp(self):
        self.db = DB.__new__(DB)
        self.db.conn = sqlite3.connect(":memory:")
        self.db.conn.execute("""
            CREATE TABLE daily_rewards (
                user_id INTEGER PRIMARY KEY,
                streak INTEGER DEFAULT 0,
                last_claim INTEGER DEFAULT 0,
                wheel_ts INTEGER DEFAULT 0
            )
        """)

    def tearDown(self):
        self.db.conn.close()

    def test_get_daily_state_for_missing_user_does_not_create_row(self):
        with patch("db.time.time", return_value=1_000_000):
            state = self.db.get_daily_state(42)

        self.assertEqual(state, {
            "streak": 0,
            "last_claim": 0,
            "wheel_ts": 0,
            "can_claim": True,
            "next_claim_at": 1_000_000,
            "streak_lost": False,
        })
        self.assertIsNone(self.db.conn.execute(
            "SELECT 1 FROM daily_rewards WHERE user_id=42"
        ).fetchone())

    def test_claim_daily_is_available_at_24_hour_boundary(self):
        self.db.conn.execute(
            "INSERT INTO daily_rewards (user_id, streak, last_claim) "
            "VALUES (42, 3, 1_000_000)"
        )

        with patch("db.time.time", return_value=1_000_000 + 24 * 3600 - 1):
            self.assertFalse(self.db.claim_daily(42, 4))
        with patch("db.time.time", return_value=1_000_000 + 24 * 3600):
            self.assertTrue(self.db.claim_daily(42, 4))

        self.assertEqual(
            self.db.conn.execute(
                "SELECT streak, last_claim FROM daily_rewards WHERE user_id=42"
            ).fetchone(),
            (4, 1_086_400),
        )

    def test_streak_lost_starts_at_48_hours(self):
        self.db.conn.execute(
            "INSERT INTO daily_rewards (user_id, streak, last_claim) "
            "VALUES (42, 3, 1_000_000)"
        )

        with patch("db.time.time", return_value=1_000_000 + 48 * 3600 - 1):
            self.assertFalse(self.db.get_daily_state(42)["streak_lost"])
        with patch("db.time.time", return_value=1_000_000 + 48 * 3600):
            state = self.db.get_daily_state(42)
        self.assertTrue(state["streak_lost"])
        self.assertTrue(state["can_claim"])

    def test_record_wheel_spin_creates_and_updates_state(self):
        with patch("db.time.time", return_value=1_234_567):
            self.db.record_wheel_spin(42)
        with patch("db.time.time", return_value=1_234_568):
            self.db.record_wheel_spin(42)

        self.assertEqual(
            self.db.conn.execute(
                "SELECT streak, last_claim, wheel_ts "
                "FROM daily_rewards WHERE user_id=42"
            ).fetchone(),
            (0, 0, 1_234_568),
        )

    def test_migration_creates_daily_rewards_table_and_index(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.executescript("""
            CREATE TABLE users (user_id INTEGER PRIMARY KEY);
            CREATE TABLE inventory (
                user_id INTEGER, item_id INTEGER, quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, item_id)
            );
            CREATE TABLE casinos (user_id INTEGER PRIMARY KEY);
            CREATE TABLE user_badges (user_id INTEGER, badge_id TEXT);
            CREATE TABLE user_badge_slot_state (
                user_id INTEGER,
                slot INTEGER,
                badge_id TEXT,
                hp INTEGER NOT NULL,
                roll_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, slot, badge_id)
            );
        """)
        db = DB.__new__(DB)
        db.conn = conn

        db._migrate()

        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(daily_rewards)")
        }
        indexes = {
            row[1] for row in conn.execute("PRAGMA index_list(daily_rewards)")
        }
        self.assertEqual(
            columns, {"user_id", "streak", "last_claim", "wheel_ts"}
        )
        self.assertIn("idx_daily_rewards_last_claim", indexes)


if __name__ == "__main__":
    unittest.main()
