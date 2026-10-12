from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import os
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import asyncio


class MaintStates(StatesGroup):
    waiting_for_reason = State()


ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class Admin:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.message(Command("admin"))(self.cmd_admin)
        dp.message(Command("give"))(self.cmd_give)
        dp.message(Command("take"))(self.cmd_take)
        dp.message(Command("setbalance"))(self.cmd_setbalance)
        dp.message(Command("setlevel"))(self.cmd_setlevel)
        dp.message(Command("setxp"))(self.cmd_setxp)
        dp.message(Command("userinfo"))(self.cmd_userinfo)

        # инлайн-панель
        dp.callback_query(F.data == "admin_stats")(self.cb_stats)
        dp.callback_query(F.data == "admin_econ")(self.cb_econ)
        dp.callback_query(F.data == "admin_help")(self.cb_help)
        dp.callback_query(F.data == "admin_refresh")(self.cb_stats)

        #техперерыыв
        dp.callback_query(F.data == "admin_maint")(self.cb_maint)
        dp.callback_query(F.data == "admin_maint_on")(self.cb_maint_on_start)
        dp.callback_query(F.data == "admin_maint_off")(self.cb_maint_off)
        dp.message(MaintStates.waiting_for_reason)(self.on_maint_reason)

                # рассылка + компенсация
        dp.message(Command("broadcast"))(self.cmd_broadcast)
        dp.message(Command("compensate"))(self.cmd_compensate)

    def _check(self, message: Message) -> bool:
        return is_admin(message.from_user.id)

    def _check_cb(self, query: CallbackQuery) -> bool:
        return is_admin(query.from_user.id)

    # ---------- ПАНЕЛЬ ----------

    def _admin_kb(self):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить",    callback_data="admin_refresh")],
            [InlineKeyboardButton(text="💰 Экономика",   callback_data="admin_econ")],
            [InlineKeyboardButton(text="🛠 Техперерыв",   callback_data="admin_maint")],
            [InlineKeyboardButton(text="📋 Помощь",      callback_data="admin_help")],
        ])

    async def cmd_admin(self, message: Message):
        if not self._check(message):
            return
        await self._send_stats(message)

    async def _send_stats(self, message_or_query):
        s = self.brain.db.get_bot_stats()
        text = (
            "🛠 **Админ-панель LuckyScoin**\n\n"
            f"👥 Юзеров: **{s['users']}**\n"
            f"💰 SC в обороте: **{s['sc']}**\n"
            f"🍀 LC в обороте: **{s['lc']}**\n"
            f"🎮 Игр сыграно: **{s['games']}**\n\n"
            "Выбери действие:"
        )
        if isinstance(message_or_query, CallbackQuery):
            await message_or_query.message.edit_text(text, reply_markup=self._admin_kb(), parse_mode="Markdown")
            await message_or_query.answer()
        else:
            await message_or_query.answer(text, reply_markup=self._admin_kb(), parse_mode="Markdown")

    async def cb_stats(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        await self._send_stats(query)

    async def cb_econ(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        text = (
            "💰 **Экономика — команды**\n\n"
            "`/give <user_id> <sc|lc> <amount>` — выдать\n"
            "`/take <user_id> <sc|lc> <amount>` — забрать\n"
            "`/setbalance <user_id> <sc|lc> <amount>` — установить\n"
            "`/setlevel <user_id> <level>` — уровень\n"
            "`/setxp <user_id> <xp>` — XP\n"
            "`/userinfo <user_id>` — инфо о юзере"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")]
        ])
        await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await query.answer()

    async def cb_help(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        text = (
            "📋 **Помощь по админке**\n\n"
            "Все команды пишутся в чат, как обычные сообщения.\n\n"
            "• `/admin` — открыть эту панель\n"
            "• `/userinfo <id>` — узнать всё про юзера\n"
            "• `/give` — выдать валюту\n"
            "• `/take` — забрать\n"
            "• `/compensate` — начислить всем\n"
            "• `/broadcast` — рассылка\n"
            "• `/setbalance` — жёстко установить баланс\n"
            "• `/setlevel` и `/setxp` — управление прокачкой\n\n"
            "Пример: `/give 123456789 sc 100`"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")]
        ])
        await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await query.answer()

    # ---------- СТАРЫЕ КОМАНДЫ (не трогаем) ----------

    def _parse_args(self, message: Message, expected: int):
        args = message.text.split()
        if len(args) != expected:
            return None
        return args[1:]

    async def cmd_give(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 4)
        if not parts:
            return await message.answer("Использование: /give <user_id> <sc|lc> <amount>")
        try:
            target_id = int(parts[0])
            currency = parts[1].lower()
            amount = int(parts[2])
        except ValueError:
            return await message.answer("❌ Пример: /give 123456789 sc 100")
        if currency not in ("sc", "lc"):
            return await message.answer("❌ Валюта: sc или lc")

        self.brain.db.add_balance(target_id, currency, amount)
        new_bal = self.brain.db.get_balance(target_id, currency)
        await message.answer(
            f"✅ Выдано **{amount} {currency.upper()}** юзеру `{target_id}`\n"
            f"Новый баланс: {new_bal}",
            parse_mode="Markdown"
        )

    async def cmd_take(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 4)
        if not parts:
            return await message.answer("Использование: /take <user_id> <sc|lc> <amount>")
        try:
            target_id = int(parts[0])
            currency = parts[1].lower()
            amount = int(parts[2])
        except ValueError:
            return await message.answer("❌ Пример: /take 123456789 lc 50")
        if currency not in ("sc", "lc"):
            return await message.answer("❌ Валюта: sc или lc")

        self.brain.db.add_balance(target_id, currency, -amount)
        new_bal = self.brain.db.get_balance(target_id, currency)
        await message.answer(
            f"✅ Забрано **{amount} {currency.upper()}** у `{target_id}`\n"
            f"Новый баланс: {new_bal}",
            parse_mode="Markdown"
        )

    async def cmd_setbalance(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 4)
        if not parts:
            return await message.answer("Использование: /setbalance <user_id> <sc|lc> <amount>")
        try:
            target_id = int(parts[0])
            currency = parts[1].lower()
            amount = int(parts[2])
        except ValueError:
            return await message.answer("❌ Неверные аргументы.")
        if currency not in ("sc", "lc"):
            return await message.answer("❌ Валюта: sc или lc")

        self.brain.db.set_balance(target_id, currency, amount)
        await message.answer(
            f"✅ Баланс {currency.upper()} юзера `{target_id}` = **{amount}**",
            parse_mode="Markdown"
        )

    async def cmd_setlevel(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 3)
        if not parts:
            return await message.answer("Использование: /setlevel <user_id> <level>")
        try:
            target_id = int(parts[0])
            level = int(parts[1])
        except ValueError:
            return await message.answer("❌ Неверные аргументы.")
        if level < 0:
            return await message.answer("❌ Уровень не может быть отрицательным.")

        self.brain.db.set_level(target_id, level)
        await message.answer(f"✅ Уровень `{target_id}` = **{level}**", parse_mode="Markdown")

    async def cmd_setxp(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 3)
        if not parts:
            return await message.answer("Использование: /setxp <user_id> <xp>")
        try:
            target_id = int(parts[0])
            xp = int(parts[1])
        except ValueError:
            return await message.answer("❌ Неверные аргументы.")
        if xp < 0:
            return await message.answer("❌ XP не может быть отрицательным.")

        self.brain.db.set_xp(target_id, xp)
        await message.answer(f"✅ XP `{target_id}` = **{xp}**", parse_mode="Markdown")

    async def cmd_userinfo(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 2)
        if not parts:
            return await message.answer("Использование: /userinfo <user_id>")
        try:
            target_id = int(parts[0])
        except ValueError:
            return await message.answer("❌ ID должен быть числом.")

        u = self.brain.db.get_user(target_id)
        xp_needed = 100 * (u["level"] + 1)
        winrate = round(u["wins"] / u["games"] * 100, 1) if u["games"] > 0 else 0

        text = (
            f"👤 **Юзер** `{target_id}`\n"
            f"Ник: @{u['username']}\n"
            f"🏷 Титул: {u['title']}\n\n"
            f"⭐ Уровень: {u['level']} (XP: {u['xp']}/{xp_needed})\n"
            f"💰 SC: {u['sc']}\n"
            f"🍀 LC: {u['lc']}\n\n"
            f"🎮 Игр: {u['games']}\n"
            f"✅ Побед: {u['wins']}\n"
            f"❌ Проигрышей: {u['losses']}\n"
            f"📊 Винрейт: {winrate}%"
        )
        await message.answer(text, parse_mode="Markdown")

        # ================= ТЕХПЕРЕРЫВ =================

    async def cb_maint(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)

        maint = self.brain.db.get_maintenance()
        status = "🔴 ВКЛЮЧЁН" if maint["enabled"] else "🟢 ВЫКЛЮЧЕН"
        reason = maint["reason"] or "—"

        text = (
            "🛠 <b>Технический перерыв</b>\n\n"
            f"Статус: {status}\n"
            f"Причина: <i>{reason}</i>\n\n"
            "Когда включён — все юзеры (кроме админов) не могут играть.\n"
            "При выключении — всем уйдёт уведомление."
        )

        buttons = []
        if maint["enabled"]:
            buttons.append([InlineKeyboardButton(
                text="✅ Выключить техперерыв",
                callback_data="admin_maint_off"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text="🛠 Включить техперерыв",
                callback_data="admin_maint_on"
            )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await query.answer()

    async def cb_maint_on_start(self, query: CallbackQuery, state: FSMContext):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        await state.set_state(MaintStates.waiting_for_reason)
        text = (
            "🛠 <b>Включение техперерыва</b>\n\n"
            "Напиши причину для юзеров (например: «обновляем слоты, скоро вернёмся»).\n\n"
            "<i>Чтобы отменить — /cancel.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_maint")]
        ])
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await query.answer()

    async def on_maint_reason(self, message: Message, state: FSMContext):
        if not self._check(message):
            return
        reason = (message.text or "").strip()
        if reason.startswith("/"):
            await state.clear()
            return await message.answer("Ок, отменено.")
        if not (3 <= len(reason) <= 200):
            return await message.answer("❌ Причина должна быть от 3 до 200 символов.")

        self.brain.db.set_maintenance(True, reason)
        await state.clear()
        await message.answer(
            f"✅ <b>Техперерыв включён</b>\n\n"
            f"Причина: <i>{reason}</i>\n\n"
            f"Юзеры видят сообщение, играть не могут.",
            parse_mode="HTML"
        )

        # Уведомляем всех (кроме админов)
        await self._broadcast(
            f"🛠 <b>Технический перерыв</b>\n\n"
            f"Причина: <i>{reason}</i>\n\n"
            f"Скоро вернёмся!"
        )

    async def cb_maint_off(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)

        self.brain.db.set_maintenance(False, "")
        await query.answer("✅ Техперерыв выключен", show_alert=True)

        # Уведомляем всех
        await self._broadcast(
            "✅ <b>Технические работы завершены!</b>\n\n"
            "Снова всё работает — заходи и играй! 🎰"
        )

        await self.cb_maint(query)

    async def _broadcast(self, text):
        """Рассылает сообщение всем юзерам, кроме админов."""
        user_ids = self.brain.db.get_all_user_ids()
        sent = 0
        for uid in user_ids:
            if is_admin(uid):
                continue
            try:
                await self.brain.bot.send_message(uid, text, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
        return sent

        # ================= РАССЫЛКА =================

    async def cmd_broadcast(self, message: Message):
        if not self._check(message):
            return
        # /broadcast текст сообщения
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.answer(
                "📢 <b>Рассылка</b>\n\n"
                "Использование:\n"
                "<code>/broadcast Текст сообщения</code>\n\n"
                "Пример:\n"
                "<code>/broadcast 🎉 Мы вернулись! Всем по 500 LC!</code>",
                parse_mode="HTML"
            )

        text = parts[1].strip()
        user_ids = self.brain.db.get_all_user_ids()
        total = len(user_ids)

        status = await message.answer(f"📤 Рассылаю {total} юзерам...")

        sent = 0
        failed = 0
        for uid in user_ids:
            try:
                await self.brain.bot.send_message(uid, text, parse_mode="HTML")
                sent += 1
                # анти-флуд телеги: 30 сообщений в секунду максимум
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1

        await status.edit_text(
            f"✅ <b>Рассылка завершена</b>\n\n"
            f"📤 Отправлено: <b>{sent}</b>\n"
            f"❌ Не дошло: <b>{failed}</b>\n"
            f"👥 Всего: {total}",
            parse_mode="HTML"
        )

    async def cmd_compensate(self, message: Message):
        if not self._check(message):
            return
        # /compensate sc 100  -> выдать всем 100 SC
        # /compensate lc 500  -> выдать всем 500 LC
        parts = message.text.split()
        if len(parts) != 3:
            return await message.answer(
                "🎁 <b>Компенсация всем</b>\n\n"
                "Использование:\n"
                "<code>/compensate &lt;sc|lc&gt; &lt;amount&gt;</code>\n\n"
                "Примеры:\n"
                "<code>/compensate lc 500</code> — 500 LC всем\n"
                "<code>/compensate sc 10</code> — 10 SC всем",
                parse_mode="HTML"
            )

        currency = parts[1].lower()
        if currency not in ("sc", "lc"):
            return await message.answer("❌ Валюта: sc или lc")

        try:
            amount = int(parts[2])
        except ValueError:
            return await message.answer("❌ Сумма должна быть числом")
        if amount <= 0:
            return await message.answer("❌ Сумма должна быть больше 0")

        user_ids = self.brain.db.get_all_user_ids()
        total = len(user_ids)

        status = await message.answer(f"🎁 Начисляю {amount} {currency.upper()} {total} юзерам...")

        sent = 0
        for uid in user_ids:
            try:
                self.brain.db.add_balance(uid, currency, amount)
                sent += 1
            except Exception:
                pass

        await status.edit_text(
            f"✅ <b>Компенсация выдана</b>\n\n"
            f"💰 Каждому: <b>+{amount} {currency.upper()}</b>\n"
            f"👥 Юзеров: <b>{sent}</b>",
            parse_mode="HTML"
        )