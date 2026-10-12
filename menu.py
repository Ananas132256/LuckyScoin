from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


BUTTONS = {
    "play":     "🎰 Играть",
    "casino":   "🏢 Моё казино",
    "shop":     "🛒 Магазин",
    "trade":    "💱 Трейд",
    "profile":  "👤 Профиль",
    "top":      "🏆 Лидерборд",
    "settings": "⚙️ Настройки",
}

LAYOUTS = {
    "classic": {
        "name": "🎰 Классика",
        "rows": [["play"], ["casino", "shop"], ["trade", "profile"], ["top", "settings"]],
    },
    "compact": {
        "name": "📦 Компакт",
        "rows": [["play", "casino"], ["shop", "trade"], ["profile", "top"], ["settings"]],
    },
    "social": {
        "name": "👤 Социальный",
        "rows": [["profile", "top"], ["trade", "casino"], ["play"], ["shop", "settings"]],
    },
    "competitive": {
        "name": "🏆 Соревновательный",
        "rows": [["top", "play"], ["casino", "trade"], ["profile", "shop"], ["settings"]],
    },
    "minimal": {
        "name": "🎯 Минимал",
        "rows": [["play"], ["casino"], ["profile"]],
    },
}

TITLES = [
    ("🎲 Новичок", 0),
    ("🍀 Везунчик", 5),
    ("💎 Богач", 25),
    ("🔥 Хайроллер", 50),
    ("👑 Легенда", 100),
]


async def safe_answer(query, *args, **kwargs):
    try:
        await query.answer(*args, **kwargs)
    except Exception:
        pass


