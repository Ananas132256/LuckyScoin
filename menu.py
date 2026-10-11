from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


<<<<<<< HEAD
=======
# Все возможные кнопки главного меню
BUTTONS = {
    "play":     "🎰 Играть",
    "profile":  "👤 Профиль",
    "top":      "🏆 Лидерборд",
    "settings": "⚙️ Настройки",
}

# Шаблоны раскладок
LAYOUTS = {
    "classic":     {"name": "🎰 Классика",          "order": ["play", "profile", "top", "settings"]},
    "social":      {"name": "👤 Социальный",        "order": ["profile", "top", "play", "settings"]},
    "competitive": {"name": "🏆 Соревновательный",  "order": ["top", "play", "profile", "settings"]},
    "minimal":     {"name": "🎯 Минимал",           "order": ["play", "profile"]},
}

# Титулы: название → нужный уровень
TITLES = [
    ("🎲 Новичок", 0),
    ("🍀 Везунчик", 5),
    ("💎 Богач", 25),
    ("🔥 Хайроллер", 50),
    ("👑 Легенда", 100),
]


>>>>>>> 76f277e (<f>)
class Menu:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.message(Command("start"))(self.cmd_start)
        dp.callback_query(F.data == "profile")(self.cb_profile)
        dp.callback_query(F.data == "top")(self.cb_top)
        dp.callback_query(F.data == "menu")(self.cb_menu)
<<<<<<< HEAD

    def main_keyboard(self):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Играть", callback_data="play")],
            [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton(text="🏆 Лидерборд", callback_data="top")],
        ])
        return kb
=======
        dp.callback_query(F.data == "settings")(self.cb_settings)
        dp.callback_query(F.data == "set_layout_menu")(self.cb_layouts)
        dp.callback_query(F.data.startswith("set_layout_"))(self.cb_set_layout)
        dp.callback_query(F.data == "set_titles_menu")(self.cb_titles)
        dp.callback_query(F.data.startswith("set_title_"))(self.cb_set_title)

    # ---------- КЛАВИАТУРЫ ----------

    def main_keyboard(self, user_id):
        layout_key = self.brain.db.get_layout(user_id)
        order = LAYOUTS.get(layout_key, LAYOUTS["classic"])["order"]

        buttons = [[InlineKeyboardButton(text=BUTTONS[key], callback_data=key)] for key in order]
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

    # ---------- ГЛАВНОЕ МЕНЮ ----------
>>>>>>> 76f277e (<f>)

    async def cmd_start(self, message: Message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or "anon"
        self.brain.db.set_username(user_id, username)
        await message.answer(
            "Добро пожаловать в LuckyScoin 🎰\nВыбери действие:",
<<<<<<< HEAD
            reply_markup=self.main_keyboard()
=======
            reply_markup=self.main_keyboard(user_id)
>>>>>>> 76f277e (<f>)
        )

    async def cb_menu(self, query: CallbackQuery):
        await query.message.edit_text(
            "Главное меню:",
<<<<<<< HEAD
            reply_markup=self.main_keyboard()
        )
        await query.answer()

=======
            reply_markup=self.main_keyboard(query.from_user.id)
        )
        await query.answer()

    # ---------- ПРОФИЛЬ ----------

>>>>>>> 76f277e (<f>)
    async def cb_profile(self, query: CallbackQuery):
        user_id = query.from_user.id
        username = query.from_user.username or query.from_user.first_name or "anon"
        self.brain.db.set_username(user_id, username)
        u = self.brain.db.get_user(user_id)
