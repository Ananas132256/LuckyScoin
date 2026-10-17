import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from handlers.game import Game


class GameBalanceSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_game_rejects_bet_if_atomic_debit_fails(self):
        game = Game.__new__(Game)
        game.brain = SimpleNamespace(db=SimpleNamespace(
            subtract_balance_if_available=Mock(return_value=False),
            get_balance=Mock(return_value=5),
            get_user=Mock(),
        ))
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),
        )

        await game._start_game(message, "basic", 10)

        game.brain.db.subtract_balance_if_available.assert_called_once_with(
            1, "lc", 10
        )
        game.brain.db.get_user.assert_not_called()
        message.answer.assert_awaited_once_with("Недостаточно LC. У тебя 5.")


class AdvancedRerollTests(unittest.TestCase):
    def test_reroll_limit_discards_final_grid(self):
        game = Game.__new__(Game)
        game.MAX_REROLLS = 1
        game._spin_grid = lambda *args: [[], [], []]
        reroll_verdict = {
            "reroll_grid": True,
            "total_mult": 1.25,
            "is_item": False,
            "action": "reroll",
        }
        game._evaluate_grid = Mock(
            side_effect=(reroll_verdict.copy(), reroll_verdict.copy())
        )

        async def no_animation(*args):
            pass

        game._anim_reveal_grid = no_animation
        game._anim_pattern_check = AsyncMock()

        result = asyncio.run(
            game._resolve_advanced(None, 10, 1, {}, {}, 0)
        )

        # The grid at the reroll limit is discarded and must never be paid.
        total_mult, is_item, _, rerolls, _, _, _, verdict = result
        self.assertEqual(rerolls, 1)
        self.assertEqual(total_mult, 0)
        self.assertFalse(is_item)
        self.assertEqual(verdict["action"], "loss")
        self.assertEqual(verdict["total_mult"], 0)
        self.assertFalse(verdict["reroll_grid"])
        game._anim_pattern_check.assert_not_awaited()

    def test_successful_grid_keeps_multipliers_accumulated_before_reroll(self):
        game = Game.__new__(Game)
        game.MAX_REROLLS = 1
        game._spin_grid = lambda *args: [[], [], []]

        async def no_animation(*args):
            pass

        game._anim_reveal_grid = no_animation
        game._anim_pattern_check = AsyncMock()
        verdicts = iter((
            {
                "reroll_grid": True,
                "total_mult": 1.25,
                "is_item": False,
                "action": "reroll",
            },
            {
                "reroll_grid": False,
                "total_mult": 2.0,
                "is_item": False,
                "action": "win",
            },
        ))
        game._evaluate_grid = lambda *args: next(verdicts)

        result = asyncio.run(
            game._resolve_advanced(None, 10, 1, {}, {}, 0)
        )

        self.assertEqual(result[0], 3.25)
        self.assertEqual(result[3], 1)
        self.assertEqual(result[7]["total_mult"], 3.25)
        game._anim_pattern_check.assert_awaited_once()


class GridPatternTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.__new__(Game)

    def make_grid(self, cells, symbol="🍎"):
        grid = [["🔥"] * 5 for _ in range(3)]
        for row, column in cells:
            grid[row][column] = symbol
        return grid

    def assert_pattern(self, cells, name, multiplier, symbol="🍎"):
        verdict = self.game._evaluate_grid(self.make_grid(cells, symbol))
        self.assertEqual(verdict["pattern"], name)
        self.assertEqual(verdict["mult"], multiplier)
        self.assertEqual(verdict["total_mult"], multiplier)
        self.assertEqual(verdict["action"], "win")
        self.assertFalse(verdict["reroll_grid"])

    def test_diagonals_match_all_three_offsets(self):
        for start_column in range(3):
            with self.subTest(direction="down", start_column=start_column):
                self.assert_pattern(
                    [
                        (0, start_column),
                        (1, start_column + 1),
                        (2, start_column + 2),
                    ],
                    f"Диагональ ↘ (старт {start_column + 1})",
                    3,
                )
        for start_column in range(2, 5):
            with self.subTest(direction="up", start_column=start_column):
                self.assert_pattern(
                    [
                        (0, start_column),
                        (1, start_column - 1),
                        (2, start_column - 2),
                    ],
                    f"Диагональ ↗ (старт {start_column + 1})",
                    3,
                )

    def test_crosses_match_each_center_only_for_identical_fruits(self):
        for center_column in range(1, 4):
            cells = [
                (0, center_column),
                (1, center_column - 1),
                (1, center_column),
                (1, center_column + 1),
                (2, center_column),
            ]
            with self.subTest(center_column=center_column):
                self.assert_pattern(
                    cells, f"Крест (центр {center_column + 1})", 5
                )

            grid = self.make_grid(cells, "🎲")
            self.assertEqual(
                self.game._match_grid_pattern(
                    grid,
                    next(
                        pattern for pattern in self.game._expand_patterns()
                        if pattern["name"] == f"Крест (центр {center_column + 1})"
                    ),
                ),
                0,
            )

    def test_frame_requires_all_four_corners_to_match(self):
        cells = [(0, 0), (0, 4), (2, 0), (2, 4)]
        self.assert_pattern(cells, "Рамка", 4)
        grid = self.make_grid(cells)
        grid[2][4] = "🍋"
        frame = next(
            pattern for pattern in self.game._expand_patterns()
            if pattern["name"] == "Рамка"
        )
        self.assertEqual(self.game._match_grid_pattern(grid, frame), 0)

    def test_vertical_pattern_matches_every_column(self):
        for column in range(5):
            with self.subTest(column=column):
                self.assert_pattern(
                    [(row, column) for row in range(3)],
                    f"Вертикаль (столбец {column + 1})", 3,
                )

    def test_grid_without_pattern_uses_line_evaluation(self):
        grid = [
            ["🍎", "🍎", "🍎", "🍋", "🍍"],
            ["🍍", "🍋", "🍭", "🍎", "🍋"],
            ["🍋", "🍭", "🍍", "🍋", "🍍"],
        ]
        verdict = self.game._evaluate_grid(grid)
        self.assertNotIn("pattern", verdict)
        self.assertEqual(verdict["action"], "win")
        self.assertEqual(verdict["lines_won"], 1)
        self.assertEqual(verdict["total_mult"], 1.5)

    def test_grid_patterns_reject_fire_and_wrong_symbol_groups(self):
        pattern = next(
            pattern for pattern in self.game._expand_patterns()
            if pattern["name"] == "Крест (центр 3)"
        )
        grid = self.make_grid(pattern["cells"], "🎲")
        self.assertEqual(self.game._match_grid_pattern(grid, pattern), 0)
        grid[0][2] = "🔥"
        self.assertEqual(self.game._match_grid_pattern(grid, pattern), 0)

        all_pattern = next(
            pattern for pattern in self.game._expand_patterns()
            if pattern["name"].startswith("Вертикаль")
        )
        grid = self.make_grid(all_pattern["cells"], "🔥")
        self.assertEqual(self.game._match_grid_pattern(grid, all_pattern), 0)

    def test_expand_patterns_creates_five_vertical_checks(self):
        patterns = self.game._expand_patterns()
        verticals = [
            pattern for pattern in patterns
            if pattern["name"].startswith("Вертикаль")
        ]
        self.assertEqual(len(patterns), 15)
        self.assertEqual(
            [pattern["name"] for pattern in verticals],
            [f"Вертикаль (столбец {column})" for column in range(1, 6)],
        )
        self.assertEqual(
            [pattern["cells"] for pattern in verticals],
            [
                [(0, column), (1, column), (2, column)]
                for column in range(5)
            ],
        )

    def test_sample_grid_matches_second_down_diagonal(self):
        grid = [
            ["🍀", "🍀", "💣", "💣", "🍍"],
            ["🍎", "🍀", "🍀", "🍋", "🍋"],
            ["🍭", "🍭", "🍍", "🍀", "💣"],
        ]
        down_diagonal = next(
            pattern for pattern in self.game._expand_patterns()
            if pattern["name"] == "Диагональ ↘ (старт 2)"
        )
        self.assertEqual(
            self.game._match_grid_pattern(grid, down_diagonal), 3
        )
        verdict = self.game._evaluate_grid(grid)
        self.assertEqual(verdict["pattern"], down_diagonal["name"])
        self.assertEqual(verdict["mult"], 3)

    def test_pattern_animation_checks_one_pattern_per_frame(self):
        self.game.brain = SimpleNamespace(
            db=SimpleNamespace(get_fast_anim=Mock(return_value=1))
        )
        self.game._expand_patterns = Mock(return_value=[
            {
                "name": "Test & pattern",
                "cells": [(0, 0)],
                "mult": 2,
            },
            {
                "name": "No match",
                "cells": [(0, 1)],
                "mult": 3,
            },
        ])
        self.game._match_grid_pattern = Mock(side_effect=(2, 0))
        self.game._render_grid = AsyncMock()
        grid = [
            ["🍎", "🍍", "🍭", "🍋", "🍎"],
            ["🍍", "🍭", "🍋", "🍎", "🍍"],
            ["🍭", "🍋", "🍎", "🍍", "🍭"],
        ]

        async def no_sleep(_):
            pass

        with patch("handlers.game.asyncio.sleep", new=no_sleep):
            matched = asyncio.run(
                self.game._anim_pattern_check(None, 10, grid, 42)
            )

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][1], 2)
        frames = self.game._render_grid.await_args_list
        self.assertEqual(len(frames), 6)
        self.assertIn("Test &amp; pattern", frames[0].args[4])
        self.assertIn("🟨", frames[0].args[3])
        self.assertEqual(frames[1].args[3], "\n".join(
            " | ".join(line) for line in grid
        ))
        self.assertIn("✅ Совпало", frames[2].args[4])
        self.assertIn("🟨", frames[3].args[3])
        self.assertIn("❌ Не совпало", frames[4].args[4])
        self.assertIn("Итог", frames[5].args[4])