class Menu:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.message(Command("start"))(self.cmd_start)
        dp.message(Command("menu"))(self.cmd_start)
        dp.callback_query(F.data == "profile")(self.cb_profile)
        dp.callback_query(F.data == "top")(self.cb_top)
        dp.callback_query(F.data == "menu")(self.cb_menu)
        dp.callback_query(F.data == "settings")(self.cb_settings)
        dp.callback_query(F.data == "set_layout_menu")(self.cb_layouts)
        dp.callback_query(F.data.startswith("set_layout_"))(self.cb_set_layout)
        dp.callback_query(F.data == "set_titles_menu")(self.cb_titles)
        dp.callback_query(F.data.startswith("set_title_"))(self.cb_set_title)
        dp.callback_query(F.data == "top_casinos")(self.cb_top_casinos)
        dp.callback_query(F.data.in_({"top_sc", "top_lc", "top_level", "top_games", "top_winrate"}))(self.cb_top_sort)

    def main_keyboard(self, user_id):
        layout_key = self.brain.db.get_layout(user_id)
        layout = LAYOUTS.get(layout_key, LAYOUTS["classic"])
        buttons = []
        for row in layout["rows"]:
            line = []
            for key in row:
                if key in BUTTONS:
                    line.append(InlineKeyboardButton(text=BUTTONS[key], callback_data=key))
            if line:
                buttons.append(line)
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def settings_keyboard(self):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Раскладка кнопок", callback_data="set_layout_menu")],
            [InlineKeyboardButton(text="🏷 Титулы",           callback_data="set_titles_menu")],
            [InlineKeyboardButton(text="⬅️ Назад",            callback_data="menu")],
        ])

    def layout_keyboard(self, current):
        buttons = []
        for key, data in LAYOUTS.items():
            mark = " ✅" if key == current else ""
            buttons.append([InlineKeyboardButton(text=data["name"] + mark, callback_data=f"set_layout_{key}")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def titles_keyboard(self, user_level, current_title):
        buttons = []
        for idx, (title, req_level) in enumerate(TITLES):
            if user_level >= req_level:
                mark = " ✅" if title == current_title else ""
                buttons.append([InlineKeyboardButton(text=title + mark, callback_data=f"set_title_{idx}")])
            else:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 {title} (с {req_level} ур.)",
                    callback_data=f"set_title_{idx}"
                )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def cmd_start(self, message: Message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or "anon"
        self.brain.db.set_username(user_id, username)
        await message.answer(
            "Добро пожаловать в LuckyScoin 🎰\nВыбери действие:",
            reply_markup=self.main_keyboard(user_id)
        )

    async def cb_menu(self, query: CallbackQuery):
        await safe_answer(query)
        user_id = query.from_user.id
        username = query.from_user.username or query.from_user.first_name or "anon"
        self.brain.db.set_username(user_id, username)
        u = self.brain.db.get_user(user_id)
        xp_needed = 100 * (u["level"] + 1)
        filled = max(0, min(10, int(u["xp"] / xp_needed * 10)))
        bar = "▰" * filled + "▱" * (10 - filled)
        percent = int(u["xp"] / xp_needed * 100)
        text = (
            f"🎰 <b>LuckyScoin</b>\n\n"
            f"👤 @{u['username']}  •  🏷 {u['title']}\n"
            f"⭐ Ур. <b>{u['level']}</b>\n"
            f"<code>{bar}</code> {percent}%\n"
            f"XP: {u['xp']}/{xp_needed}\n\n"
            f"💰 SC: <b>{u['sc']}</b>\n"
            f"🍀 LC: <b>{u['lc']}</b>\n\n"
            f"Выбери действие:"
        )
        try:
            await query.message.edit_text(text, reply_markup=self.main_keyboard(user_id), parse_mode="HTML")
        except Exception:
            pass

    async def cb_profile(self, query: CallbackQuery):
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
        text = (
            f"👤 @{u['username']}\n"
            f"🏷 {u['title']}\n\n"
            f"⭐ Уровень: {u['level']} (XP: {u['xp']}/{xp_needed})\n"
            f"💰 SC: {u['sc']}\n"
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
        buttons.append([InlineKeyboardButton(text="⬅️ Назад",     callback_data="menu")])
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        except Exception:
            pass

    def _top_kb(self, sort_by):
        def mark(x):
            return " ✅" if sort_by == x else ""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 SC{mark('sc')}", callback_data="top_sc"),
             InlineKeyboardButton(text=f"🍀 LC{mark('lc')}", callback_data="top_lc")],
            [InlineKeyboardButton(text=f"⭐ Ур.{mark('level')}", callback_data="top_level"),
             InlineKeyboardButton(text=f"🎮 Игр{mark('games')}", callback_data="top_games"),
             InlineKeyboardButton(text=f"📊 ВР{mark('winrate')}", callback_data="top_winrate")],
            [InlineKeyboardButton(text="🏢 Топ казино", callback_data="top_casinos")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
        ])

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
            [InlineKeyboardButton(text="⬅️ Назад",   callback_data="top_sc")],
        ])
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

    async def cb_top(self, query: CallbackQuery):
        await safe_answer(query)
        await self._show_top(query, "sc")

    async def cb_top_sort(self, query: CallbackQuery):
        await safe_answer(query)
        sort_by = query.data.replace("top_", "")
        if sort_by not in ("sc", "lc", "level", "games", "winrate"):
            return
        await self._show_top(query, sort_by)

    async def _show_top(self, query: CallbackQuery, sort_by: str):
        if sort_by == "winrate":
            data = self.brain.db.top_winrate(10)
            lines = ["🏆 <b>Топ по винрейту</b> (мин 10 игр)\n"]
            if not data:
                lines.append("Пока пусто.")
            medals = ["🥇", "🥈", "🥉"]
            for i, (uname, uid, wins, games, wr, title) in enumerate(data, 1):
                medal = medals[i - 1] if i <= 3 else f"{i}."
                name = f"@{uname}" if uname else f"ID {uid}"
                lines.append(f"{medal} {name} — {wr}% ({wins}/{games})")
        else:
            data = self.brain.db.top_by(sort_by, 10)
            label = {"sc": "SC", "lc": "LC", "level": "уровню", "wins": "победам", "games": "играм"}.get(sort_by, sort_by)
            lines = [f"🏆 <b>Топ по {label}</b>\n"]
            if not data:
                lines.append("Пусто.")
            medals = ["🥇", "🥈", "🥉"]
            for i, (uname, uid, val, title) in enumerate(data, 1):
                medal = medals[i - 1] if i <= 3 else f"{i}."
                name = f"@{uname}" if uname else f"ID {uid}"
                lines.append(f"{medal} {name} — {val}")
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=self._top_kb(sort_by), parse_mode="HTML")
        except Exception:
            pass

    async def cb_settings(self, query: CallbackQuery):
        await safe_answer(query)
        user_id = query.from_user.id
        layout_key = self.brain.db.get_layout(user_id)
        title = self.brain.db.get_title(user_id)
        layout_name = LAYOUTS.get(layout_key, LAYOUTS["classic"])["name"]
        text = f"⚙️ <b>Настройки</b>\n\n🎨 Раскладка: {layout_name}\n🏷 Титул: {title}\n\nВыбери, что изменить:"
        try:
            await query.message.edit_text(text, reply_markup=self.settings_keyboard(), parse_mode="HTML")
        except Exception:
            pass

    async def cb_layouts(self, query: CallbackQuery):
        await safe_answer(query)
        user_id = query.from_user.id
        current = self.brain.db.get_layout(user_id)
        try:
            await query.message.edit_text(
                "🎨 <b>Выбери раскладку кнопок:</b>\n\nОна определяет, как расположены кнопки в главном меню.",
                reply_markup=self.layout_keyboard(current),
                parse_mode="HTML"
            )
        except Exception:
            pass

    async def cb_set_layout(self, query: CallbackQuery):
        key = query.data.replace("set_layout_", "")
        if key not in LAYOUTS:
            return await safe_answer(query, "❌ Неизвестная раскладка", show_alert=True)
        self.brain.db.set_layout(query.from_user.id, key)
        await safe_answer(query, f"✅ Раскладка: {LAYOUTS[key]['name']}")
        await self.cb_layouts(query)

    async def cb_titles(self, query: CallbackQuery):
        await safe_answer(query)
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        current = self.brain.db.get_title(user_id)
        try:
            await query.message.edit_text(
                f"🏷 <b>Титулы</b>\n\nТвой уровень: {level}\nТитулы открываются по мере прокачки.\nЭксклюзивные титулы можно купить в магазине за SC.",
                reply_markup=self.titles_keyboard(level, current),
                parse_mode="HTML"
            )
        except Exception:
            pass

    async def cb_set_title(self, query: CallbackQuery):
        try:
            idx = int(query.data.replace("set_title_", ""))
        except ValueError:
            return await safe_answer(query, "❌ Ошибка", show_alert=True)
        title, req_level = TITLES[idx]
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        if level < req_level:
            return await safe_answer(query, f"🔒 Нужен уровень {req_level}!", show_alert=True)
        self.brain.db.set_title(user_id, title)
        await safe_answer(query, f"✅ Титул: {title}")
        await self.cb_titles(query)