<<<<<<< HEAD
        if u["games"] > 0:
            winrate = round(u["wins"] / u["games"] * 100, 1)
        else:
            winrate = 0
        xp_needed = 100 * (u["level"] + 1)
        text = (
            f"👤 @{u['username']}\n\n"
=======

        winrate = round(u["wins"] / u["games"] * 100, 1) if u["games"] > 0 else 0
        xp_needed = 100 * (u["level"] + 1)

        text = (
            f"👤 @{u['username']}\n"
            f"🏷 {u['title']}\n\n"
>>>>>>> 76f277e (<f>)
            f"⭐ Уровень: {u['level']} (XP: {u['xp']}/{xp_needed})\n\n"
            f"💰 SC: {u['sc']}\n"
            f"🍀 LC: {u['lc']}\n\n"
            f"🎮 Игр: {u['games']}\n"
            f"✅ Побед: {u['wins']}\n"
            f"❌ Проигрышей: {u['losses']}\n"
            f"📊 Винрейт: {winrate}%"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
<<<<<<< HEAD
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]
=======
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
            [InlineKeyboardButton(text="⬅️ Назад",     callback_data="menu")],
>>>>>>> 76f277e (<f>)
        ])
        await query.message.edit_text(text, reply_markup=kb)
        await query.answer()

<<<<<<< HEAD
=======
    # ---------- ЛИДЕРБОРД ----------

>>>>>>> 76f277e (<f>)
    async def cb_top(self, query: CallbackQuery):
        top = self.brain.db.top_balances(10)
        if not top:
            text = "Пока никого нет в топе."
        else:
            lines = ["🏆 Топ игроков:\n"]
            for i, (username, uid, sc) in enumerate(top, 1):
                name = f"@{username}" if username else f"ID {uid}"
                lines.append(f"{i}. {name} — {sc} SC")
            text = "\n".join(lines)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]
        ])
        await query.message.edit_text(text, reply_markup=kb)
<<<<<<< HEAD
        await query.answer()
=======
        await query.answer()

    # ---------- НАСТРОЙКИ ----------

    async def cb_settings(self, query: CallbackQuery):
        user_id = query.from_user.id
        layout_key = self.brain.db.get_layout(user_id)
        title = self.brain.db.get_title(user_id)
        layout_name = LAYOUTS.get(layout_key, LAYOUTS["classic"])["name"]

        text = (
            "⚙️ **Настройки**\n\n"
            f"🎨 Раскладка: {layout_name}\n"
            f"🏷 Титул: {title}\n\n"
            "Выбери, что изменить:"
        )
        await query.message.edit_text(
            text, reply_markup=self.settings_keyboard(), parse_mode="Markdown"
        )
        await query.answer()

    async def cb_layouts(self, query: CallbackQuery):
        user_id = query.from_user.id
        current = self.brain.db.get_layout(user_id)
        await query.message.edit_text(
            "🎨 **Выбери раскладку кнопок:**\n\n"
            "Она определяет, в каком порядке кнопки показываются в главном меню.",
            reply_markup=self.layout_keyboard(current),
            parse_mode="Markdown"
        )
        await query.answer()

    async def cb_set_layout(self, query: CallbackQuery):
        key = query.data.replace("set_layout_", "")
        if key not in LAYOUTS:
            return await query.answer("❌ Неизвестная раскладка", show_alert=True)

        self.brain.db.set_layout(query.from_user.id, key)
        await query.answer(f"✅ Раскладка: {LAYOUTS[key]['name']}")
        await self.cb_layouts(query)

    async def cb_titles(self, query: CallbackQuery):
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        current = self.brain.db.get_title(user_id)
        await query.message.edit_text(
            f"🏷 **Титулы**\n\nТвой уровень: {level}\n"
            "Титулы открываются по мере прокачки.",
            reply_markup=self.titles_keyboard(level, current),
            parse_mode="Markdown"
        )
        await query.answer()

    async def cb_set_title(self, query: CallbackQuery):
        try:
            idx = int(query.data.replace("set_title_", ""))
        except ValueError:
            return await query.answer("❌ Ошибка", show_alert=True)

        title, req_level = TITLES[idx]
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)

        if level < req_level:
            return await query.answer(f"🔒 Нужен уровень {req_level}!", show_alert=True)

        self.brain.db.set_title(user_id, title)
        await query.answer(f"✅ Титул: {title}")
        await self.cb_titles(query)
>>>>>>> 76f277e (<f>)