class SpinAnimationTests(unittest.IsolatedAsyncioTestCase):
    async def test_spin_animation_has_ten_fake_real_frames_and_final_stop(self):
        game = Game.__new__(Game)
        game._render = AsyncMock()
        cfg = {"label": "🎰"}
        symbols = ["A", "B", "C", "D", "E"]

        with patch("handlers.game.random.choice", return_value="🎲"):
            await game._anim_spin(None, "test", 10, cfg, symbols, 42)

        self.assertEqual(game._render.await_count, 11)
        frames = [
            call.args[3].split(" | ")
            for call in game._render.await_args_list
        ]
        self.assertEqual(frames[0], ["🎲", "🌫️", "🌫️", "🌫️", "🌫️"])
        self.assertEqual(frames[1], ["A", "🌫️", "🌫️", "🌫️", "🌫️"])
        self.assertEqual(frames[2], ["A", "🎲", "🌫️", "🌫️", "🌫️"])
        self.assertEqual(frames[3], ["A", "B", "🌫️", "🌫️", "🌫️"])
        self.assertEqual(frames[8], ["A", "B", "C", "D", "🎲"])
        self.assertEqual(frames[9], ["A", "B", "C", "D", "E"])
        final_frame = game._render.await_args_list[-1].args[3]
        self.assertEqual(final_frame, "A | B | C | D | E")
        self.assertIn("Стоп!", game._render.await_args_list[-1].args[4])

    async def test_safe_edit_uses_fast_animation_preference(self):
        for fast_anim, expected_delay in ((1, 0.2), (0, 1.0)):
            with self.subTest(fast_anim=fast_anim):
                game = Game.__new__(Game)
                game.brain = SimpleNamespace(
                    db=SimpleNamespace(
                        get_fast_anim=Mock(return_value=fast_anim)
                    )
                )
                game._edit_lock = asyncio.Lock()
                game._last_edit = 9.9
                message = SimpleNamespace(edit_text=AsyncMock())
                with patch("handlers.game.time.time", return_value=10), patch(
                    "handlers.game.asyncio.sleep", new=AsyncMock()
                ) as sleep:
                    await game._safe_edit(message, "frame", user_id=42)

                sleep.assert_awaited_once()
                self.assertAlmostEqual(
                    sleep.await_args.args[0],
                    expected_delay,
                )
                game.brain.db.get_fast_anim.assert_called_once_with(42)

    async def test_advanced_animation_reveals_columns_in_eleven_frames(self):
        game = Game.__new__(Game)
        game._render_grid = AsyncMock()
        grid = [
            ["A1", "A2", "A3", "A4", "A5"],
            ["B1", "B2", "B3", "B4", "B5"],
            ["C1", "C2", "C3", "C4", "C5"],
        ]

        with patch("handlers.game.random.choice", return_value="🎲"):
            await game._anim_reveal_grid(
                None, "Продвинутое казино", 10, grid, {"label": "🎰"}, 42
            )

        self.assertEqual(game._render_grid.await_count, 11)
        first_grid = game._render_grid.await_args_list[0].args[3].splitlines()
        self.assertEqual(first_grid[0], "🎲 | 🌫️ | 🌫️ | 🌫️ | 🌫️")
        second_grid = game._render_grid.await_args_list[1].args[3].splitlines()
        self.assertEqual(second_grid[0], "A1 | 🌫️ | 🌫️ | 🌫️ | 🌫️")
        final_grid = game._render_grid.await_args_list[-1].args[3].splitlines()
        self.assertEqual(final_grid[2], "C1 | C2 | C3 | C4 | C5")

    async def test_reroll_and_overheat_use_requested_frame_counts(self):
        game = Game.__new__(Game)
        game._render = AsyncMock()
        cfg = {"label": "🎰"}
        symbols = ["A", "B", "C", "D", "E"]

        await game._anim_unstable_reroll(
            None, "test", 10, symbols, "A", 1, 1, 0, 42
        )
        reroll_frames = [
            call.args[3].split(" | ")
            for call in game._render.await_args_list
        ]
        self.assertEqual(len(reroll_frames), 5)
        self.assertEqual(reroll_frames[0], ["🌫️", "B", "C", "D", "E"])
        self.assertEqual(reroll_frames[-1], ["🌫️"] * 5)

        game._render.reset_mock()
        await game._anim_heat_ignite(
            None, "test", 10, symbols, [0, 1, 2, 3, 4], 5, 42
        )
        self.assertEqual(game._render.await_count, 6)
        self.assertIn("Что-то возгорается", game._render.await_args_list[0].args[4])
        self.assertEqual(
            game._render.await_args_list[-1].args[3],
            "🔥 | 🔥 | 🔥 | 🔥 | 🔥",
        )

    async def test_bomb_animation_uses_two_or_three_frames(self):
        game = Game.__new__(Game)
        game._render = AsyncMock()
        before = ["💣", "💣", "💣", "A", "A"]
        blast = ["💥", "💥", "💥", "A", "A"]

        await game._cinematic_bomb_explosion(
            None, "test", 10, before, blast, -10, 3, 42
        )
        self.assertEqual(game._render.await_count, 2)

        game._render.reset_mock()
        await game._cinematic_bomb_explosion(
            None, "test", 10, before,
            ["💥", "💥", "💥", "🔥", "🔥"], -10, 3, 42,
        )
        self.assertEqual(game._render.await_count, 3)


