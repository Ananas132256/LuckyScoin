import unittest
from unittest.mock import patch

from notifier import _tick


class FakeDB:
    CASINO_MAX_HOURS = 8

    def __init__(self):
        self.flags = {}
        self.user_ids = [1, 2, 3, 4]
        self.states = {
            1: {"can_claim": True},
            2: {"can_claim": True},
            3: {"can_claim": False},
            4: {"can_claim": True},
        }
        self.maintenance_enabled = False

    def get_maintenance(self):
        return {"enabled": self.maintenance_enabled}

    def get_users_with_casino(self):
        return []

    def get_all_user_ids(self):
        return self.user_ids

    def get_daily_state(self, user_id):
        return self.states[user_id]

    def get_flag(self, key, default=None):
        return self.flags.get(key, default)

    def set_flag(self, key, value):
        self.flags[key] = value


class FakeBot:
    def __init__(self, failing_user=None):
        self.failing_user = failing_user
        self.messages = []

    async def send_message(self, user_id, text):
        if user_id == self.failing_user:
            raise RuntimeError("send failed")
        self.messages.append((user_id, text))


class FakeBrain:
    def __init__(self, failing_user=None):
        self.db = FakeDB()
        self.bot = FakeBot(failing_user=failing_user)


class DailyNudgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_nudges_eligible_non_admin_users_and_sets_cooldown(self):
        brain = FakeBrain()
        brain.db.flags["daily_nudge_ts:2"] = str(1_000_000 - 20 * 3600 + 1)

        with patch("notifier.time.time", return_value=1_000_000), patch(
            "notifier.is_admin", side_effect=lambda uid, db: uid == 1
        ):
            await _tick(brain)

        self.assertEqual(
            brain.bot.messages,
            [(4, "🎁 Твоя ежедневная награда готова!\n"
                 "Заходи и забери LC — серия растёт каждый день.")],
        )
        self.assertEqual(brain.db.flags["daily_nudge_ts:4"], "1000000")

    async def test_maintenance_skips_daily_nudges(self):
        brain = FakeBrain()
        brain.db.maintenance_enabled = True

        with patch("notifier.is_admin") as is_admin:
            await _tick(brain)

        self.assertEqual(brain.bot.messages, [])
        is_admin.assert_not_called()

    async def test_failed_send_does_not_stop_other_users(self):
        brain = FakeBrain(failing_user=2)

        with patch("notifier.time.time", return_value=1_000_000), patch(
            "notifier.is_admin", return_value=False
        ):
            await _tick(brain)

        self.assertEqual([uid for uid, _ in brain.bot.messages], [1, 4])
        self.assertNotIn("daily_nudge_ts:2", brain.db.flags)


if __name__ == "__main__":
    unittest.main()
