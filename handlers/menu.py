import html
from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from utils import (
    format_sc, is_current_screen, nav_footer, safe_answer, with_hero,
)
import time


class DisplayNameStates(StatesGroup):
    waiting_for_name = State()


BUTTONS = {
    "play":     "🎰 Играть",
    "daily":    "🎁 Ежедневно",
    "casino":   "🏢 Моё казино",
    "shop":     "🛒 Магазин",
    "trade":    "💱 Трейд",
    "profile":  "👤 Профиль",
    "top":      "🏆 Лидерборд",
    "inv":      "🎒 Инвентарь",
    "about":    "ℹ️ О боте",
    "settings": "⚙️ Настройки",
    "complaint": "📮 Жалоба",
}


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}с"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"


def _maint_line(brain) -> str:
    try:
        maint = brain.db.get_maintenance()
        if not maint["enabled"]:
            return ""
        elapsed = int(time.time()) - maint["started_at"]
        duration = _fmt_duration(max(0, elapsed))
        reason = maint["reason"] or "ведутся работы"
        return (
            f"\n\n🛠 <b>Технический перерыв</b>\n"
            f"⏳ Длится уже: <b>{duration}</b>\n"
            f"<i>{reason}</i>"
        )
    except Exception:
        return ""


class Menu:
    TOP_SORTS = {
        "sc": ("💰 SC", "SC", " SC"),
        "lc": ("🍀 LC", "LC", " LC"),
        "level": ("⭐ Ур.", "уровню", " ур."),
        "games": ("🎮 Игр", "играм", " игр"),
        "winrate": ("📊 ВР", "винрейту", "%"),
    }

    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.message(Command("start"))(self.cmd_start)
        dp.message(Command("menu"))(self.cmd_start)
        dp.message(Command("version"))(self.cmd_version)
        dp.callback_query(F.data == "profile")(self.cb_profile)
        dp.callback_query(F.data == "top")(self.cb_top)
        dp.callback_query(F.data == "menu")(self.cb_menu)
        dp.callback_query(F.data == "cele_done")(self.cb_cele_done)
        dp.callback_query(F.data == "about")(self.cb_about)
        dp.callback_query(F.data == "settings")(self.cb_settings)
        dp.callback_query(F.data == "set_notif_toggle")(self.cb_notif_toggle)
        dp.callback_query(F.data == "set_display_name")(self.cb_display_name_start)
        dp.callback_query(F.data == "set_fast_anim")(self.cb_fast_anim_toggle)
        dp.message(Command("cancel"), DisplayNameStates.waiting_for_name)(
            self.cb_display_name_cancel
        )
        dp.message(DisplayNameStates.waiting_for_name)(self.on_display_name_input)
        dp.callback_query(F.data == "top_casinos")(self.cb_top_casinos)
        dp.callback_query(
            F.data.in_({f"top_{key}" for key in self.TOP_SORTS})
        )(self.cb_top_sort)

    def main_keyboard(self, user_id):
        from config import TYCOON_ENABLED

        labels = dict(BUTTONS)
        if not TYCOON_ENABLED:
            labels["casino"] = "🚧 Казино (ремонт)"
        buttons = []
        for row in (
            ["play"],
            ["daily"],
            ["casino", "shop"],
            ["trade", "profile"],
            ["top", "inv"],
            ["about", "settings"],
            ["complaint"],
        ):
            line = []
            for key in row:
                if key in labels:
                    line.append(InlineKeyboardButton(text=labels[key], callback_data=key))
            if line:
                buttons.append(line)
        buttons.extend(nav_footer())
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def settings_keyboard(self):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Уведомления", callback_data="set_notif_toggle")],
            [InlineKeyboardButton(text="👤 Отображаемое имя", callback_data="set_display_name")],
            [InlineKeyboardButton(text="⚡ Быстрая анимация", callback_data="set_fast_anim")],
            [InlineKeyboardButton(text="⬅️ Назад",            callback_data="menu")],
        ])

    async def _show_celebration(self, message: Message):
        """Send the one-time 1.0.0 welcome screen."""
        from config import UPDATE_GIF_FILE_ID

        user_id = message.from_user.id
        caption = self.build_celebration_caption(user_id)

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🎰 Вернуться в меню",
                callback_data="cele_done",
            )
        ]])
        try:
            await message.answer_animation(
                animation=UPDATE_GIF_FILE_ID,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception as error:
            try:
                print(f"⚠️ Celebration GIF failed: {error}")
            except Exception:
                pass
            await message.answer(
                caption, reply_markup=kb, parse_mode="HTML"
            )

    def build_celebration_caption(self, user_id: int) -> str:
        """Return the HTML celebration caption for a given user."""
        from config import UPDATE_VERSION

        conv = self.brain.db.get_user_conversion_before(user_id)
        caption = (
            f"🎉 <b>LuckyScoin обновился до v{UPDATE_VERSION}!</b>\n\n"
            "Мы вернулись, и у нас для тебя кое-что есть:\n"
            "🎁 <b>Уникальный титул «Старичок»</b> — только 2 дня "
            "в магазине, успей забрать!\n\n"
        )
        if conv and conv["lc_before"] > 0:
            tiers = conv["tiers"]
            rate_lines = []
            for cap, rate in tiers:
                rate_label = f"{rate:,}".replace(",", " ")
                if cap is None:
                    rate_lines.append(
                        f"• свыше — {rate_label} LC = 1 SC"
                    )
                    break
                rate_lines.append(
                    f"• до {cap:,} LC — {rate_label} LC = 1 SC"
                    .replace(",", " ")
                )
            caption += (
                "💱 <b>Что случилось с твоими LC?</b>\n"
                f"Было: <b>{conv['lc_before']:,} LC</b>"
                .replace(",", " ") + "\n"
                "Переведено по каскадному курсу:\n"
                + "\n".join(rate_lines) + "\n"
                f"Начислено: <b>+{format_sc(conv['sc_gained'])} SC</b>\n\n"
                "<i>Мы сбрасываем экономику, чтобы дать всем равный "
                "старт. Раньше LC было слишком много и они обесценились. "
                "SC — стабильная валюта, ей инфляция не грозит.</i>\n\n"
            )
        caption += "Жми кнопку ниже, чтобы продолжить."
        caption = caption.replace(",", " ")
        return caption

    def _menu_text(self, user_id):
        """Return the HTML text for the main menu."""
        from config import SEASON_DURATION_DAYS

        user = self.brain.db.get_user(user_id)
        body = "🎰 <b>LuckyScoin</b>\n\nВыбери действие:"
        body += _maint_line(self.brain)
        text = with_hero(body, user)

        elapsed = self.brain.db.get_season_elapsed()
        season_num = self.brain.db.get_current_season()
        if elapsed > 0:
            days_left = max(0, SEASON_DURATION_DAYS - elapsed // 86400)
            text = (
                f"🏁 <b>Сезон {season_num}</b> · "
                f"осталось <b>{days_left} дн.</b>\n\n{text}"
            )
        return text

    async def cmd_start(self, message: Message):
        user_id = message.from_user.id
        self.brain.db.record_daily_visit(user_id)
        username = message.from_user.username or message.from_user.first_name or "anon"
        user = self.brain.db.get_user(user_id)
        is_new_user = (
            user["username"] is None
            and user["total_bets"] == 0
            and user["games"] == 0
        )
        self.brain.db.set_username(user_id, username)
        if is_new_user:
            self.brain.db.log_event(user_id, username, "signup", "")
        if not self.brain.db.has_seen_celebration(user_id):
            await self._show_celebration(message)
            return
        text = self._menu_text(user_id)
        state = self.brain.db.get_daily_state(user_id)
        if state["can_claim"]:
            text = "🎁 <b>Ежедневная награда ждёт!</b>\n\n" + text
        await message.answer(text, reply_markup=self.main_keyboard(user_id), parse_mode="HTML")

    async def cmd_version(self, message: Message):
        try:
            from version import format_changelog
            text = format_changelog(limit=3)
        except Exception:
            text = "🎰 <b>LuckyScoin</b> v1.0.0"
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

    async def cb_menu(self, query: CallbackQuery):
        await safe_answer(query)
        user_id = query.from_user.id
        self.brain.db.record_daily_visit(user_id)
        username = query.from_user.username or query.from_user.first_name or "anon"
        self.brain.db.set_username(user_id, username)
        if not self.brain.db.has_seen_celebration(user_id):
            await self._show_celebration(query.message)
            return
        text = self._menu_text(user_id)
        state = self.brain.db.get_daily_state(user_id)
        if state["can_claim"]:
            text = "🎁 <b>Ежедневная награда ждёт!</b>\n\n" + text
        try:
            await query.message.edit_text(text, reply_markup=self.main_keyboard(user_id), parse_mode="HTML")
        except Exception:
            pass

    async def cb_cele_done(self, query: CallbackQuery):
        await safe_answer(query)
        user_id = query.from_user.id
        self.brain.db.mark_celebration_seen(user_id)
        try:
            await query.message.delete()
        except Exception:
            pass
        text = self._menu_text(user_id)
        await query.message.answer(
            text,
            reply_markup=self.main_keyboard(user_id),
            parse_mode="HTML",
        )

    async def cb_about(self, query: CallbackQuery):
        await safe_answer(query)
        try:
            from version import format_changelog
            text = format_changelog(limit=5)
        except Exception:
            text = (
                "🎰 <b>LuckyScoin</b>\n\n"
                "Версия: <b>1.0.0</b>\n\n"
                "<i>Информация о версии недоступна.</i>"
            )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Играть", callback_data="play")],
            [InlineKeyboardButton(text="⬅️ Назад",  callback_data="menu")],
        ] + nav_footer())
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML",
                                          disable_web_page_preview=True)
        except Exception:
            pass

    async def cb_profile(self, query: CallbackQuery, state: FSMContext = None):
        if is_current_screen(query, "profile"):
            return await safe_answer(query, "Уже здесь")
        if state:
            await state.clear()
        await safe_answer(query)
        user_id = query.from_user.id
        username = query.from_user.username or query.from_user.first_name or "anon"
        self.brain.db.set_username(user_id, username)
        u = self.brain.db.get_user(user_id)
        winrate = round(u["wins"] / u["games"] * 100, 1) if u["games"] > 0 else 0
        xp_needed = 100 * (u["level"] + 1)

        casino = self.brain.db.get_casino(user_id)
        casino_block = ""
        if casino:
            income = self.brain.db.get_income_per_hour(user_id)
            pending, _, _ = self.brain.db.get_pending_income(user_id)
            casino_block = f"\n🏢 <b>{casino['name']}</b> (ур. {casino['level']})\n💵 {income} LC/ч"
            if pending > 0:
                casino_block += f" • 💰 {pending} LC к сбору"
            casino_block += "\n"

        badges_block = ""
        try:
            from content.catalog import BADGES
            equipped = self.brain.db.get_user_badges(user_id)
            names = [BADGES[bid]["name"] for bid in equipped.values() if bid and bid in BADGES]
            if names:
                badges_block = "\n🎖 " + " • ".join(names) + "\n"
        except Exception:
            pass

        title_line = f"🏷 {u['title']}\n" if u["title"] else ""
        display_name = str(u.get("display_name") or "").strip()
        name_line = html.escape(display_name) if display_name else f"@{html.escape(str(u['username'] or 'player'))}"
        text = (
            f"👤 {name_line}\n"
            f"{title_line}"
            f"{badges_block}\n"
            f"⭐ Уровень: {u['level']} (XP: {u['xp']}/{xp_needed})\n"
            f"💰 SC: {format_sc(u['sc'])}\n"
            f"🍀 LC: {u['lc']}"
            f"{casino_block}\n"
            f"🎮 Игр: {u['games']}\n"
            f"✅ Побед: {u['wins']}\n"
            f"❌ Проигрышей: {u['losses']}\n"
            f"📊 Винрейт: {winrate}%"
        )
        buttons = []
        if casino:
            buttons.append([InlineKeyboardButton(text="🏢 Открыть казино", callback_data="casino")])
        buttons.append([InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inv")])
        buttons.append([InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")])
        buttons.extend(nav_footer("profile"))
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        except Exception:
            pass

    def _top_kb(self, sort_by):
        sort_buttons = [
            InlineKeyboardButton(
                text=f"{label}{' ✅' if sort_by == key else ''}",
                callback_data=f"top_{key}",
            )
            for key, (label, _, _) in self.TOP_SORTS.items()
        ]
        sort_rows = [sort_buttons[:2], sort_buttons[2:]]
        return InlineKeyboardMarkup(inline_keyboard=[
            *[row for row in sort_rows if row],
            [InlineKeyboardButton(text="🏢 Топ казино", callback_data="top_casinos")],
        ] + nav_footer("top"))

    async def cb_top_casinos(self, query: CallbackQuery):
        await safe_answer(query)
        user_id = query.from_user.id
        data = self.brain.db.top_casinos(10)
        total_active = self.brain.db.count_active_casinos()
        total_all = self.brain.db.count_all_casinos()
        lines = ["🏢 <b>Топ казино</b>\n"]
        if not data:
            lines.append("Пока никто не прокачал своё казино.")
            lines.append(f"<i>Всего открыто: {total_all}</i>")
        else:
            medals = ["🥇", "🥈", "🥉"]
            for i, (uid, uname, title, cname, earned, level) in enumerate(data, 1):
                medal = medals[i - 1] if i <= 3 else f"{i}."
                name = f"@{uname}" if uname else f"ID {uid}"
                income = self.brain.db.get_income_per_hour(uid)
                lines.append(f"{medal} <b>{cname}</b> — ур. {level} ({income} LC/ч)\n    👤 {name} — 💼 {earned} LC")
            lines.append(f"\n📊 Активных казино: <b>{total_active}</b> из {total_all}")
        rank, in_top = self.brain.db.get_user_casino_position(user_id, limit=10)
        if rank is not None and not in_top:
            casino = self.brain.db.get_casino(user_id)
            if casino:
                lines.append(f"\n🎯 <b>Твоё место: #{rank}</b> — «{casino['name']}» (ур. {casino['level']})")
        elif rank is None:
            casino = self.brain.db.get_casino(user_id)
            if casino:
                lines.append(f"\n💤 <i>Твоё казино «{casino['name']}» пока не в рейтинге.</i>")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏢 К казино", callback_data="casino")],
            [InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"top_{next(iter(self.TOP_SORTS))}",
            )],
        ] + nav_footer("top"))
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

    async def cb_top(self, query: CallbackQuery, state: FSMContext = None):
        if is_current_screen(query, "top"):
            return await safe_answer(query, "Уже здесь")
        if state:
            await state.clear()
        await safe_answer(query)
        await self._show_top(query, "sc")

    async def cb_top_sort(self, query: CallbackQuery):
        await safe_answer(query)
        sort_by = query.data.removeprefix("top_")
        if sort_by not in self.TOP_SORTS:
            return
        await self._show_top(query, sort_by)

    async def _show_top(self, query: CallbackQuery, sort_by: str):
        from config import SEASON_DURATION_DAYS

        _, label, unit = self.TOP_SORTS[sort_by]
        caller_id = query.from_user.id
        top_ids = set()
        elapsed = self.brain.db.get_season_elapsed()
        days_left = max(
            0, SEASON_DURATION_DAYS - elapsed // 86400
        )
        remaining = "&lt; 1" if days_left == 0 else str(days_left)
        season_line = (
            f"🏁 Сезон {self.brain.db.get_current_season()} · "
            f"осталось {remaining} дн.\n\n"
        )
        if sort_by == "winrate":
            data = getattr(self.brain.db, f"top_{sort_by}")(10)
            lines = [
                season_line + f"🏆 <b>Топ по {label}</b> (мин 10 игр)\n"
            ]
            if not data:
                lines.append("Пока пусто.")
            medals = ["🥇", "🥈", "🥉"]
            for i, (uname, uid, wins, games, wr, title) in enumerate(data, 1):
                top_ids.add(uid)
                medal = medals[i - 1] if i <= 3 else f"{i}."
                name = f"@{uname}" if uname else f"ID {uid}"
                if uid == caller_id:
                    name = f"👉 {name} 👈"
                title_text = f" {html.escape(title)}" if title else ""
                wins_text = f"{wins:,}".replace(",", " ")
                games_text = f"{games:,}".replace(",", " ")
                lines.append(
                    f"{medal} {name}{title_text} — {wr}% "
                    f"({wins_text}/{games_text})"
                )

            if caller_id not in top_ids:
                rank_data = self.brain.db.get_user_rank_winrate(caller_id)
                if rank_data is None:
                    lines.append(
                        "\n🎯 <b>Ты</b> — нужен минимум 10 игр для рейтинга"
                    )
                else:
                    rank, winrate, wins, games, total = rank_data
                    lines.extend([
                        "\n┈┈┈┈┈┈┈┈┈┈",
                        f"🎯 <b>Ты</b> — #{rank} из {total} · "
                        f"📊 {winrate}% "
                        f"({wins:,}/{games:,})".replace(",", " "),
                    ])
                    if 10 < rank <= 13:
                        places = rank - 10
                        place_word = (
                            "место" if places == 1
                            else "места" if places in (2, 3, 4)
                            else "мест"
                        )
                        lines.append(
                            f"<i>💡 До топ-10: ещё {places} "
                            f"{place_word}!</i>"
                        )
        else:
            data = self.brain.db.top_by(sort_by, 10)
            lines = [season_line + f"🏆 <b>Топ по {label}</b>\n"]
            if not data:
                lines.append("Пусто.")
            medals = ["🥇", "🥈", "🥉"]
            for i, (uname, uid, val, title) in enumerate(data, 1):
                top_ids.add(uid)
                medal = medals[i - 1] if i <= 3 else f"{i}."
                name = f"@{uname}" if uname else f"ID {uid}"
                if uid == caller_id:
                    name = f"👉 {name} 👈"
                title_text = f" {html.escape(title)}" if title else ""
                value = (
                    format_sc(val) if sort_by == "sc"
                    else f"{val:,}".replace(",", " ")
                )
                lines.append(
                    f"{medal} {name}{title_text} — {value}{unit}"
                )

            if caller_id not in top_ids:
                rank, value, total = self.brain.db.get_user_rank(
                    caller_id, sort_by
                )
                if rank is not None:
                    if sort_by == "sc":
                        value_text = f"💰 {format_sc(value)}"
                    elif sort_by == "lc":
                        value = f"{value:,}".replace(",", " ")
                        value_text = f"🍀 {value}"
                    elif sort_by == "level":
                        value = f"{value:,}".replace(",", " ")
                        value_text = f"⭐ {value} ур."
                    else:
                        value = f"{value:,}".replace(",", " ")
                        value_text = f"🎮 {value} игр"
                    lines.extend([
                        "\n┈┈┈┈┈┈┈┈┈┈",
                        f"🎯 <b>Ты</b> — #{rank} из {total} · "
                        f"{value_text}",
                    ])
                    if 10 < rank <= 13:
                        places = rank - 10
                        place_word = (
                            "место" if places == 1
                            else "места" if places in (2, 3, 4)
                            else "мест"
                        )
                        lines.append(
                            f"<i>💡 До топ-10: ещё {places} "
                            f"{place_word}!</i>"
                        )
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=self._top_kb(sort_by), parse_mode="HTML")
        except Exception:
            pass

    async def cb_settings(self, query: CallbackQuery):
        await safe_answer(query)
        user_id = query.from_user.id
        text = self.settings_text(user_id)
        try:
            await query.message.edit_text(text, reply_markup=self.settings_keyboard(), parse_mode="HTML")
        except Exception:
            pass

    def settings_text(self, user_id):
        notif_enabled = self.brain.db.get_flag(f"notif:{user_id}", "1") == "1"
        fast_anim = self.brain.db.get_fast_anim(user_id) == 1
        return (
            "⚙️ <b>Настройки</b>\n\n"
            f"🔔 Уведомления: {'включены' if notif_enabled else 'выключены'}\n"
            f"⚡ Быстрая анимация: {'включена' if fast_anim else 'выключена'}\n\n"
            "Выбери, что изменить:"
        )

    async def cb_notif_toggle(self, query: CallbackQuery):
        user_id = query.from_user.id
        flag_key = f"notif:{user_id}"
        enabled = self.brain.db.get_flag(flag_key, "1") != "1"
        self.brain.db.set_flag(flag_key, "1" if enabled else "0")
        status = "включены" if enabled else "выключены"
        await safe_answer(query, f"🔔 Уведомления {status}")
        try:
            await query.message.edit_text(
                self.settings_text(user_id),
                reply_markup=self.settings_keyboard(),
                parse_mode="HTML",
            )
        except Exception:
            pass

    async def cb_display_name_start(self, query: CallbackQuery, state: FSMContext):
        await state.set_state(DisplayNameStates.waiting_for_name)
        await safe_answer(query)
        await query.message.answer(
            "👤 Отправь отображаемое имя длиной от 3 до 20 символов.\n"
            "Для отмены отправь /cancel."
        )

    async def on_display_name_input(self, message: Message, state: FSMContext):
        name = (message.text or "").strip()
        if not 3 <= len(name) <= 20:
            return await message.answer(
                "❌ Имя должно содержать от 3 до 20 символов. Попробуй ещё раз или отправь /cancel."
            )
        self.brain.db.set_display_name(message.from_user.id, name)
        await state.clear()
        await message.answer(f"✅ Отображаемое имя сохранено: {html.escape(name)}", parse_mode="HTML")

    async def cb_display_name_cancel(self, message: Message, state: FSMContext):
        await state.clear()
        await message.answer("Изменение отображаемого имени отменено.")

    async def cb_fast_anim_toggle(self, query: CallbackQuery):
        user_id = query.from_user.id
        enabled = self.brain.db.get_fast_anim(user_id) != 1
        self.brain.db.set_fast_anim(user_id, int(enabled))
        response = (
            "✅ Быстрая анимация включена"
            if enabled else "⚠️ Роллы будут медленнее"
        )
        await safe_answer(query, response, show_alert=not enabled)
        try:
            await query.message.edit_text(
                self.settings_text(user_id),
                reply_markup=self.settings_keyboard(),
                parse_mode="HTML",
            )
        except Exception:
            pass