class SpinModeTests(unittest.TestCase):
    def test_spin_type_limits_and_unlock_levels(self):
        self.assertEqual(len(Game.SPIN_TYPES), 9)
        self.assertEqual(
            Game.SPIN_TYPES,
            {
                "mini": ("Mini", 1, 3, 0.1),
                "safe": ("Safe", 5, 25, 0.5),
                "common": ("Common", 1, 5, 1),
                "uncommon": ("Uncommon", 6, 250, 2),
                "rare": ("Rare", 250, 1000, 5),
                "ultra": ("Ultra", 1000, 10000, 10),
                "epic": ("Epic", 10000, 1000000, 15),
                "advanced": ("Advanced", 100, 5000, 1.5),
                "hardcore": ("Hardcore", 500, 2000, 15),
            },
        )
        self.assertEqual(Game.LEVEL_REQ["mini"], 3)
        self.assertEqual(Game.LEVEL_REQ["hardcore"], 65)

    def test_mini_only_generates_three_fruit_cells_and_evaluates_no_patterns(self):
        game = Game.__new__(Game)
        chosen_populations = []

        def choose(population, weights, k):
            chosen_populations.append(population)
            return [population[0]]

        with patch("handlers.game.random.random", return_value=1), patch(
            "handlers.game.random.choices", side_effect=choose
        ):
            symbols = game._spin(spin_key="mini")

        self.assertEqual(len(symbols), 3)
        self.assertTrue(set(symbols) <= set(Game.FRUIT_SYMBOLS))
        self.assertTrue(all(
            set(population) <= set(Game.FRUIT_SYMBOLS)
            for population in chosen_populations
        ))
        self.assertEqual(
            game._evaluate(["🍭", "🍭", "🍭"], spin_key="mini")["action"],
            "win",
        )
        self.assertEqual(
            game._evaluate(["🍎", "🍍", "🍋"], spin_key="mini")["action"],
            "loss",
        )

    def test_safe_and_hardcore_symbol_subsets(self):
        game = Game.__new__(Game)
        populations = []

        def choose(population, weights, k):
            populations.append(set(population))
            return [population[0]]

        with patch("handlers.game.random.random", return_value=1), patch(
            "handlers.game.random.choices", side_effect=choose
        ):
            game._spin(spin_key="safe")
            game._spin(spin_key="hardcore")

        self.assertTrue(all(
            population == set(Game.FRUIT_SYMBOLS)
            for population in populations[:5]
        ))
        self.assertTrue(all(
            population == set(Game.HARDCORE_SYMBOLS)
            for population in populations[5:]
        ))

    def test_hardcore_restores_saved_score_even_if_spin_raises(self):
        game = Game.__new__(Game)
        db = SimpleNamespace(
            get_overheat_score=Mock(return_value=23),
            set_overheat_score=Mock(),
        )
        game.brain = SimpleNamespace(db=db)

        async def fail_inner(*args):
            raise RuntimeError("spin failure")

        game._start_game_inner = fail_inner
        message = SimpleNamespace(from_user=SimpleNamespace(id=42))

        with self.assertRaisesRegex(RuntimeError, "spin failure"):
            asyncio.run(game._start_game(message, "hardcore", 500))

        self.assertEqual(
            db.set_overheat_score.call_args_list,
            [unittest.mock.call(42, 50), unittest.mock.call(42, 23)],
        )

    def test_advanced_patterns_handler_is_removed(self):
        self.assertFalse(hasattr(Game, "cb_advanced_patterns"))


class SpinCategoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_category_lists_show_only_their_modes_and_lock_by_level(self):
        game = Game.__new__(Game)
        game.brain = SimpleNamespace(
            db=SimpleNamespace(get_level_xp=Mock(return_value=(4, 0)))
        )
        game._safe_edit = AsyncMock()
        query = SimpleNamespace(
            from_user=SimpleNamespace(id=1),
            message=SimpleNamespace(),
            answer=AsyncMock(),
        )

        await game.cb_regular_list(query)
        regular_kb = game._safe_edit.await_args.kwargs["reply_markup"]
        regular_callbacks = [
            button.callback_data
            for row in regular_kb.inline_keyboard
            for button in row
        ]
        self.assertEqual(
            regular_callbacks[:7],
            ["choose_mini", "locked", "choose_common", "locked",
             "locked", "locked", "locked"],
        )
        self.assertIn("common", Game.REGULAR_SPINS)
        self.assertNotIn("choose_advanced", regular_callbacks)

        game._safe_edit.reset_mock()
        game.brain.db.get_level_xp.return_value = (12, 0)
        await game.cb_effects_list(query)
        effects_kb = game._safe_edit.await_args.kwargs["reply_markup"]
        effects_callbacks = [
            button.callback_data
            for row in effects_kb.inline_keyboard
            for button in row
        ]
        self.assertEqual(effects_callbacks[:2], ["choose_advanced", "locked"])


if __name__ == "__main__":
    unittest.main()
