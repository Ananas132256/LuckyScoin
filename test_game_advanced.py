import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from game import Game


class AdvancedRerollTests(unittest.TestCase):
    def test_reroll_limit_discards_final_grid(self):
        game = Game.__new__(Game)
        game.MAX_REROLLS = 1
        pattern = next(
            pattern for pattern in game.PATTERNS
            if pattern.get("action") == "reroll"
        )
        symbols = [symbol for symbol in game.SYMBOLS if symbol != "🔥"]
        labels = {}
        line = []
        for label in pattern["pattern"]:
            if label not in labels:
                labels[label] = symbols[len(labels)]
            line.append(labels[label])

        game._spin_grid = lambda *args: [line, line, line]

        async def no_animation(*args):
            pass

        game._anim_reveal_grid = no_animation

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

    def test_successful_grid_keeps_multipliers_accumulated_before_reroll(self):
        game = Game.__new__(Game)
        game.MAX_REROLLS = 1
        game._spin_grid = lambda *args: [[], [], []]

        async def no_animation(*args):
            pass

        game._anim_reveal_grid = no_animation
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


class SpinAnimationTests(unittest.IsolatedAsyncioTestCase):
    async def test_spin_animation_uses_config_and_reveals_after_noise(self):
        game = Game.__new__(Game)
        game._render = AsyncMock()
        cfg = {
            "spin_frames": 2,
            "spin_delay": 0.25,
            "stop_delay": 0.5,
            "last_stop_delay": 1.0,
            "label": "🎰",
        }
        symbols = ["A", "B", "C", "D", "E"]

        with patch("game.random.choice", return_value="🎲"), patch(
            "game.asyncio.sleep", new=AsyncMock()
        ) as sleep:
            await game._anim_spin(None, "test", 10, cfg, symbols)

        self.assertEqual(game._render.await_count, cfg["spin_frames"] + 5)
        first_frame = game._render.await_args_list[0].args[3]
        self.assertEqual(first_frame, "🎲 | 🎲 | 🎲 | 🎲 | 🎲")
        final_frame = game._render.await_args_list[-1].args[3]
        self.assertEqual(final_frame, "A | B | C | D | E")
        self.assertEqual(
            [0.25, 0.25, 0.5, 0.5, 0.5, 0.5, 1.0],
            [call.args[0] for call in sleep.await_args_list],
        )


if __name__ == "__main__":
    unittest.main()
