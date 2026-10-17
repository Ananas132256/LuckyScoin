import unittest
from unittest.mock import AsyncMock, patch

from handlers.daily import Daily


class FakeDB:
    def __init__(self):
        self.state = {
            "streak": 2,
            "last_claim": 0,
            "wheel_ts": 0,
            "can_claim": True,
            "next_claim_at": 0,
            "streak_lost": False,
        }
        self.flags = {}
        self.claims = []
        self.balances = []
        self.events = []
        self.wheel_spins = []

    def get_daily_state(self, user_id):
        return dict(self.state)

    def claim_daily(self, user_id, streak):
        self.claims.append((user_id, streak))
        self.state.update(
            streak=streak,
            last_claim=100_000,
            can_claim=False,
            next_claim_at=100_000 + 86_400,
        )
        return True

    def add_balance(self, user_id, currency, amount):
        self.balances.append((user_id, currency, amount))

    def log_event(self, *event):
        self.events.append(event)

    def get_flag(self, key, default=None):
        return self.flags.get(key, default)

    def set_flag(self, key, value):
        self.flags[key] = str(value)

    def record_wheel_spin(self, user_id):
        self.wheel_spins.append(user_id)


class FakeMessage:
    def __init__(self):
        self.edits = []
        self.edit_text = AsyncMock(side_effect=self._edit_text)

    def _edit_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


class FakeQuery:
    def __init__(self, user_id=42):
        self.from_user = type("User", (), {"id": user_id})()
        self.message = FakeMessage()
        self.answer = AsyncMock()


class DailyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = FakeDB()
        self.brain = type("Brain", (), {"db": self.db})()
        self.daily = Daily(self.brain)
        self.query = FakeQuery()

    async def test_claim_awards_lc_and_records_seventh_day_wheel(self):
        self.db.state["streak"] = 6

        with patch("handlers.daily.time.time", return_value=100_000), patch(
            "handlers.daily.random.random", return_value=0.99
        ), patch("handlers.daily.asyncio.sleep", new=AsyncMock()):
            await self.daily.cb_claim(self.query)

        self.assertEqual(self.db.claims, [(42, 7)])
        self.assertEqual(self.db.balances, [(42, "lc", 1_500)])
        self.assertEqual(
            self.db.events,
            [(42, "", "daily_claim", "7|1500")],
        )
        self.assertEqual(self.db.flags["daily_wheel_until:42"], "100300")
        keyboard = self.query.message.edit_text.call_args.kwargs["reply_markup"]
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]
        self.assertIn("daily_wheel", callbacks)
        self.assertNotIn("daily_claim", callbacks)

    async def test_claim_refuses_when_daily_state_is_not_claimable(self):
        self.db.state["can_claim"] = False

        await self.daily.cb_claim(self.query)

        self.assertEqual(self.db.claims, [])
        self.assertEqual(self.db.balances, [])
        self.assertEqual(self.query.message.edit_text.await_count, 0)
        self.query.answer.assert_awaited_once_with(
            "⏳ Уже получено. Возвращайся позже.",
            show_alert=True,
        )

    async def test_wheel_spin_requires_unexpired_grant_and_awards_lc(self):
        self.db.flags["daily_wheel_until:42"] = "100300"
        prize = {
            "symbol": "🥉",
            "name": "Bronze",
            "chance": 35,
            "lc_amount": 100,
        }

        with patch("handlers.daily.time.time", return_value=100_000), patch(
            "handlers.daily.random.choices", return_value=[prize]
        ), patch("handlers.daily.asyncio.sleep", new=AsyncMock()):
            await self.daily.cb_wheel_spin(self.query)

        self.assertEqual(self.db.flags["daily_wheel_until:42"], "0")
        self.assertEqual(self.db.wheel_spins, [42])
        self.assertEqual(self.db.balances, [(42, "lc", 100)])
        self.assertEqual(
            self.db.events,
            [(42, "", "daily_wheel", "Bronze|100")],
        )
        self.assertEqual(self.query.message.edit_text.await_count, 4)
        final_text = self.query.message.edit_text.await_args.args[0]
        self.assertIn("Бронза", final_text)

    async def test_expired_wheel_grant_is_rejected(self):
        self.db.flags["daily_wheel_until:42"] = "100000"

        with patch("handlers.daily.time.time", return_value=100_000):
            await self.daily.cb_wheel_spin(self.query)

        self.assertEqual(self.db.balances, [])
        self.assertEqual(self.query.message.edit_text.await_count, 0)
        self.query.answer.assert_awaited_once_with(
            "Колесо недоступно.",
            show_alert=True,
        )

    async def test_missed_streak_resets_to_day_one(self):
        self.db.state.update(streak=6, streak_lost=True)

        with patch("handlers.daily.time.time", return_value=100_000), patch(
            "handlers.daily.random.random", return_value=0.99
        ), patch("handlers.daily.asyncio.sleep", new=AsyncMock()):
            await self.daily.cb_claim(self.query)

        self.assertEqual(self.db.claims, [(42, 1)])
        self.assertEqual(self.db.balances, [(42, "lc", 50)])
        self.assertEqual(
            self.db.events,
            [(42, "", "daily_claim", "1|50")],
        )

    async def test_regular_wheel_roll_obeys_chance_and_cooldown(self):
        self.db.state["streak"] = 2
        self.db.state["wheel_ts"] = 100_000 - 12 * 3600

        with patch("handlers.daily.time.time", return_value=100_000), patch(
            "handlers.daily.random.random", return_value=0.14
        ), patch("handlers.daily.asyncio.sleep", new=AsyncMock()):
            await self.daily.cb_claim(self.query)

        self.assertEqual(self.db.claims, [(42, 3)])
        self.assertEqual(self.db.flags["daily_wheel_until:42"], "100300")

    async def test_regular_wheel_roll_is_suppressed_during_cooldown(self):
        self.db.state["streak"] = 2
        self.db.state["wheel_ts"] = 100_000 - 12 * 3600 + 1

        with patch("handlers.daily.time.time", return_value=100_000), patch(
            "handlers.daily.random.random", return_value=0.01
        ), patch("handlers.daily.asyncio.sleep", new=AsyncMock()):
            await self.daily.cb_claim(self.query)

        self.assertEqual(self.db.flags["daily_wheel_until:42"], "0")


if __name__ == "__main__":
    unittest.main()
