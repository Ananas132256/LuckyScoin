"""
Player-to-player trade.

Economy note: the SC fee (TRADE_FEE_BURN_PERCENT) is intentionally
BURNED, not credited to any user. It acts as an SC sink to keep
inflation under control. Do not "fix" this as a bug without
consulting the balance team.
"""

import html
import time
from decimal import Decimal, InvalidOperation

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from utils import format_sc, safe_answer


TRADE_FEE_BURN_PERCENT = 5
TRADE_TTL_SECONDS = 24 * 3600


class Trade:
    def __init__(self, brain):
        self.brain = brain
        self.pending = {}   # {trade_id: {...}}
        self.counter = 0

    async def _prune_expired(self):
        now = time.time()
        expired = [
            trade_id
            for trade_id, trade in self.pending.items()
            if now - trade["ts"] > TRADE_TTL_SECONDS
        ]
        for trade_id in expired:
            trade = self.pending.pop(trade_id)
            for user_id in (trade["from_id"], trade["to_id"]):
                try:
                    await self.brain.bot.send_message(
                        user_id,
                        f"⌛ Предложение трейда #{trade_id} истекло.",
                    )
                except Exception as error:
                    print(
                        f"Ошибка уведомления об истечении трейда "
                        f"#{trade_id} для {user_id}: {error}"
                    )

    def register(self, dp: Dispatcher):
        dp.message(Command("trade"))(self.cmd_trade)
        dp.callback_query(F.data == "trade")(self.cb_trade_info)
        dp.callback_query(F.data == "trade_pick_badge")(self.cb_pick_badge)
        dp.callback_query(F.data.startswith("trade_select_badge_"))(self.cb_select_badge)
        dp.callback_query(F.data.startswith("trade_accept_"))(self.cb_accept)
        dp.callback_query(F.data.startswith("trade_decline_"))(self.cb_decline)

    def _badge(self, badge_id):
        from cosmetics import BADGES
        return BADGES.get(badge_id)

    def _parse_asset(self, value):
        if value.startswith("badge:"):
            badge_id = value[len("badge:"):]
            if not badge_id or not self._badge(badge_id):
                raise ValueError("Неизвестная медаль.")
            return {"type": "badge", "badge_id": badge_id}
        try:
            amount_decimal = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("Используй количество SC или badge:<ID>.") from error
        if not amount_decimal.is_finite() or amount_decimal <= 0:
            raise ValueError("Количество SC должно быть больше 0.")
        if amount_decimal != amount_decimal.quantize(Decimal("0.01")):
            raise ValueError("Количество SC укажи не более чем с двумя знаками.")
        return {"type": "sc", "amount": round(float(amount_decimal), 2)}

    def _asset_label(self, asset):
        if asset["type"] == "sc":
            return f"{format_sc(asset['amount'])} SC"
        badge = self._badge(asset["badge_id"])
        return f"медаль {badge['name']}"

    def _fee_for(self, asset):
        if asset["type"] != "sc":
            return 0
        return max(
            0.1,
            round(asset["amount"] * TRADE_FEE_BURN_PERCENT / 100, 2),
        )

    def _owns_badge(self, user_id, badge_id):
        return any(
            badge["badge_id"] == badge_id
            for badge in self.brain.db.get_all_owned_badges(user_id)
        )

    async def cb_trade_info(self, query: CallbackQuery):
        try:
            text = (
                "💱 <b>Трейд SC и медалей</b>\n\n"
                "Создай предложение командой:\n"
                "<code>/trade @username &lt;даю&gt; &lt;хочу&gt;</code>\n\n"
                "<b>Числа означают SC, медаль задаётся как badge:&lt;ID&gt;:</b>\n"
                "<code>/trade @vasya 2.5 1.25</code>\n"
                "<code>/trade @vasya 100 500</code>\n"
                "<code>/trade @vasya badge:leaf 500</code>\n"
                "<code>/trade @vasya 500 badge:d6_full</code>\n"
                "<code>/trade @vasya badge:leaf badge:four_leaf_clover</code>\n\n"
                f"Комиссия: {TRADE_FEE_BURN_PERCENT}% с SC, которые платит принимающий."
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🎖 Выбрать значок", callback_data="trade_pick_badge"
                )],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
            ])
            await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка инструкции трейда: {error}")
            await safe_answer(query, "Не удалось открыть инструкцию.", show_alert=True)

    async def cb_pick_badge(self, query: CallbackQuery):
        try:
            owned = self.brain.db.get_all_owned_badges(query.from_user.id)
            rows = []
            for badge in owned:
                sources = []
                if badge["slots"]:
                    sources.append(
                        "надета: " + ", ".join(str(slot + 1) for slot in badge["slots"])
                    )
                if badge["quantity"]:
                    sources.append(f"в инвентаре: {badge['quantity']}")
                rows.append([InlineKeyboardButton(
                    text=f"{badge['name']} ({'; '.join(sources)})",
                    callback_data=f"trade_select_badge_{badge['badge_id']}",
                )])
            if not rows:
                text = "🎖 <b>Твои медали</b>\n\nНет медалей для обмена."
            else:
                text = (
                    "🎖 <b>Твои медали</b>\n\n"
                    "Выбери медаль, чтобы скопировать её ID для команды трейда."
                )
            rows.append([InlineKeyboardButton(
                text="⬅️ Назад", callback_data="trade"
            )])
            await query.message.edit_text(
                text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                parse_mode="HTML",
            )
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка списка медалей для трейда: {error}")
            await safe_answer(query, "Не удалось загрузить медали.", show_alert=True)

    async def cb_select_badge(self, query: CallbackQuery):
        try:
            badge_id = query.data.removeprefix("trade_select_badge_")
            badge = self._badge(badge_id)
            if not badge:
                await safe_answer(query, "Медаль не найдена.", show_alert=True)
                return
            text = (
                f"🎖 Выбрана медаль: <b>{badge['name']}</b>\n"
                f"ID: <code>{html.escape(badge_id)}</code>\n\n"
                "Скопируй ID в команду:\n"
                f"<code>/trade @username badge:{html.escape(badge_id)} 500</code>\n"
                f"<code>/trade @username 500 badge:{html.escape(badge_id)}</code>"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ К медалям", callback_data="trade_pick_badge")
            ]])
            await query.message.edit_text(
                text, reply_markup=keyboard, parse_mode="HTML"
            )
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка выбора медали для трейда: {error}")
            await safe_answer(query, "Не удалось выбрать медаль.", show_alert=True)

    async def cmd_trade(self, message: Message):
        try:
            await self._prune_expired()
            parts = (message.text or "").split()
            if len(parts) != 4:
                return await message.answer(
                    "💱 <b>Формат:</b>\n"
                    "<code>/trade @username &lt;даю&gt; &lt;хочу&gt;</code>\n\n"
                    "<code>/trade @vasya 100 500</code> — обмен SC\n"
                    "<code>/trade @vasya badge:leaf 500</code> — медаль на SC\n"
                    "<code>/trade @vasya 500 badge:d6_full</code> — SC на медаль\n"
                    "<code>/trade @vasya badge:leaf badge:four_leaf_clover</code>\n\n"
                    "Для медалей используй <code>badge:&lt;ID&gt;</code>.",
                    parse_mode="HTML",
                )

            target_username = parts[1].lstrip("@")
            if not target_username:
                return await message.answer("❌ Укажи username получателя.")
            give = self._parse_asset(parts[2])
            want = self._parse_asset(parts[3])

            target_id = self.brain.db.get_user_by_username(target_username)
            if not target_id:
                return await message.answer(
                    f"❌ Юзер @{html.escape(target_username)} не найден в боте."
                )
            my_id = message.from_user.id
            if target_id == my_id:
                return await message.answer("❌ Нельзя трейдить с самим собой.")

            if give["type"] == "sc":
                my_sc = self.brain.db.get_balance(my_id, "sc")
                if my_sc < give["amount"]:
                    return await message.answer(
                        f"❌ Недостаточно SC. У тебя {format_sc(my_sc)}, "
                        f"нужно {format_sc(give['amount'])}."
                    )
            elif not self._owns_badge(my_id, give["badge_id"]):
                return await message.answer("❌ У тебя нет этой медали.")

            fee = self._fee_for(want)
            if want["type"] == "sc":
                target_sc = self.brain.db.get_balance(target_id, "sc")
                required = want["amount"] + fee
                if target_sc < required:
                    return await message.answer(
                        f"❌ У @{html.escape(target_username)} только "
                        f"{format_sc(target_sc)} SC. Для сделки нужно "
                        f"{format_sc(required)} (включая комиссию "
                        f"{format_sc(fee)})."
                    )

            self.counter += 1
            trade_id = self.counter
            self.pending[trade_id] = {
                "from_id": my_id,
                "to_id": target_id,
                "give": give,
                "want": want,
                "ts": time.time(),
            }
            my_name = html.escape(
                message.from_user.username or message.from_user.first_name or "anon"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Принять", callback_data=f"trade_accept_{trade_id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"trade_decline_{trade_id}"
                )],
            ])
            fee_line = (
                f"Комиссия с тебя: <b>{format_sc(fee)} SC</b>\n"
                if fee else ""
            )
            await self.brain.bot.send_message(
                target_id,
                "💱 <b>Предложение трейда</b>\n\n"
                f"От: @{my_name}\n"
                f"Он даёт тебе: <b>{html.escape(self._asset_label(give))}</b>\n"
                f"Он хочет от тебя: <b>{html.escape(self._asset_label(want))}</b>\n"
                f"{fee_line}\n"
                "Принять предложение?",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await message.answer(
                f"✅ Предложение отправлено @{html.escape(target_username)}."
            )
        except ValueError as error:
            await message.answer(f"❌ {html.escape(str(error))}")
        except Exception as error:
            print(f"⚠️ Ошибка создания трейда: {error}")
            await message.answer("❌ Не удалось создать предложение трейда.")

    async def cb_accept(self, query: CallbackQuery):
        try:
            await self._prune_expired()
            trade_id = int(query.data.removeprefix("trade_accept_"))
            trade = self.pending.get(trade_id)
            if not trade:
                return await safe_answer(query, "Предложение устарело.", show_alert=True)
            if query.from_user.id != trade["to_id"]:
                return await safe_answer(query, "Это не твоё предложение.", show_alert=True)

            from_id = trade["from_id"]
            to_id = trade["to_id"]
            give = trade["give"]
            want = trade["want"]
            fee = self._fee_for(want)
            db = self.brain.db
            conn = db.conn
            from cosmetics import BADGES

            try:
                # Блокируем записи, повторно проверяем активы и выполняем трейд атомарно.
                conn.execute("BEGIN IMMEDIATE")

                if give["type"] == "sc":
                    row = conn.execute(
                        "SELECT sc FROM users WHERE user_id=?", (from_id,)
                    ).fetchone()
                    if not row or row[0] < give["amount"]:
                        conn.rollback()
                        return await safe_answer(
                            query, "У отправителя уже нет столько SC.", show_alert=True
                        )
                if want["type"] == "sc":
                    required = want["amount"] + fee
                    row = conn.execute(
                        "SELECT sc FROM users WHERE user_id=?", (to_id,)
                    ).fetchone()
                    if not row or row[0] < required:
                        conn.rollback()
                        return await safe_answer(
                            query,
                            f"Нужно {format_sc(required)} SC "
                            "(включая комиссию).",
                            show_alert=True,
                        )

                badge_transfers = []
                if give["type"] == "badge":
                    badge_transfers.append((from_id, to_id, give["badge_id"]))
                if want["type"] == "badge":
                    badge_transfers.append((to_id, from_id, want["badge_id"]))

                # Проверяем медали и их shop_id до любых изменений баланса или инвентаря.
                badge_shop_ids = {}
                for sender, _, badge_id in badge_transfers:
                    badge = BADGES.get(badge_id)
                    shop_id = badge.get("shop_id") if badge else None
                    if not shop_id:
                        conn.rollback()
                        return await safe_answer(
                            query, "У медали отсутствует товар в инвентаре.",
                            show_alert=True,
                        )
                    badge_shop_ids[badge_id] = shop_id
                    quantity_row = conn.execute(
                        "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?",
                        (sender, shop_id),
                    ).fetchone()
                    equipped_row = conn.execute(
                        "SELECT slot FROM user_badges "
                        "WHERE user_id=? AND badge_id=? ORDER BY slot LIMIT 1",
                        (sender, badge_id),
                    ).fetchone()
                    if (not quantity_row or quantity_row[0] < 1) and not equipped_row:
                        conn.rollback()
                        message = (
                            "У отправителя больше нет этой медали."
                            if sender == from_id
                            else "У тебя больше нет этой медали."
                        )
                        return await safe_answer(query, message, show_alert=True)

                # Fee is burned: subtracted from the buyer, credited to no one.
                # Сначала списываем валюту и медали.
                if give["type"] == "sc":
                    conn.execute(
                        "UPDATE users SET sc=ROUND(sc-?, 2) WHERE user_id=?",
                        (give["amount"], from_id),
                    )
                if want["type"] == "sc":
                    conn.execute(
                        "UPDATE users SET sc=ROUND(sc-?, 2) WHERE user_id=?",
                        (want["amount"] + fee, to_id),
                    )

                for sender, _, badge_id in badge_transfers:
                    shop_id = badge_shop_ids[badge_id]
                    equipped_row = conn.execute(
                        "SELECT slot FROM user_badges "
                        "WHERE user_id=? AND badge_id=? ORDER BY slot LIMIT 1",
                        (sender, badge_id),
                    ).fetchone()
                    quantity_row = conn.execute(
                        "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?",
                        (sender, shop_id),
                    ).fetchone()
                    if equipped_row:
                        conn.execute(
                            "DELETE FROM user_badges WHERE user_id=? AND slot=?",
                            (sender, equipped_row[0]),
                        )
                    conn.execute(
                        "DELETE FROM user_badge_slot_state "
                        "WHERE user_id=? AND badge_id=?",
                        (sender, badge_id),
                    )
                    if quantity_row and quantity_row[0] > 0:
                        quantity = quantity_row[0] - 1
                        if quantity:
                            conn.execute(
                                "UPDATE inventory SET quantity=? "
                                "WHERE user_id=? AND item_id=?",
                                (quantity, sender, shop_id),
                            )
                        else:
                            conn.execute(
                                "DELETE FROM inventory WHERE user_id=? AND item_id=?",
                                (sender, shop_id),
                            )

                # Затем начисляем валюту и медали получателям.
                if give["type"] == "sc":
                    conn.execute(
                        "UPDATE users SET sc=ROUND(sc+?, 2) WHERE user_id=?",
                        (give["amount"], to_id),
                    )
                if want["type"] == "sc":
                    conn.execute(
                        "UPDATE users SET sc=ROUND(sc+?, 2) WHERE user_id=?",
                        (want["amount"], from_id),
                    )

                for sender, recipient, badge_id in badge_transfers:
                    shop_id = badge_shop_ids[badge_id]
                    conn.execute(
                        "INSERT INTO inventory (user_id, item_id, quantity) "
                        "VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) "
                        "DO UPDATE SET quantity=quantity+1",
                        (recipient, shop_id),
                    )
                conn.commit()
            except Exception as error:
                conn.rollback()
                db.log_admin(0, "trade_error", f"{trade_id}: {error}")
                print(f"Ошибка при передаче трейда #{trade_id}: {error}")
                try:
                    await self.brain.bot.send_message(
                        from_id,
                        f"⚠️ Трейд #{trade_id} не выполнен из-за ошибки. "
                        "Предложение осталось активным.",
                    )
                except Exception as notify_error:
                    print(
                        f"Ошибка уведомления об отмене трейда "
                        f"#{trade_id}: {notify_error}"
                    )
                return await safe_answer(
                    query,
                    "⚠️ Ошибка при выполнении трейда. Обратитесь к админам.",
                    show_alert=True,
                )

            for uid in (from_id, to_id):
                self.brain.db.log_event(
                    uid, "", "trade",
                    f"{self._asset_label(give)}|{self._asset_label(want)}"
                )

            # Удаляем предложение только после успешной фиксации всех передач.
            del self.pending[trade_id]

            try:
                await query.message.edit_text(
                    "✅ <b>Трейд завершён</b>\n\n"
                    f"Ты получил: <b>{html.escape(self._asset_label(give))}</b>\n"
                    f"Ты отдал: <b>{html.escape(self._asset_label(want))}</b>"
                    + (
                        f"\nКомиссия: <b>{format_sc(fee)} SC</b>"
                        if fee else ""
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
            await safe_answer(query)

            receiver_name = html.escape(
                query.from_user.username or query.from_user.first_name or "игроком"
            )
            try:
                await self.brain.bot.send_message(
                    from_id,
                    "✅ <b>Трейд завершён</b>\n\n"
                    f"Ты получил: <b>{html.escape(self._asset_label(want))}</b>\n"
                    f"Ты отдал: <b>{html.escape(self._asset_label(give))}</b>\n"
                    f"Партнёр: @{receiver_name}"
                    + (
                        f"\nКомиссия с партнёра: "
                        f"<b>{format_sc(fee)} SC</b>"
                        if fee else ""
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        except (TypeError, ValueError) as error:
            await safe_answer(query, f"❌ Ошибка трейда: {error}", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка принятия трейда: {error}")
            await safe_answer(query, "Не удалось завершить трейд.", show_alert=True)

    async def cb_decline(self, query: CallbackQuery):
        try:
            trade_id = int(query.data.removeprefix("trade_decline_"))
            trade = self.pending.get(trade_id)
            if not trade:
                return await safe_answer(query, "Уже устарело.", show_alert=True)
            if query.from_user.id != trade["to_id"]:
                return await safe_answer(query, "Это не твоё предложение.", show_alert=True)

            del self.pending[trade_id]
            try:
                await query.message.edit_text("❌ Трейд отклонён.")
            except Exception:
                pass
            await safe_answer(query)
            try:
                await self.brain.bot.send_message(
                    trade["from_id"], "❌ Трейд отклонён."
                )
            except Exception:
                pass
        except (TypeError, ValueError):
            await safe_answer(query, "❌ Ошибка", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка отклонения трейда: {error}")
            await safe_answer(query, "Не удалось отклонить трейд.", show_alert=True)
