import time
from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

SHOP_ENABLED = True

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


async def safe_answer(query, *args, **kwargs):
    try:
        await query.answer(*args, **kwargs)
    except Exception:
        pass


class Shop:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "shop")(self.cb_shop)
        # ВАЖНО: обработчик "inv" убран — теперь им занимается Inventory
        # dp.callback_query(F.data == "inv")(self.cb_inventory)
        dp.callback_query(F.data.startswith("shop_cat_"))(self.cb_cat)
        dp.callback_query(F.data.startswith("shop_buy_"))(self.cb_buy)

    def main_kb(self):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏷 Титулы", callback_data="shop_cat_title")],
            [InlineKeyboardButton(text="🎖 Значки", callback_data="shop_cat_badge")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
        ])

    async def cb_shop(self, query: CallbackQuery):
        if not SHOP_ENABLED:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]
            ])
            text = (
                "🛒 <b>Магазин временно недоступен</b>\n\n"
                "Мы обновляем ассортимент и улучшаем систему покупок.\n"
                "Скоро вернёмся с новыми предметами! 🎁\n\n"
                "<i>Следи за новостями в боте.</i>"
            )
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
            try:
                await query.answer("🛒 Магазин обновляется", show_alert=True)
            except Exception:
                pass
            return

        await safe_answer(query)
        user_id = query.from_user.id
        sc = self.brain.db.get_balance(user_id, "sc")

        next_refresh = self.brain.db.get_shop_next_refresh()
        seconds_left = max(0, next_refresh - int(time.time()))
        timer = _format_time_left(seconds_left)

        text = (
            f"🛒 <b>Магазин LuckyScoin</b>\n\n"
            f"💰 Твой баланс: <b>{sc} SC</b>\n"
            f"⏳ Обновление ассортимента через: <b>{timer}</b>\n\n"
            f"Ассортимент меняется каждые 6 часов!\n"
            f"Выбери категорию:"
        )
        try:
            await query.message.edit_text(text, reply_markup=self.main_kb(), parse_mode="HTML")
        except Exception:
            pass

    async def cb_cat(self, query: CallbackQuery):
        cat = query.data.replace("shop_cat_", "")

        stock = self.brain.db.get_shop_items()
        items = [row for row in stock if row[4] == cat]

        if not items:
            text = (
                f"🛒 <b>{CATEGORY_NAMES.get(cat, cat)}</b>\n\n"
                "Сейчас в этой категории нет товаров. Загляни после следующего обновления!"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")]
            ])
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
            return await query.answer()

        user_id = query.from_user.id
        sc = self.brain.db.get_balance(user_id, "sc")

        next_refresh = self.brain.db.get_shop_next_refresh()
        seconds_left = max(0, next_refresh - int(time.time()))
        timer = _format_time_left(seconds_left)

        lines = [
            f"🛒 <b>{CATEGORY_NAMES.get(cat, cat)}</b>\n",
            f"💰 Баланс: <b>{sc} SC</b>",
            f"⏳ Обновление через: <b>{timer}</b>\n",
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
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
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