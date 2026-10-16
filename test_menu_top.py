import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from config import SEASON_DURATION_DAYS
from menu import Menu


class MenuTopTests(unittest.TestCase):
    def make_menu(self, sort_by, rows, elapsed):
        db = SimpleNamespace(
            get_season_elapsed=lambda: elapsed,
            get_current_season=lambda: 7,
            top_by=lambda field, limit: rows,
            top_winrate=lambda limit: rows,
        )
        menu = Menu.__new__(Menu)
        menu.brain = SimpleNamespace(db=db)
        menu._top_kb = lambda field: None
        query = SimpleNamespace(
            from_user=SimpleNamespace(id=rows[0][1]),
            message=SimpleNamespace(edit_text=AsyncMock()),
        )
        asyncio.run(menu._show_top(query, sort_by))
        return query.message.edit_text.await_args.args[0]

    def test_sc_top_shows_title_and_season_remaining(self):
        text = self.make_menu(
            "sc",
            [("vasya", 1, 1500.5, "🎲 Новичок")],
            3 * 86400,
        )
        self.assertIn("🏁 Сезон 7 · осталось 17 дн.", text)
        self.assertIn("🥇 👉 @vasya 👈 🎲 Новичок — 1 500.5 SC", text)

    def test_expired_season_uses_less_than_one_day_label(self):
        text = self.make_menu(
            "sc",
            [("vasya", 1, 25, "")],
            (SEASON_DURATION_DAYS + 1) * 86400,
        )
        self.assertIn("осталось &lt; 1 дн.", text)
        self.assertIn("🥇 👉 @vasya 👈 — 25 SC", text)

    def test_winrate_top_shows_title(self):
        text = self.make_menu(
            "winrate",
            [("petya", 2, 8, 10, 80.0, "🍀 Везунчик")],
            0,
        )
        self.assertIn("🥇 👉 @petya 👈 🍀 Везунчик — 80.0%", text)


if __name__ == "__main__":
    unittest.main()
