import sqlite3
import unittest
from contextlib import redirect_stdout
from io import StringIO

from db import DB


class LegacyTitleRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.db = DB.__new__(DB)
        self.db.conn = sqlite3.connect(":memory:")
        self.db.conn.executescript("""
            CREATE TABLE items (
                item_id INTEGER PRIMARY KEY,
                category TEXT NOT NULL
            );
            CREATE TABLE inventory (
                user_id INTEGER,
                item_id INTEGER,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, item_id)
            );
            CREATE TABLE system_flags (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            INSERT INTO items (item_id, category) VALUES
                (1, 'title'),
                (2, 'title'),
                (3, 'badge'),
                (4, 'title');
            INSERT INTO inventory (user_id, item_id, quantity) VALUES
                (10, 1, 2),
                (10, 101, 3),
                (10, 2, 1),
                (10, 3, 4),
                (11, 4, 5);
        """)

    def tearDown(self):
        self.db.conn.close()

    def test_recovers_title_rows_merges_quantities_and_runs_once(self):
        output = StringIO()
        with redirect_stdout(output):
            migrated = self.db.recover_legacy_titles()

        self.assertEqual(migrated, 3)
        self.assertEqual(output.getvalue(), "Legacy titles recovered: 3\n")
        self.assertEqual(
            self.db.conn.execute(
                "SELECT user_id, item_id, quantity FROM inventory "
                "ORDER BY user_id, item_id"
            ).fetchall(),
            [
                (10, 3, 4),
                (10, 101, 5),
                (10, 102, 1),
                (11, 104, 5),
            ],
        )
        self.assertEqual(
            self.db.get_flag("legacy_titles_recovered"),
            "1",
        )
        self.assertFalse(self.db.conn.in_transaction)
        self.assertEqual(self.db.recover_legacy_titles(), 0)
        self.assertEqual(
            self.db.conn.execute(
                "SELECT quantity FROM inventory WHERE user_id=10 AND item_id=101"
            ).fetchone(),
            (5,),
        )

    def test_zero_rows_still_sets_guard_and_prints_summary(self):
        self.db.conn.execute("DELETE FROM inventory")
        output = StringIO()

        with redirect_stdout(output):
            migrated = self.db.recover_legacy_titles()

        self.assertEqual(migrated, 0)
        self.assertEqual(output.getvalue(), "Legacy titles recovered: 0\n")
        self.assertEqual(self.db.get_flag("legacy_titles_recovered"), "1")


if __name__ == "__main__":
    unittest.main()
