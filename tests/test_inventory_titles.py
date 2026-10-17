import unittest
from unittest.mock import AsyncMock

from handlers.inventory import Inventory


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

    async def test_titles_screen_paginates_five_titles_at_a_time(self):
        from content.catalog import TITLES

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
        self.assertIn("inv_title_pick_🎲 Новичок", callbacks)
        self.assertIn("inv_title_pick_🍀 Везунчик", callbacks)
        self.assertIn("🔒 💎 Богач (с 25 ур.)", labels)
        self.assertEqual(sum(
            button.callback_data.startswith("inv_title_pick_")
            for button in buttons
        ), 2)
        self.assertEqual(rows[-3][0].callback_data, "inv")
        self.assertEqual(rows[-2][0].callback_data, "play")
        self.assertEqual(rows[-1][0].callback_data, "menu")

        page_query = FakeQuery(data="inv_titles_page_1")
        await inventory.cb_titles_page(page_query)
        page_text = page_query.message.edit_text.await_args.args[0]
        page_keyboard = page_query.message.edit_text.await_args.kwargs["reply_markup"]
        page_buttons = [
            button
            for row in page_keyboard.inline_keyboard
            for button in row
        ]
        page_callbacks = [button.callback_data for button in page_buttons]
        self.assertIn("🛒 <b>Купленные</b>", page_text)
        self.assertIn("🔒 🍀 Клевер", [button.text for button in page_buttons])
        self.assertEqual(
            page_keyboard.inline_keyboard[-4][1].text,
            "2/3",
        )
        self.assertTrue(all(
            f"inv_title_pick_{title['name']}" not in page_callbacks
            for key, title in TITLES.items()
            if key != "old"
        ))

        last_page_query = FakeQuery(data="inv_titles_page_2")
        await inventory.cb_titles_page(last_page_query)
        last_page_keyboard = last_page_query.message.edit_text.await_args.kwargs["reply_markup"]
        last_page_callbacks = [
            button.callback_data
            for row in last_page_keyboard.inline_keyboard
            for button in row
        ]
        self.assertIn("inv_title_pick_🧓 Старичок", last_page_callbacks)

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
        from content.catalog import TITLES

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
        inventory.cb_titles.assert_awaited_once_with(query, page=1)

    async def test_unknown_title_is_rejected(self):
        inventory = self.make_inventory()
        inventory.cb_titles = AsyncMock()
        query = FakeQuery(data="inv_title_pick_unknown")

        await inventory.cb_title_pick(query)

        query.answer.assert_awaited_once_with(
            "Титул не найден",
            show_alert=True,
        )

    async def test_badge_pick_rejects_level_locked_slot(self):
        from content.catalog import BADGES

        inventory = self.make_inventory(level=5)
        inventory.brain.db.get_rooms = lambda user_id: []
        query = FakeQuery(
            data=f"inv_badge_pick_3_{next(iter(BADGES))}"
        )

        await inventory.cb_badge_pick(query)

        query.answer.assert_awaited_once_with(
            "Ячейка заблокирована.",
            show_alert=True,
        )


if __name__ == "__main__":
    unittest.main()
