import time
from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


RARITY_EMOJI = {
    "common":    "⚪",
    "rare":      "🔵",
    "epic":      "🟣",
    "legendary": "🟡",
}

CATEGORY_NAMES = {
    "title": "🏷 Титулы",
    "badge": "🎖 Значки",
}


def _format_time_left(seconds):
    if seconds <= 0:
        return "сейчас"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"


class Shop:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "shop")(self.cb_shop)
        dp.callback_query(F.data == "inv")(self.cb_inventory)
        dp.callback_query(F.data.startswith("shop_cat_"))(self.cb_cat)
        dp.callback_query(F.data.startswith("shop_buy_"))(self.cb_buy)

    def main_kb(self):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏷 Титулы", callback_data="shop_cat_title")],
            [InlineKeyboardButton(text="🎖 Значки", callback_data="shop_cat_badge")],
            [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inv")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
        ])

    async def cb_shop(self, query: CallbackQuery):
        user_id = query.from_user.id
        sc = self.brain.db.get_balance(user_id, "sc")

        next_refresh = self.brain.db.get_shop_next_refresh()
        seconds_left = max(0, next_refresh - int(time.time()))
        timer = _format_time_left(seconds_left)

        text = (
            f"🛒 **Магазин LuckyScoin**\n\n"
            f"💰 Твой баланс: **{sc} SC**\n"
            f"⏳ Обновление ассортимента через: **{timer}**\n\n"
            f"Ассортимент меняется каждые 6 часов!\n"
            f"Выбери категорию:"
        )
        try:
            await query.message.edit_text(text, reply_markup=self.main_kb(), parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    async def cb_cat(self, query: CallbackQuery):
        cat = query.data.replace("shop_cat_", "")

        # Товары этой категории из текущей ротации
        stock = self.brain.db.get_shop_items()
        items = [row for row in stock if row[4] == cat]  # row = (id, name, price, rarity, category)

        if not items:
            text = (
                f"🛒 **{CATEGORY_NAMES.get(cat, cat)}**\n\n"
                "Сейчас в этой категории нет товаров. Загляни после следующего обновления!"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")]
            ])
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass
            return await query.answer()

        user_id = query.from_user.id
        sc = self.brain.db.get_balance(user_id, "sc")

        next_refresh = self.brain.db.get_shop_next_refresh()
        seconds_left = max(0, next_refresh - int(time.time()))
        timer = _format_time_left(seconds_left)

        lines = [
            f"🛒 **{CATEGORY_NAMES.get(cat, cat)}**\n",
            f"💰 Баланс: **{sc} SC**",
            f"⏳ Обновление через: **{timer}**\n",
        ]
        buttons = []
        for item_id, name, price, rarity, _ in items:
            owned = self.brain.db.has_item(user_id, item_id)
            mark = " ✅" if owned > 0 else ""
            lines.append(f"{RARITY_EMOJI.get(rarity, '⚪')} {name} — {price} SC{mark}")
            if owned == 0:
                buttons.append([InlineKeyboardButton(
                    text=f"Купить {name} ({price} SC)",
                    callback_data=f"shop_buy_{item_id}"
                )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    async def cb_buy(self, query: CallbackQuery):
        try:
            item_id = int(query.data.replace("shop_buy_", ""))
        except ValueError:
            return await query.answer("❌ Ошибка", show_alert=True)

        user_id = query.from_user.id
        ok, msg = self.brain.db.buy_item(user_id, item_id)
        await query.answer(msg, show_alert=True)

        if ok:
            item = self.brain.db.get_item(item_id)
            if item:
                query.data = f"shop_cat_{item['category']}"
                await self.cb_cat(query)

    async def cb_inventory(self, query: CallbackQuery):
        user_id = query.from_user.id
        inv = self.brain.db.get_inventory(user_id)
        if not inv:
            text = "🎒 **Инвентарь**\n\nПока пусто. Купи что-нибудь в магазине!"
        else:
            lines = ["🎒 **Инвентарь**\n"]
            current_cat = None
            for item_id, qty, name, rarity, cat in inv:
                if cat != current_cat:
                    lines.append(f"\n**{CATEGORY_NAMES.get(cat, cat)}:**")
                    current_cat = cat
                qty_str = f" x{qty}" if qty > 1 else ""
                lines.append(f"{RARITY_EMOJI.get(rarity, '⚪')} {name}{qty_str}")
            text = "\n".join(lines)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 В магазин", callback_data="shop")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()