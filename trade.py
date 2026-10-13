import time
from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton


TRADE_FEE_PERCENT = 5   # комиссия в SC (сжигается)


class Trade:
    def __init__(self, brain):
        self.brain = brain
        self.pending = {}   # {trade_id: {...}}
        self.counter = 0

    def register(self, dp: Dispatcher):
        dp.message(Command("trade"))(self.cmd_trade)
        dp.callback_query(F.data == "trade")(self.cb_trade_info)
        dp.callback_query(F.data.startswith("trade_accept_"))(self.cb_accept)
        dp.callback_query(F.data.startswith("trade_decline_"))(self.cb_decline)

    async def cb_trade_info(self, query: CallbackQuery):
        text = (
            "💱 **Трейд SC**\n\n"
            "Обмен SC с другим игроком.\n\n"
            "**Формат:**\n"
            "`/trade @username <даю_SC> <хочу_SC>`\n\n"
            "**Пример:**\n"
            "`/trade @vasya 5 3`\n"
            "Ты отдаёшь 5 SC, получаешь 3 SC.\n\n"
            f"Комиссия: {TRADE_FEE_PERCENT}% с принимающего."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    async def cmd_trade(self, message: Message):
        parts = message.text.split()
        if len(parts) != 4:
            return await message.answer(
                "📝 **Формат:**\n"
                "`/trade @username <даю_SC> <хочу_SC>`\n\n"
                "Пример: `/trade @vasya 5 3`\n"
                "Ты отдаёшь 5 SC, хочешь 3 SC.",
                parse_mode="Markdown"
            )

        target_username = parts[1].lstrip("@")
        try:
            give = int(parts[2])
            want = int(parts[3])
        except ValueError:
            return await message.answer("❌ Числа должны быть целыми.")

        if give <= 0 or want <= 0:
            return await message.answer("❌ Числа должны быть больше 0.")

        target_id = self.brain.db.get_user_by_username(target_username)
        if not target_id:
            return await message.answer(f"❌ Юзер @{target_username} не найден в боте.")

        my_id = message.from_user.id
        if target_id == my_id:
            return await message.answer("❌ Нельзя трейдить с самим собой.")

        my_sc = self.brain.db.get_balance(my_id, "sc")
        if my_sc < give:
            return await message.answer(f"❌ Недостаточно SC. У тебя {my_sc}, нужно {give}.")

        target_sc = self.brain.db.get_balance(target_id, "sc")
        fee = max(1, (want * TRADE_FEE_PERCENT) // 100)
        if target_sc < want + fee:
            return await message.answer(
                f"❌ У @{target_username} только {target_sc} SC. "
                f"Для сделки нужно {want + fee} (включая комиссию {fee})."
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

        my_name = message.from_user.username or message.from_user.first_name or "anon"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять",  callback_data=f"trade_accept_{trade_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"trade_decline_{trade_id}")],
        ])

        try:
            await self.brain.bot.send_message(
                target_id,
                f"💱 **Предложение трейда**\n\n"
                f"От: @{my_name}\n"
                f"Он даёт тебе: **{give} SC**\n"
                f"Он хочет от тебя: **{want} SC**\n"
                f"Комиссия: **{fee} SC**\n\n"
                f"Итого ты отдашь: {want + fee} SC",
                reply_markup=kb,
                parse_mode="Markdown"
            )
            await message.answer(f"✅ Предложение отправлено @{target_username}.")
        except Exception as e:
            del self.pending[trade_id]
            await message.answer(f"❌ Не смог отправить сообщение: {e}")

    async def cb_accept(self, query: CallbackQuery):
        try:
            trade_id = int(query.data.replace("trade_accept_", ""))
        except ValueError:
            return await query.answer("❌ Ошибка", show_alert=True)

        trade = self.pending.get(trade_id)
        if not trade:
            return await query.answer("Предложение устарело.", show_alert=True)

        if query.from_user.id != trade["to_id"]:
            return await query.answer("Это не твоё предложение.", show_alert=True)

        # Забираем сделку из pending до проверок баланса, чтобы исключить двойное принятие.
        del self.pending[trade_id]

        from_id = trade["from_id"]
        to_id = trade["to_id"]
        give = trade["give"]
        want = trade["want"]
        fee = max(1, (want * TRADE_FEE_PERCENT) // 100)

        if self.brain.db.get_balance(from_id, "sc") < give:
            return await query.answer("У отправителя уже нет столько SC.", show_alert=True)
        if self.brain.db.get_balance(to_id, "sc") < want + fee:
            return await query.answer(f"Нужно {want + fee} SC (включая комиссию).", show_alert=True)

        # Выполняем
        self.brain.db.add_balance(from_id, "sc", -give)
        self.brain.db.add_balance(to_id, "sc", give)
        self.brain.db.add_balance(to_id, "sc", -(want + fee))
        self.brain.db.add_balance(from_id, "sc", want)
        # fee сжигается

        try:
            await query.message.edit_text(
                f"✅ **Трейд завершён**\n\n"
                f"Ты получил: +{give} SC\n"
                f"Ты отдал: -{want} SC\n"
                f"Комиссия: -{fee} SC",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        try:
            await self.brain.bot.send_message(
                from_id,
                f"✅ **Трейд с @{query.from_user.username or 'юзером'} завершён**\n\n"
                f"Ты получил: +{want} SC\n"
                f"Ты отдал: -{give} SC",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    async def cb_decline(self, query: CallbackQuery):
        try:
            trade_id = int(query.data.replace("trade_decline_", ""))
        except ValueError:
            return await query.answer("❌ Ошибка", show_alert=True)

        trade = self.pending.get(trade_id)
        if not trade:
            return await query.answer("Уже устарело.", show_alert=True)

        if query.from_user.id != trade["to_id"]:
            return await query.answer("Это не твоё предложение.", show_alert=True)

        del self.pending[trade_id]
        try:
            await query.message.edit_text("❌ Трейд отклонён.")
        except Exception:
            pass
        try:
            await self.brain.bot.send_message(trade["from_id"], "❌ Трейд отклонён.")
        except Exception:
            pass