import sqlite3
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import core.database as db_module
from core.database import DB
from handlers.game import Game
from handlers.shop import Shop
from utils import in_date_range


class HalloweenDateTests(unittest.TestCase):
    def test_date_range_includes_both_boundaries(self):
        start = (2026, 10, 26)
        end = (2026, 11, 1)
        self.assertTrue(in_date_range(start, end, date(2026, 10, 26)))
        self.assertTrue(in_date_range(start, end, date(2026, 11, 1)))
        self.assertFalse(in_date_range(start, end, date(2026, 10, 25)))
        self.assertFalse(in_date_range(start, end, date(2026, 11, 2)))

    def test_shop_filters_halloween_catalog_by_date(self):
        database = DB.__new__(DB)
        database.conn = sqlite3.connect(":memory:")
        database.conn.executescript("""
            CREATE TABLE shop_meta (id INTEGER, next_refresh INTEGER);
            INSERT INTO shop_meta VALUES (1, 5000);
            CREATE TABLE shop_stock (item_id INTEGER PRIMARY KEY);
            CREATE TABLE items (
                item_id INTEGER, name TEXT, price_sc INTEGER,
                rarity TEXT, category TEXT
            );
            INSERT INTO shop_stock VALUES (21), (51), (52);
            INSERT INTO items VALUES
                (21, '🍃 Листочек', 10, 'common', 'badge'),
                (51, '🎃 Джек', 5000, 'legendary', 'badge'),
                (52, '🌀 Круговорот', 1500, 'rare', 'badge');
        """)
        try:
            for current_date, expected in (
                (date(2026, 10, 25), {21}),
                (date(2026, 10, 31), {21, 51, 52}),
                (date(2026, 11, 1), {21, 52}),
                (date(2026, 11, 2), {21}),
            ):
                fake_datetime = SimpleNamespace(
                    now=lambda: datetime.combine(
                        current_date, datetime.min.time()
                    )
                )
                with (
                    patch.object(db_module.time, "time", return_value=1000),
                    patch.object(db_module, "datetime", fake_datetime),
                ):
                    self.assertEqual(
                        {row[0] for row in database.get_shop_items()},
                        expected,
                    )
        finally:
            database.conn.close()


class HalloweenGameTests(unittest.TestCase):
    def make_game(self, equipped=True):
        game = Game.__new__(Game)
        game.brain = SimpleNamespace(db=SimpleNamespace(
            get_user_badges=Mock(return_value={
                0: "halloween_cyclone" if equipped else None,
            }),
        ))
        return game

    def test_cyclone_applies_example_roll(self):
        game = self.make_game()
        self.assertEqual(
            game._apply_cyclone(
                ["🍎", "🍍", "🌀", "🍎", "🍎"], 123
            ),
            ["🍎", "🍎", "🍎", "🍍", "🍎"],
        )

    def test_cyclone_wraps_edge_neighbors_and_is_equipment_gated(self):
        game = self.make_game()
        self.assertEqual(
            game._apply_cyclone(
                ["🌀", "🍎", "🍍", "🍋", "🎲"], 123
            ),
            ["🎲", "🎲", "🍍", "🍋", "🍎"],
        )
        self.assertEqual(
            self.make_game(equipped=False)._apply_cyclone(
                ["🍎", "🍍", "🌀", "🍎", "🍎"], 123
            ),
            ["🍎", "🍍", "🌀", "🍎", "🍎"],
        )

    def test_evaluation_uses_cyclone_result_for_matching(self):
        game = self.make_game()
        verdict = game._evaluate(
            ["🍎", "🍍", "🌀", "🍎", "🍎"],
            user_id=123,
        )
        self.assertEqual(verdict["action"], "win")
        self.assertEqual(verdict["sym"], "🍎")
        self.assertEqual(verdict["run"], 3)
        self.assertEqual(
            verdict["symbols"], ["🍎", "🍎", "🍎", "🍍", "🍎"]
        )

    def test_jack_multipliers_follow_stake_parity_and_dates(self):
        self.assertEqual(
            Game._jack_multipliers(2, date(2026, 10, 29)), (6, 2)
        )
        self.assertEqual(
            Game._jack_multipliers(3, date(2026, 10, 29)), (2, 4)
        )
        self.assertEqual(
            Game._jack_multipliers(2, date(2026, 10, 31)), (9, 3)
        )
        self.assertEqual(
            Game._jack_multipliers(3, date(2026, 11, 1)), (3, 6)
        )
        self.assertEqual(
            Game._jack_multipliers(2, date(2026, 11, 2)), (3, 1)
        )

    def test_jack_passive_effect_is_xp_bonus(self):
        from content.catalog import BADGES
        from content.effects import get_badge_effects

        self.assertEqual(
            get_badge_effects(BADGES["halloween_jack"], {}),
            {"xp_bonus": 0.25},
        )

    def test_cyclone_symbol_is_only_included_when_equipped(self):
        for equipped in (True, False):
            game = self.make_game(equipped)
            with patch("handlers.game.random.choices", return_value=["🍎"]) as choices:
                game._spin(user_id=123)
            symbols = choices.call_args.args[0]
            self.assertEqual("🌀" in symbols, equipped)


class HalloweenShopTests(unittest.IsolatedAsyncioTestCase):
    async def test_buying_event_badge_awards_and_equips_event_title(self):
        database = SimpleNamespace(
            get_item=Mock(return_value={
                "item_id": 51,
                "name": "🎃 Джек",
                "price_sc": 5000,
                "category": "badge",
            }),
            buy_item=Mock(return_value=(True, "Покупка успешна")),
            log_event=Mock(),
            has_item=Mock(return_value=0),
            add_item=Mock(),
            set_title=Mock(),
        )
        shop = Shop(SimpleNamespace(db=database))
        shop.cb_cat = AsyncMock()
        query = SimpleNamespace(
            data="shop_buy_confirm_51",
            from_user=SimpleNamespace(id=123),
            answer=AsyncMock(),
        )
        halloween_datetime = SimpleNamespace(
            now=lambda: datetime(2026, 10, 30)
        )

        with patch("utils.datetime", halloween_datetime):
            await shop.cb_buy_confirm(query)

        database.add_item.assert_called_once_with(123, 120, 1)
        database.set_title.assert_called_once_with(123, "🎃 Хеллоуин2026")


if __name__ == "__main__":
    unittest.main()
