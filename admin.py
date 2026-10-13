from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import os
import asyncio
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from cosmetics import BADGES


# ============================================================
#  СТАТИЧНЫЕ АДМИНЫ (из переменной окружения) — снять нельзя
# ============================================================
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]


class MaintStates(StatesGroup):
    waiting_for_reason = State()


class DeleteUserStates(StatesGroup):
    waiting_for_confirm = State()


def is_static_admin(user_id: int) -> bool:
    """Админ из env — его снять нельзя."""
    return user_id in ADMIN_IDS


def is_admin(user_id: int, db=None) -> bool:
    """Статичный ИЛИ динамический админ."""
    if is_static_admin(user_id):
        return True
    if db is not None:
        try:
            return db.is_db_admin(user_id)
        except Exception:
            return False
    return False


class Admin:
    def __init__(self, brain):
        self.brain = brain

    # ---------- РЕГИСТРАЦИЯ ----------

    def register(self, dp: Dispatcher):
        # обычные команды
        dp.message(Command("admin"))(self.cmd_admin)
        dp.message(Command("give"))(self.cmd_give)
        dp.message(Command("take"))(self.cmd_take)
        dp.message(Command("setbalance"))(self.cmd_setbalance)
        dp.message(Command("setlevel"))(self.cmd_setlevel)
        dp.message(Command("setxp"))(self.cmd_setxp)
        dp.message(Command("userinfo"))(self.cmd_userinfo)

        # медали
        dp.message(Command("givebadge"))(self.cmd_givebadge)
        dp.message(Command("removebadge"))(self.cmd_removebadge)
        dp.message(Command("listbadges"))(self.cmd_listbadges)
        dp.message(Command("clearbadges"))(self.cmd_clearbadges)

        # админы
        dp.message(Command("addadmin"))(self.cmd_addadmin)
        dp.message(Command("removeadmin"))(self.cmd_removeadmin)
        dp.message(Command("listadmins"))(self.cmd_listadmins)

        # удаление юзера
        dp.message(Command("deleteuser"))(self.cmd_deleteuser)
        dp.message(DeleteUserStates.waiting_for_confirm)(self.on_delete_confirm)
        dp.callback_query(F.data.startswith("deluser_yes_"))(self.cb_delete_yes)
        dp.callback_query(F.data.startswith("deluser_no_"))(self.cb_delete_no)

        # лог
        dp.message(Command("adminlog"))(self.cmd_adminlog)
        dp.message(Command("clearlog"))(self.cmd_clearlog)

        # инлайн-панель
        dp.callback_query(F.data == "admin_stats")(self.cb_stats)
        dp.callback_query(F.data == "admin_econ")(self.cb_econ)
        dp.callback_query(F.data == "admin_help")(self.cb_help)
        dp.callback_query(F.data == "admin_refresh")(self.cb_stats)
        dp.callback_query(F.data == "admin_admins")(self.cb_admins)
        dp.callback_query(F.data == "admin_log")(self.cb_log)

        # техперерыв
        dp.callback_query(F.data == "admin_maint")(self.cb_maint)
        dp.callback_query(F.data == "admin_maint_on")(self.cb_maint_on_start)
        dp.callback_query(F.data == "admin_maint_off")(self.cb_maint_off)
        dp.message(MaintStates.waiting_for_reason)(self.on_maint_reason)

        # рассылка + компенсация
        dp.message(Command("broadcast"))(self.cmd_broadcast)
        dp.message(Command("compensate"))(self.cmd_compensate)

    # ---------- ПРОВЕРКИ ----------

    def _check(self, message: Message) -> bool:
        return is_admin(message.from_user.id, self.brain.db)

    def _check_cb(self, query: CallbackQuery) -> bool:
        return is_admin(query.from_user.id, self.brain.db)

    def _log(self, message: Message):
        """Логирует команду админа."""
        text = message.text or ""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lstrip("/") if parts else "?"
        args = parts[1] if len(parts) > 1 else ""
        self.brain.db.log_admin(message.from_user.id, cmd, args)

    # ---------- УНИВЕРСАЛЬНЫЙ ПОИСК ЮЗЕРА ----------

    def _resolve_user(self, raw: str):
        raw = raw.strip()
        if not raw:
            return None
        if raw.startswith("@"):
            return self.brain.db.get_user_by_username(raw[1:])
        if not raw.lstrip("-").isdigit():
            return self.brain.db.get_user_by_username(raw)
        try:
            return int(raw)
        except ValueError:
            return None

    # ---------- ПАНЕЛЬ ----------

    def _admin_kb(self):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить",   callback_data="admin_refresh")],
            [InlineKeyboardButton(text="💰 Экономика",  callback_data="admin_econ")],
            [InlineKeyboardButton(text="👑 Админы",     callback_data="admin_admins")],
            [InlineKeyboardButton(text="📜 Лог",        callback_data="admin_log")],
            [InlineKeyboardButton(text="🛠 Техперерыв",  callback_data="admin_maint")],
            [InlineKeyboardButton(text="📋 Помощь",     callback_data="admin_help")],
        ])

    async def cmd_admin(self, message: Message):
        if not self._check(message):
            return
        self._log(message)
        await self._send_stats(message)

    async def _send_stats(self, message_or_query):
        s = self.brain.db.get_bot_stats()
        text = (
            "🛠 <b>Админ-панель LuckyScoin</b>\n\n"
            f"👥 Юзеров: <b>{s['users']}</b>\n"
            f"💰 SC в обороте: <b>{s['sc']}</b>\n"
            f"🍀 LC в обороте: <b>{s['lc']}</b>\n"
            f"🎮 Игр сыграно: <b>{s['games']}</b>\n\n"
            "Выбери действие:"
        )
        if isinstance(message_or_query, CallbackQuery):
            try:
                await message_or_query.message.edit_text(
                    text, reply_markup=self._admin_kb(), parse_mode="HTML"
                )
            except Exception:
                pass
            await message_or_query.answer()
        else:
            await message_or_query.answer(text, reply_markup=self._admin_kb(), parse_mode="HTML")

    async def cb_stats(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        await self._send_stats(query)

    async def cb_econ(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        text = (
            "💰 <b>Экономика — команды</b>\n\n"
            "<code>/give &lt;id|@user&gt; &lt;sc|lc&gt; &lt;amount&gt;</code>\n"
            "<code>/take &lt;id|@user&gt; &lt;sc|lc&gt; &lt;amount&gt;</code>\n"
            "<code>/setbalance &lt;id|@user&gt; &lt;sc|lc&gt; &lt;amount&gt;</code>\n"
            "<code>/setlevel &lt;id|@user&gt; &lt;level&gt;</code>\n"
            "<code>/setxp &lt;id|@user&gt; &lt;xp&gt;</code>\n"
            "<code>/userinfo &lt;id|@user&gt;</code>\n\n"
            "<b>Медали:</b>\n"
            "<code>/givebadge &lt;id|@user&gt; &lt;badge&gt;</code>\n"
            "<code>/removebadge &lt;id|@user&gt; &lt;slot|all&gt;</code>\n"
            "<code>/listbadges</code> — список ID\n"
            "<code>/clearbadges</code> — снести всем"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

    async def cb_help(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        text = (
            "📋 <b>Помощь по админке</b>\n\n"
            "<b>Экономика:</b>\n"
            "• <code>/give</code> — выдать валюту\n"
            "• <code>/take</code> — забрать\n"
            "• <code>/setbalance</code> — установить баланс\n"
            "• <code>/setlevel</code>, <code>/setxp</code>\n"
            "• <code>/userinfo</code> — всё о юзере\n"
            "• <code>/compensate</code> — начислить всем\n"
            "• <code>/broadcast</code> — рассылка\n\n"
            "<b>Медали:</b>\n"
            "• <code>/givebadge</code>, <code>/removebadge</code>\n"
            "• <code>/listbadges</code>, <code>/clearbadges</code>\n\n"
            "<b>Админы:</b>\n"
            "• <code>/addadmin &lt;id|@user&gt;</code>\n"
            "• <code>/removeadmin &lt;id|@user&gt;</code>\n"
            "• <code>/listadmins</code>\n\n"
            "<b>Юзеры:</b>\n"
            "• <code>/deleteuser &lt;id|@user&gt;</code>\n\n"
            "<b>Логи:</b>\n"
            "• <code>/adminlog [N]</code>\n"
            "• <code>/clearlog</code>\n\n"
            "💡 Вместо ID можно писать <b>@username</b>."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

    # ================= ЭКОНОМИКА =================

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
            return await message.answer("Использование: /give <id|@user> <sc|lc> <amount>")
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")
        try:
            currency = parts[1].lower()
            amount = int(parts[2])
        except ValueError:
            return await message.answer("❌ Пример: /give @vasya sc 100")
        if currency not in ("sc", "lc"):
            return await message.answer("❌ Валюта: sc или lc")

        self.brain.db.add_balance(target_id, currency, amount)
        new_bal = self.brain.db.get_balance(target_id, currency)
        await message.answer(
            f"✅ Выдано <b>{amount} {currency.upper()}</b> юзеру <code>{target_id}</code>\n"
            f"Новый баланс: {new_bal}",
            parse_mode="HTML"
        )

    async def cmd_take(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 4)
        if not parts:
            return await message.answer("Использование: /take <id|@user> <sc|lc> <amount>")
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")
        try:
            currency = parts[1].lower()
            amount = int(parts[2])
        except ValueError:
            return await message.answer("❌ Пример: /take @vasya lc 50")
        if currency not in ("sc", "lc"):
            return await message.answer("❌ Валюта: sc или lc")

        self.brain.db.add_balance(target_id, currency, -amount)
        new_bal = self.brain.db.get_balance(target_id, currency)
        await message.answer(
            f"✅ Забрано <b>{amount} {currency.upper()}</b> у <code>{target_id}</code>\n"
            f"Новый баланс: {new_bal}",
            parse_mode="HTML"
        )

    async def cmd_setbalance(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 4)
        if not parts:
            return await message.answer("Использование: /setbalance <id|@user> <sc|lc> <amount>")
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")
        try:
            currency = parts[1].lower()
            amount = int(parts[2])
        except ValueError:
            return await message.answer("❌ Неверные аргументы.")
        if currency not in ("sc", "lc"):
            return await message.answer("❌ Валюта: sc или lc")

        self.brain.db.set_balance(target_id, currency, amount)
        await message.answer(
            f"✅ Баланс {currency.upper()} юзера <code>{target_id}</code> = <b>{amount}</b>",
            parse_mode="HTML"
        )

    async def cmd_setlevel(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 3)
        if not parts:
            return await message.answer("Использование: /setlevel <id|@user> <level>")
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")
        try:
            level = int(parts[1])
        except ValueError:
            return await message.answer("❌ Уровень — число.")
        if level < 0:
            return await message.answer("❌ Уровень не может быть отрицательным.")

        self.brain.db.set_level(target_id, level)
        await message.answer(
            f"✅ Уровень <code>{target_id}</code> = <b>{level}</b>",
            parse_mode="HTML"
        )

    async def cmd_setxp(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 3)
        if not parts:
            return await message.answer("Использование: /setxp <id|@user> <xp>")
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")
        try:
            xp = int(parts[1])
        except ValueError:
            return await message.answer("❌ XP — число.")
        if xp < 0:
            return await message.answer("❌ XP не может быть отрицательным.")

        self.brain.db.set_xp(target_id, xp)
        await message.answer(
            f"✅ XP <code>{target_id}</code> = <b>{xp}</b>",
            parse_mode="HTML"
        )

    async def cmd_userinfo(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 2)
        if not parts:
            return await message.answer("Использование: /userinfo <id|@user>")
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")

        u = self.brain.db.get_user(target_id)
        xp_needed = 100 * (u["level"] + 1)
        winrate = round(u["wins"] / u["games"] * 100, 1) if u["games"] > 0 else 0

        badges_line = ""
        try:
            equipped = self.brain.db.get_user_badges_full(target_id)
            if equipped:
                names = []
                for slot in sorted(equipped.keys()):
                    info = equipped[slot]
                    bid = info["badge_id"]
                    hp = info["hp"]
                    badge = BADGES.get(bid)
                    if badge:
                        hp_str = "∞" if hp == -1 else str(hp)
                        names.append(f"{badge['name']} [{hp_str}]")
                if names:
                    badges_line = "🎖 Медали: " + " • ".join(names) + "\n"
        except Exception:
            pass

        admin_marker = ""
        if is_static_admin(target_id):
            admin_marker = " 👑 <i>(статичный админ)</i>"
        elif self.brain.db.is_db_admin(target_id):
            admin_marker = " 👑 <i>(админ)</i>"

        title_line = f"🏷 Титул: {u['title']}\n" if u["title"] else ""
        text = (
            f"👤 <b>Юзер</b> <code>{target_id}</code>{admin_marker}\n"
            f"Ник: @{u['username']}\n"
            f"{title_line}"
            f"{badges_line}\n"
            f"⭐ Уровень: {u['level']} (XP: {u['xp']}/{xp_needed})\n"
            f"💰 SC: {u['sc']}\n"
            f"🍀 LC: {u['lc']}\n\n"
            f"🎮 Игр: {u['games']}\n"
            f"✅ Побед: {u['wins']}\n"
            f"❌ Проигрышей: {u['losses']}\n"
            f"📊 Винрейт: {winrate}%\n"
            f"🔥 Серия: {u.get('streak', 0)} (макс: {u.get('max_streak', 0)})"
        )
        await message.answer(text, parse_mode="HTML")

    # ================= МЕДАЛИ =================

    async def cmd_givebadge(self, message: Message):
        if not self._check(message):
            return
        parts = message.text.split()
        if len(parts) != 3:
            return await message.answer(
                "🏅 Использование:\n"
                "<code>/givebadge &lt;id|@user&gt; &lt;badge_id&gt;</code>\n"
                "Список ID: /listbadges",
                parse_mode="HTML"
            )
        self._log(message)
        target_id = self._resolve_user(parts[1])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")
        badge_id = parts[2].lower()

        if badge_id not in BADGES:
            return await message.answer(
                f"❌ Медаль <code>{badge_id}</code> не найдена. Список: /listbadges",
                parse_mode="HTML"
            )

        equipped = self.brain.db.get_user_badges(target_id)
        free_slot = None
        for i in range(5):
            if not equipped.get(i):
                free_slot = i
                break

        if free_slot is None:
            return await message.answer(
                f"❌ У юзера <code>{target_id}</code> все 5 слотов заняты. /removebadge",
                parse_mode="HTML"
            )

        self.brain.db.set_user_badge(target_id, free_slot, badge_id)
        badge = BADGES[badge_id]
        await message.answer(
            f"✅ Медаль <b>{badge['name']}</b> выдана юзеру <code>{target_id}</code>\n"
            f"Слот: <b>{free_slot + 1}</b>",
            parse_mode="HTML"
        )

    async def cmd_removebadge(self, message: Message):
        if not self._check(message):
            return
        parts = message.text.split()
        if len(parts) not in (3, 4):
            return await message.answer(
                "🏅 Использование:\n"
                "<code>/removebadge &lt;id|@user&gt; &lt;slot 1-5|all&gt;</code>",
                parse_mode="HTML"
            )
        self._log(message)
        target_id = self._resolve_user(parts[1])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")

        if parts[2].lower() == "all":
            self.brain.db.conn.execute("DELETE FROM user_badges WHERE user_id=?", (target_id,))
            self.brain.db.conn.commit()
            return await message.answer(
                f"✅ Все значки сняты у <code>{target_id}</code>",
                parse_mode="HTML"
            )

        try:
            slot = int(parts[2]) - 1
        except ValueError:
            return await message.answer("❌ Слот — число 1-5.")
        if not (0 <= slot <= 4):
            return await message.answer("❌ Слот от 1 до 5.")

        self.brain.db.remove_user_badge(target_id, slot)
        await message.answer(
            f"✅ Значок со слота <b>{slot + 1}</b> снят у <code>{target_id}</code>",
            parse_mode="HTML"
        )

    async def cmd_listbadges(self, message: Message):
        if not self._check(message):
            return
        self._log(message)
        lines = ["🎖 <b>Все медали</b>\n"]
        for bid, b in BADGES.items():
            hp = b.get("hp", "inf")
            hp_str = "∞" if hp == "inf" else str(hp)
            rarity = b.get("rarity", "?")
            lines.append(f"• <code>{bid}</code> — {b['name']} [{rarity}, HP: {hp_str}]")
        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:4000] + "\n\n<i>...список обрезан</i>"
        await message.answer(text, parse_mode="HTML")

    async def cmd_clearbadges(self, message: Message):
        if not self._check(message):
            return
        self._log(message)
        self.brain.db.conn.execute("DELETE FROM user_badges")
        self.brain.db.conn.commit()
        await message.answer("✅ Все медали у всех игроков удалены.")

    # ================= АДМИНЫ =================

    async def cmd_addadmin(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 2)
        if not parts:
            return await message.answer(
                "👑 <b>Добавить админа</b>\n\n"
                "<code>/addadmin &lt;id|@user&gt;</code>",
                parse_mode="HTML"
            )
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден. Убедись, что он жал /start.")

        if is_static_admin(target_id):
            return await message.answer("ℹ️ Этот юзер и так статичный админ.")

        if self.brain.db.is_db_admin(target_id):
            return await message.answer("ℹ️ Этот юзер уже админ.")

        self.brain.db.add_admin(target_id, added_by=message.from_user.id)
        await message.answer(
            f"✅ Юзер <code>{target_id}</code> теперь админ.",
            parse_mode="HTML"
        )

    async def cmd_removeadmin(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 2)
        if not parts:
            return await message.answer(
                "👑 <b>Снять админа</b>\n\n"
                "<code>/removeadmin &lt;id|@user&gt;</code>",
                parse_mode="HTML"
            )
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")

        if is_static_admin(target_id):
            return await message.answer(
                "⛔ <b>Нельзя снять статичного админа.</b>\n"
                "<i>Он задан в переменной окружения ADMIN_IDS.</i>",
                parse_mode="HTML"
            )

        if not self.brain.db.is_db_admin(target_id):
            return await message.answer("ℹ️ Этот юзер не админ.")

        self.brain.db.remove_admin(target_id)
        await message.answer(
            f"✅ Юзер <code>{target_id}</code> больше не админ.",
            parse_mode="HTML"
        )

    async def cmd_listadmins(self, message: Message):
        if not self._check(message):
            return
        self._log(message)
        lines = ["👑 <b>Список админов</b>\n"]

        lines.append("🔒 <b>Статичные</b> (из env, снять нельзя):")
        if ADMIN_IDS:
            for uid in ADMIN_IDS:
                lines.append(f"• <code>{uid}</code>")
        else:
            lines.append("<i>нет</i>")

        lines.append("\n👤 <b>Динамические</b> (можно снять):")
        db_admins = self.brain.db.get_db_admins()
        if db_admins:
            for uid, added_by, added_at in db_admins:
                import time as _t
                date = _t.strftime("%d.%m.%Y", _t.localtime(added_at))
                lines.append(f"• <code>{uid}</code> — добавил <code>{added_by}</code> ({date})")
        else:
            lines.append("<i>нет</i>")

        await message.answer("\n".join(lines), parse_mode="HTML")

    async def cb_admins(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)

        lines = ["👑 <b>Админы</b>\n"]
        lines.append("🔒 <b>Статичные:</b>")
        if ADMIN_IDS:
            for uid in ADMIN_IDS:
                lines.append(f"• <code>{uid}</code>")
        else:
            lines.append("<i>нет</i>")

        lines.append("\n👤 <b>Динамические:</b>")
        db_admins = self.brain.db.get_db_admins()
        if db_admins:
            for uid, added_by, added_at in db_admins:
                lines.append(f"• <code>{uid}</code> (кем: {added_by})")
        else:
            lines.append("<i>нет</i>")

        lines.append("\n<i>Управление: /addadmin, /removeadmin</i>")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")]
        ])
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

    # ================= УДАЛЕНИЕ ЮЗЕРА =================

    async def cmd_deleteuser(self, message: Message):
        if not self._check(message):
            return
        parts = self._parse_args(message, 2)
        if not parts:
            return await message.answer(
                "🗑 <b>Удалить юзера</b>\n\n"
                "<code>/deleteuser &lt;id|@user&gt;</code>\n\n"
                "⚠️ Удаляет ВСЁ: баланс, значки, казино, инвентарь.",
                parse_mode="HTML"
            )
        self._log(message)
        target_id = self._resolve_user(parts[0])
        if target_id is None:
            return await message.answer("❌ Юзер не найден.")

        if is_static_admin(target_id):
            return await message.answer("⛔ Нельзя удалить статичного админа.")

        if target_id == message.from_user.id:
            return await message.answer("⛔ Нельзя удалить себя.")

        u = self.brain.db.get_user(target_id)
        text = (
            f"🗑 <b>Удалить юзера?</b>\n\n"
            f"ID: <code>{target_id}</code>\n"
            f"Ник: @{u['username']}\n"
            f"💰 SC: {u['sc']}  •  🍀 LC: {u['lc']}\n"
            f"⭐ Уровень: {u['level']}\n\n"
            f"<b>Это действие необратимо!</b>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 УДАЛИТЬ", callback_data=f"deluser_yes_{target_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"deluser_no_{target_id}")],
        ])
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

    async def on_delete_confirm(self, message: Message, state: FSMContext):
        # на всякий случай, если юзер что-то пишет
        await state.clear()

    async def cb_delete_yes(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        try:
            target_id = int(query.data.replace("deluser_yes_", ""))
        except ValueError:
            return await query.answer("Ошибка", show_alert=True)

        if is_static_admin(target_id):
            return await query.answer("⛔ Нельзя удалить статичного админа.", show_alert=True)
        if target_id == query.from_user.id:
            return await query.answer("⛔ Нельзя удалить себя.", show_alert=True)

        self.brain.db.log_admin(query.from_user.id, "deleteuser", str(target_id))
        self.brain.db.delete_user(target_id)

        try:
            await query.message.edit_text(
                f"✅ Юзер <code>{target_id}</code> удалён из базы.",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await query.answer("✅ Удалён", show_alert=True)

    async def cb_delete_no(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        try:
            await query.message.edit_text("❌ Удаление отменено.")
        except Exception:
            pass
        await query.answer()

    # ================= ЛОГ =================

    async def cmd_adminlog(self, message: Message):
        if not self._check(message):
            return
        parts = message.text.split()
        limit = 20
        if len(parts) == 2:
            try:
                limit = max(1, min(100, int(parts[1])))
            except ValueError:
                pass

        rows = self.brain.db.get_admin_log(limit)
        if not rows:
            return await message.answer("📜 Лог пуст.")

        lines = [f"📜 <b>Лог команд</b> (последние {len(rows)})\n"]
        import time as _t
        for admin_id, cmd, args, ts in rows:
            date = _t.strftime("%d.%m %H:%M", _t.localtime(ts))
            arg_str = f" <code>{args}</code>" if args else ""
            lines.append(f"<code>{date}</code> — <code>{admin_id}</code> — /{cmd}{arg_str}")

        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:4000] + "\n\n<i>...обрезано</i>"
        await message.answer(text, parse_mode="HTML")

    async def cmd_clearlog(self, message: Message):
        if not self._check(message):
            return
        self.brain.db.clear_admin_log()
        await message.answer("✅ Лог очищен.")

    async def cb_log(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        rows = self.brain.db.get_admin_log(15)
        if not rows:
            text = "📜 Лог пуст."
        else:
            lines = ["📜 <b>Последние команды</b>\n"]
            import time as _t
            for admin_id, cmd, args, ts in rows:
                date = _t.strftime("%d.%m %H:%M", _t.localtime(ts))
                arg_str = f" {args}" if args else ""
                lines.append(f"<code>{date}</code> | {admin_id} | /{cmd}{arg_str}")
            text = "\n".join(lines)
            if len(text) > 4000:
                text = text[:4000] + "\n<i>...обрезано</i>"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

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
            "Когда включён — все юзеры (кроме админов) не могут играть."
        )
        buttons = []
        if maint["enabled"]:
            buttons.append([InlineKeyboardButton(text="✅ Выключить", callback_data="admin_maint_off")])
        else:
            buttons.append([InlineKeyboardButton(text="🛠 Включить", callback_data="admin_maint_on")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

    async def cb_maint_on_start(self, query: CallbackQuery, state: FSMContext):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        await state.set_state(MaintStates.waiting_for_reason)
        text = (
            "🛠 <b>Включение техперерыва</b>\n\n"
            "Напиши причину для юзеров.\n\n"
            "<i>Чтобы отменить — /cancel.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_maint")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

    async def on_maint_reason(self, message: Message, state: FSMContext):
        if not self._check(message):
            return
        reason = (message.text or "").strip()
        if reason.startswith("/"):
            await state.clear()
            return await message.answer("Ок, отменено.")
        if not (3 <= len(reason) <= 200):
            return await message.answer("❌ Причина 3-200 символов.")

        self.brain.db.set_maintenance(True, reason)
        self.brain.db.log_admin(message.from_user.id, "maint_on", reason)
        await state.clear()
        await message.answer(
            f"✅ <b>Техперерыв включён</b>\n\nПричина: <i>{reason}</i>",
            parse_mode="HTML"
        )
        await self._broadcast(
            f"🛠 <b>Технический перерыв</b>\n\nПричина: <i>{reason}</i>\n\nСкоро вернёмся!"
        )

    async def cb_maint_off(self, query: CallbackQuery):
        if not self._check_cb(query):
            return await query.answer("⛔ Нет доступа", show_alert=True)
        self.brain.db.set_maintenance(False, "")
        self.brain.db.log_admin(query.from_user.id, "maint_off", "")
        await query.answer("✅ Техперерыв выключен", show_alert=True)
        await self._broadcast(
            "✅ <b>Технические работы завершены!</b>\n\nСнова всё работает — заходи и играй! 🎰"
        )
        await self.cb_maint(query)

    async def _broadcast(self, text):
        user_ids = self.brain.db.get_all_user_ids()
        sent = 0
        for uid in user_ids:
            if is_admin(uid, self.brain.db):
                continue
            try:
                await self.brain.bot.send_message(uid, text, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
        return sent

    # ================= РАССЫЛКА / КОМПЕНСАЦИЯ =================

    async def cmd_broadcast(self, message: Message):
        if not self._check(message):
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.answer(
                "📢 <code>/broadcast Текст</code>",
                parse_mode="HTML"
            )
        self._log(message)
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
        parts = message.text.split()
        if len(parts) != 3:
            return await message.answer(
                "🎁 <code>/compensate &lt;sc|lc&gt; &lt;amount&gt;</code>",
                parse_mode="HTML"
            )
        self._log(message)
        currency = parts[1].lower()
        if currency not in ("sc", "lc"):
            return await message.answer("❌ Валюта: sc или lc")
        try:
            amount = int(parts[2])
        except ValueError:
            return await message.answer("❌ Сумма — число")
        if amount <= 0:
            return await message.answer("❌ Сумма > 0")

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