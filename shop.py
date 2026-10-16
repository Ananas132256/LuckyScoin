import time
from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from cosmetics import RARITY_EMOJI
from utils import is_current_screen, nav_footer, safe_answer, with_hero

SHOP_ENABLED = True

CATEGORY_NAMES = {
    "title": "🏷 Титулы",
    "badge": "🎖 Медали",
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
        # ВАЖНО: обработчик "inv" убран — теперь им занимается Inventory
        # dp.callback_query(F.data == "inv")(self.cb_inventory)
        dp.callback_query(F.data.startswith("shop_cat_"))(self.cb_cat)
        dp.callback_query(F.data.startswith("shop_buy_"))(self.cb_buy)
        dp.callback_query(F.data == "claim_old_title")(self.cb_claim_old)

    def main_kb(self, items, gift_active=False):
        categories = {item[4] for item in items}
        buttons = (
            [[InlineKeyboardButton(
                text="🎁 Забрать «Старичка»",
                callback_data="claim_old_title",
            )]]
            if gift_active else []
        )
        buttons.extend([
            [InlineKeyboardButton(
                text=CATEGORY_NAMES.get(category, category),
                callback_data=f"shop_cat_{category}"
            )]
            for category in ("title", "badge")
            if category in categories
        ])
        buttons.extend(
            [InlineKeyboardButton(text=CATEGORY_NAMES.get(category, category),
                                  callback_data=f"shop_cat_{category}")]
            for category in sorted(categories - {"title", "badge"})
        )
        buttons.extend(nav_footer("shop"))
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def cb_shop(self, query: CallbackQuery, answer_query=True):
        if is_current_screen(query, "shop"):
            return await safe_answer(query, "Уже здесь")
        user_id = query.from_user.id
        user = self.brain.db.get_user(user_id)
        if not SHOP_ENABLED:
            buttons = []
            buttons.extend(nav_footer("shop"))
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            text = (
                "🛒 <b>Магазин временно недоступен</b>\n\n"
                "Мы обновляем ассортимент и улучшаем систему покупок.\n"
                "Скоро вернёмся с новыми предметами! 🎁\n\n"
                "<i>Следи за новостями в боте.</i>"
            )
            text = with_hero(text, user)
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
            try:
                await query.answer("🛒 Магазин обновляется", show_alert=True)
            except Exception:
                pass
            return

        if answer_query:
            await safe_answer(query)
        sc = self.brain.db.get_balance(user_id, "sc")
        items = self.brain.db.get_shop_items()
        import time as _t
        from config import UPDATE_GIFT_TITLE_ID
        from cosmetics import TITLES

        window_until = int(self.brain.db.get_flag(
            "old_title_window_until", "0"
        ))
        gift_active = (
            window_until > int(_t.time())
            and UPDATE_GIFT_TITLE_ID in TITLES
        )

        next_refresh = self.brain.db.get_shop_next_refresh()
        seconds_left = max(0, next_refresh - int(time.time()))
        timer = _format_time_left(seconds_left)

        body = (
            f"🛒 <b>Магазин LuckyScoin</b>\n\n"
            f"💰 Твой баланс: <b>{sc} SC</b>\n"
            f"⏳ Обновление ассортимента через: <b>{timer}</b>\n\n"
            f"Ассортимент меняется каждые 6 часов!\n"
            f"Выбери категорию:"
        )
        if gift_active:
            body = (
                "🎁 <b>Обновление 1.0.0 — подарок!</b>\n"
                f"🧓 <b>Старичок</b> — бесплатный титул, осталось "
                f"<b>{_format_time_left(window_until - int(_t.time()))}</b>\n\n"
                + body
            )
        text = with_hero(body, user)
        try:
            await query.message.edit_text(
                text,
                reply_markup=self.main_kb(items, gift_active=gift_active),
                parse_mode="HTML",
            )
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
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")],
            ] + nav_footer("shop"))
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
            mark = f" ✅ ×{owned}" if owned > 0 else ""
            lines.append(f"{RARITY_EMOJI.get(rarity, '⚪')} {name} — {price} SC{mark}")
            if owned == 0:
                buttons.append([InlineKeyboardButton(
                    text=f"Купить {name} ({price} SC)",
                    callback_data=f"shop_buy_{item_id}"
                )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")])
        buttons.extend(nav_footer("shop"))

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
            category = item["category"] if item else "unknown"
            event_type = "buy_title" if category == "title" else "buy_badge"
            payload = (
                f"{item['name']}|{item['price_sc']}"
                if item else str(item_id)
            )
            self.brain.db.log_event(user_id, "", event_type, payload)
            if item:
                query.data = f"shop_cat_{item['category']}"
                await self.cb_cat(query)

    async def cb_claim_old(self, query: CallbackQuery):
        import time as _t
        from config import UPDATE_GIFT_TITLE_ID
        from cosmetics import TITLES

        title = TITLES.get(UPDATE_GIFT_TITLE_ID)
        if not title:
            return await safe_answer(
                query, "Подарок недоступен.", show_alert=True
            )

        window_until = int(self.brain.db.get_flag(
            "old_title_window_until", "0"
        ))
        if int(_t.time()) >= window_until:
            return await safe_answer(
                query, "⌛ Окно подарочного титула закрылось.",
                show_alert=True,
            )

        user_id = query.from_user.id
        shop_id = title["shop_id"]
        if self.brain.db.has_item(user_id, shop_id) > 0:
            return await safe_answer(
                query, "🎁 У тебя уже есть этот титул.",
                show_alert=True,
            )

        self.brain.db.add_item(user_id, shop_id, 1)
        self.brain.db.log_event(
            user_id,
            query.from_user.username or "",
            "buy_title",
            f"{title['name']}|0",
        )
        await safe_answer(
            query,
            "🎉 Титул «Старичок» в инвентаре! Надень его, когда "
            "захочешь — он навсегда.",
            show_alert=True,
        )
        await self.cb_shop(query, answer_query=False)