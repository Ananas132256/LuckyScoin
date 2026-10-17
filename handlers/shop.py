import html
import time
import math
from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message,
)
from content.catalog import BADGES, RARITY_EMOJI, TITLES, describe_effect_dict
from utils import format_sc, is_current_screen, nav_footer, safe_answer, with_hero

SHOP_ENABLED = True

CATEGORY_NAMES = {
    "title": "🏷 Титулы",
    "badge": "🎖 Медали",
}


class ExchangeStates(StatesGroup):
    waiting_amount = State()


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
        self._exchange_cooldowns = {}

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "shop")(self.cb_shop)
        # ВАЖНО: обработчик "inv" убран — теперь им занимается Inventory
        # dp.callback_query(F.data == "inv")(self.cb_inventory)
        dp.callback_query(F.data.startswith("shop_cat_"))(self.cb_cat)
        dp.callback_query(F.data.startswith("shop_buy_confirm_"))(self.cb_buy_confirm)
        dp.callback_query(F.data.startswith("shop_buy_"))(self.cb_buy_preview)
        dp.callback_query(F.data == "shop_exchange")(self.cb_exchange_menu)
        dp.callback_query(F.data == "shop_exchange_lc")(
            self.cb_exchange_lc_start
        )
        dp.callback_query(F.data == "shop_exchange_sc")(
            self.cb_exchange_sc_start
        )
        dp.callback_query(F.data == "shop_exchange_cancel")(
            self.cb_exchange_cancel
        )
        dp.message(ExchangeStates.waiting_amount)(self.on_exchange_amount)
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
        buttons.append([InlineKeyboardButton(
            text="💱 Обмен",
            callback_data="shop_exchange",
        )])
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
        from content.catalog import TITLES

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
            f"💰 Твой баланс: <b>{format_sc(sc)} SC</b>\n"
            f"⏳ Обновление ассортимента через: <b>{timer}</b>\n\n"
            f"Ассортимент меняется каждые 6 часов!\n"
            f"Выбери категорию:"
        )
        from config import HALLOWEEN_END, HALLOWEEN_START
        from utils import in_date_range
        if in_date_range(HALLOWEEN_START, HALLOWEEN_END):
            body = (
                "🎃 <b>Хеллоуин 2026!</b>\n"
                "Доступно до <b>1 ноября</b>. Успей забрать 🎃 Джека и "
                "🌀 Круговорот.\n\n" + body
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

    async def cb_cat(self, query: CallbackQuery, answer_query=True):
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
            if answer_query:
                await query.answer()
            return

        user_id = query.from_user.id
        sc = self.brain.db.get_balance(user_id, "sc")

        next_refresh = self.brain.db.get_shop_next_refresh()
        seconds_left = max(0, next_refresh - int(time.time()))
        timer = _format_time_left(seconds_left)

        lines = [
            f"🛒 <b>{CATEGORY_NAMES.get(cat, cat)}</b>\n",
            f"💰 Баланс: <b>{format_sc(sc)} SC</b>",
            f"⏳ Обновление через: <b>{timer}</b>\n",
        ]
        buttons = []
        for item_id, name, price, rarity, _ in items:
            owned = self.brain.db.has_item(user_id, item_id)
            mark = f" ✅ ×{owned}" if owned > 0 else ""
            lines.append(
                f"{RARITY_EMOJI.get(rarity, '⚪')} {name} — "
                f"{format_sc(price)} SC{mark}"
            )
            if owned == 0:
                buttons.append([InlineKeyboardButton(
                    text=f"Купить {name} ({format_sc(price)} SC)",
                    callback_data=f"shop_buy_{item_id}"
                )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")])
        buttons.extend(nav_footer("shop"))

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        if answer_query:
            await query.answer()

    async def cb_buy_preview(self, query: CallbackQuery):
        try:
            item_id = int(query.data.replace("shop_buy_", ""))
        except ValueError:
            return await query.answer("❌ Ошибка", show_alert=True)

        user_id = query.from_user.id
        item = self.brain.db.get_item(item_id)
        if not item:
            return await safe_answer(query, "❌ Предмет не найден.", show_alert=True)

        category = item["category"]
        details = TITLES.get(next(
            (key for key, value in TITLES.items()
             if value["shop_id"] == item_id),
            "",
        ))
        badge = BADGES.get(next(
            (key for key, value in BADGES.items()
             if value["shop_id"] == item_id),
            "",
        ))
        details = details or badge or {}

        desc = html.escape(str(details.get("desc", "Описание недоступно.")))
        text_lines = [
            f"{RARITY_EMOJI.get(item['rarity'], '⚪')} "
            f"<b>{html.escape(str(item['name']))}</b>\n",
            f"{desc}",
        ]
        if category == "badge" and badge:
            try:
                from content.effects import get_badge_effects
                stats = self.brain.db.get_extended_stats(user_id)
                effects = get_badge_effects(badge, stats)
                text_lines.append(f"\n✨ Эффект: {describe_effect_dict(effects)}")
            except Exception as error:
                print(f"⚠️ Не удалось рассчитать эффект медали: {error}")
                text_lines.append("\n✨ Эффект: описание недоступно")
            hp = badge.get("hp", "—")
            hp_text = "∞" if hp == "inf" else str(hp)
            break_on = ", ".join(map(str, badge.get("break_on", []))) or "—"
            text_lines.extend([
                f"❤️ HP: {hp_text}",
                f"💥 Сгорает при: {break_on}",
            ])
        else:
            text_lines.extend([
                f"\n✨ Эффект: {describe_effect_dict({})}",
                "❤️ HP: —",
                "💥 Сгорает при: —",
            ])
        text_lines.append(f"\n💰 Цена: <b>{format_sc(item['price_sc'])} SC</b>")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Купить",
                callback_data=f"shop_buy_confirm_{item_id}",
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=f"shop_cat_{category}",
            )],
        ])
        await query.message.edit_text(
            "\n".join(text_lines),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await safe_answer(query)

    async def cb_buy_confirm(self, query: CallbackQuery):
        try:
            item_id = int(query.data.replace("shop_buy_confirm_", ""))
        except ValueError:
            return await query.answer("❌ Ошибка", show_alert=True)

        user_id = query.from_user.id
        item = self.brain.db.get_item(item_id)
        ok, msg = self.brain.db.buy_item(user_id, item_id)
        await query.answer(msg, show_alert=True)

        if ok and item:
            category = item["category"]
            event_type = "buy_title" if category == "title" else "buy_badge"
            payload = f"{item['name']}|{item['price_sc']}"
            self.brain.db.log_event(user_id, "", event_type, payload)
            badge = next(
                (
                    cosmetic for cosmetic in BADGES.values()
                    if cosmetic["shop_id"] == item_id
                ),
                None,
            )
            if badge and badge.get("halloween"):
                from config import HALLOWEEN_END, HALLOWEEN_START
                from utils import in_date_range
                title = TITLES.get("halloween_2026")
                if (
                    title
                    and in_date_range(HALLOWEEN_START, HALLOWEEN_END)
                    and self.brain.db.has_item(user_id, title["shop_id"]) == 0
                ):
                    self.brain.db.add_item(user_id, title["shop_id"], 1)
                    self.brain.db.set_title(user_id, title["name"])
        if item:
            query.data = f"shop_cat_{item['category']}"
            await self.cb_cat(query, answer_query=False)

    async def cb_exchange_menu(self, query: CallbackQuery, answer_query=True):
        user_id = query.from_user.id
        lc_to_sc = self.brain.db.get_exchange_rate("lc_to_sc")
        sc_to_lc = self.brain.db.get_exchange_rate("sc_to_lc")
        text = (
            "💱 <b>Обмен валют</b>\n\n"
            f"💰 SC: <b>{format_sc(self.brain.db.get_balance(user_id, 'sc'))}</b>\n"
            f"🍀 LC: <b>{format_sc(self.brain.db.get_balance(user_id, 'lc'))}</b>\n\n"
            f"Курс LC → SC: <b>{format_sc(lc_to_sc)} LC = 1 SC</b>\n"
            f"Курс SC → LC: <b>1 SC = {format_sc(sc_to_lc)} LC</b>\n\n"
            "Выбери направление:"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💱 LC → SC", callback_data="shop_exchange_lc")],
            [InlineKeyboardButton(text="💱 SC → LC", callback_data="shop_exchange_sc")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")],
        ] + nav_footer("shop"))
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        if answer_query:
            await safe_answer(query)

    def _exchange_ready(self, user_id):
        now = time.time()
        cooldown_until = self._exchange_cooldowns.get(user_id, 0)
        if now < cooldown_until:
            return None, math.ceil(cooldown_until - now)
        return now, 0

    async def _start_exchange(self, query, state, direction):
        user_id = query.from_user.id
        now, remaining = self._exchange_ready(user_id)
        if now is None:
            return await safe_answer(
                query, f"⏳ Повтори обмен через {remaining} сек.", show_alert=True
            )
        rate = self.brain.db.get_exchange_rate(direction)
        if rate <= 0:
            return await safe_answer(query, "❌ Курс обмена недоступен.", show_alert=True)
        await state.set_state(ExchangeStates.waiting_amount)
        await state.update_data(direction=direction)
        currency = "LC" if direction == "lc_to_sc" else "SC"
        balance = self.brain.db.get_balance(user_id, currency.lower())
        rate_text = (
            f"{format_sc(rate)} LC за 1 SC"
            if direction == "lc_to_sc"
            else f"1 SC за {format_sc(rate)} LC"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="shop_exchange_cancel",
            )
        ]])
        await query.message.edit_text(
            f"💱 <b>Обмен валют</b>\n\n"
            f"Баланс: <b>{format_sc(balance)} {currency}</b>\n"
            f"Курс: <b>{rate_text}</b>\n\n"
            f"Введи количество {currency} для обмена. /cancel — отмена.",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await safe_answer(query)

    async def cb_exchange_lc_start(self, query: CallbackQuery, state: FSMContext):
        return await self._start_exchange(query, state, "lc_to_sc")

    async def cb_exchange_sc_start(self, query: CallbackQuery, state: FSMContext):
        return await self._start_exchange(query, state, "sc_to_lc")

    async def on_exchange_amount(self, message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if text.lower() == "/cancel":
            await state.clear()
            return await message.answer("Отменено.")
        try:
            amount = float(text.replace(",", "."))
        except ValueError:
            return await message.answer("Введи число.")
        if not math.isfinite(amount):
            return await message.answer("Введи число.")
        if amount <= 0:
            return await message.answer("Сумма должна быть > 0.")

        data = await state.get_data()
        direction = data.get("direction")
        if direction not in ("lc_to_sc", "sc_to_lc"):
            await state.clear()
            return await message.answer("❌ Направление обмена потеряно. Начни заново.")

        user_id = message.from_user.id
        db = self.brain.db
        rate = db.get_exchange_rate(direction)
        if rate <= 0:
            return await message.answer("❌ Курс обмена недоступен.")

        if direction == "lc_to_sc":
            if amount < rate:
                return await message.answer(
                    f"Минимум {format_sc(rate)} LC (= 1 SC)."
                )
            if db.get_balance(user_id, "lc") < amount:
                return await message.answer("Недостаточно LC.")
            if not db.subtract_balance_if_available(user_id, "lc", amount):
                return await message.answer("Недостаточно LC.")
            sc_gain = round(amount / rate, 2)
            db.add_balance(user_id, "sc", sc_gain)
            db.log_event(
                user_id, "", "exchange", f"lc_to_sc|{amount:g}|{sc_gain:g}"
            )
            await message.answer(
                f"💱 {amount:g} LC → <b>+{sc_gain:g} SC</b> "
                f"(курс {format_sc(rate)})",
                parse_mode="HTML",
            )
        else:
            if db.get_balance(user_id, "sc") < amount:
                return await message.answer("Недостаточно SC.")
            if not db.subtract_balance_if_available(user_id, "sc", amount):
                return await message.answer("Недостаточно SC.")
            lc_gain = int(round(amount * rate, 2))
            db.add_balance(user_id, "lc", lc_gain)
            db.log_event(
                user_id, "", "exchange", f"sc_to_lc|{amount:g}|{lc_gain}"
            )
            await message.answer(
                f"💱 {amount:g} SC → <b>+{lc_gain} LC</b> "
                f"(курс {format_sc(rate)})",
                parse_mode="HTML",
            )

        self._exchange_cooldowns[user_id] = time.time() + 60
        await state.clear()

    async def cb_exchange_cancel(self, query: CallbackQuery, state: FSMContext):
        await state.clear()
        await self.cb_exchange_menu(query, answer_query=False)
        await safe_answer(query)

    async def cb_claim_old(self, query: CallbackQuery):
        import time as _t
        from config import UPDATE_GIFT_TITLE_ID
        from content.catalog import TITLES

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