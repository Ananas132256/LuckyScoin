import asyncio
import unittest

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


if __name__ == "__main__":
    unittest.main()
