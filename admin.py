
from aiogram import Dispatcher, F
from aiogram.filters import Command
<<<<<<< HEAD
from aiogram.types import Message


# ⚠️ ВПИШИ СВОЙ TELEGRAM ID (узнать у @userinfobot)
=======
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


>>>>>>> 76f277e (<f>)
ADMIN_IDS = [
    5998092433,
    5364546094,
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

<<<<<<< HEAD
    def _check(self, message: Message) -> bool:
        return is_admin(message.from_user.id)

    async def cmd_admin(self, message: Message):
        if not self._check(message):
            return
        text = (
            "🛠 **Админ-команды LuckyScoin:**\n\n"
            "`/give <user_id> <sc|lc> <amount>` — выдать валюту\n"
            "`/take <user_id> <sc|lc> <amount>` — забрать валюту\n"
            "`/setbalance <user_id> <sc|lc> <amount>` — установить баланс\n"
            "`/setlevel <user_id> <level>` — установить уровень\n"
            "`/setxp <user_id> <xp>` — установить XP\n"
            "`/userinfo <user_id>` — инфо о юзере"
        )
        await message.answer(text, parse_mode="Markdown")
=======
        # инлайн-панель
        dp.callback_query(F.data == "admin_stats")(self.cb_stats)
        dp.callback_query(F.data == "admin_econ")(self.cb_econ)
        dp.callback_query(F.data == "admin_help")(self.cb_help)
        dp.callback_query(F.data == "admin_refresh")(self.cb_stats)

    def _check(self, message: Message) -> bool:
        return is_admin(message.from_user.id)

    def _check_cb(self, query: CallbackQuery) -> bool:
        return is_admin(query.from_user.id)

    # ---------- ПАНЕЛЬ ----------

    def _admin_kb(self):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить",   callback_data="admin_refresh")],
            [InlineKeyboardButton(text="💰 Экономика",  callback_data="admin_econ")],
            [InlineKeyboardButton(text="📋 Помощь",     callback_data="admin_help")],
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
>>>>>>> 76f277e (<f>)

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
<<<<<<< HEAD
            f"Ник: @{u['username']}\n\n"
=======
            f"Ник: @{u['username']}\n"
            f"🏷 Титул: {u['title']}\n\n"
>>>>>>> 76f277e (<f>)
            f"⭐ Уровень: {u['level']} (XP: {u['xp']}/{xp_needed})\n"
            f"💰 SC: {u['sc']}\n"
            f"🍀 LC: {u['lc']}\n\n"
            f"🎮 Игр: {u['games']}\n"
            f"✅ Побед: {u['wins']}\n"
            f"❌ Проигрышей: {u['losses']}\n"
            f"📊 Винрейт: {winrate}%"
        )
        await message.answer(text, parse_mode="Markdown")