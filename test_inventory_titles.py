import unittest
from unittest.mock import AsyncMock

from inventory import Inventory


class FakeDB:
    def __init__(self, level=0, owned_items=()):
        self.level = level
        self.owned_items = set(owned_items)
        self.title = "🎲 Новичок"
        self.selected = []

    def get_user(self, user_id):
        return {"level": self.level}

    def get_title(self, user_id):
        return self.title

    def has_item(self, user_id, item_id):
        return int(item_id in self.owned_items)

    def set_title(self, user_id, name):
        self.selected.append((user_id, name))
        self.title = name


class FakeQuery:
    def __init__(self, user_id=42, data=""):
        self.from_user = type("User", (), {"id": user_id})()
        self.data = data
        self.answer = AsyncMock()
        self.message = type("Message", (), {"edit_text": AsyncMock()})()


class InventoryTitleTests(unittest.IsolatedAsyncioTestCase):
    def make_inventory(self, level=0, owned_items=()):
        inventory = Inventory.__new__(Inventory)
        inventory.brain = type(
            "Brain", (), {"db": FakeDB(level, owned_items)}
        )()
        return inventory

    async def test_titles_screen_lists_progression_and_purchase_sections(self):
        from cosmetics import TITLES

        inventory = self.make_inventory(level=5, owned_items={100})
        query = FakeQuery()

        await inventory.cb_titles(query)

        text = query.message.edit_text.await_args.args[0]
        keyboard = query.message.edit_text.await_args.kwargs["reply_markup"]
        rows = keyboard.inline_keyboard
        buttons = [button for row in rows for button in row]
        callbacks = [button.callback_data for button in buttons]
        labels = [button.text for button in buttons]
        self.assertIn("🏆 <b>За уровень</b>", text)
        self.assertIn("🛒 <b>Купленные</b>", text)
        self.assertIn("inv_title_pick_🎲 Новичок", callbacks)
        self.assertIn("inv_title_pick_🍀 Везунчик", callbacks)
        self.assertIn("inv_title_pick_🧓 Старичок", callbacks)
        self.assertIn("🔒 💎 Богач (с 25 ур.)", labels)
        self.assertIn("🔒 🍀 Клевер", labels)
        self.assertTrue(all(
            f"inv_title_pick_{title['name']}" not in callbacks
            for key, title in TITLES.items()
            if key != "old"
        ))
        self.assertEqual(rows[-3][0].callback_data, "inv")
        self.assertEqual(rows[-2][0].callback_data, "play")
        self.assertEqual(rows[-1][0].callback_data, "menu")

    async def test_level_title_selection_checks_level(self):
        inventory = self.make_inventory(level=4)
        inventory.cb_titles = AsyncMock()
        query = FakeQuery(data="inv_title_pick_🍀 Везунчик")

        await inventory.cb_title_pick(query)

        self.assertEqual(inventory.brain.db.selected, [])
        query.answer.assert_awaited_once_with(
            "🔒 Нужен уровень 5",
            show_alert=True,
        )

    async def test_unowned_shop_title_is_rejected_and_owned_title_equips(self):
        from cosmetics import TITLES

        title = TITLES["clover"]
        inventory = self.make_inventory(level=0)
        inventory.cb_titles = AsyncMock()
        query = FakeQuery(data=f"inv_title_pick_{title['name']}")

        await inventory.cb_title_pick(query)

        self.assertEqual(inventory.brain.db.selected, [])
        query.answer.assert_awaited_once_with(
            "🔒 Титул ещё не куплен",
            show_alert=True,
        )

        inventory = self.make_inventory(
            level=0, owned_items={title["shop_id"]}
        )
        inventory.cb_titles = AsyncMock()
        query = FakeQuery(data=f"inv_title_pick_{title['name']}")

        await inventory.cb_title_pick(query)

        self.assertEqual(
            inventory.brain.db.selected,
            [(42, title["name"])],
        )
        inventory.cb_titles.assert_awaited_once_with(query)

    async def test_unknown_title_is_rejected(self):
        inventory = self.make_inventory()
        inventory.cb_titles = AsyncMock()
        query = FakeQuery(data="inv_title_pick_unknown")

        await inventory.cb_title_pick(query)

        query.answer.assert_awaited_once_with(
            "Титул не найден",
            show_alert=True,
        )


if __name__ == "__main__":
    unittest.main()
