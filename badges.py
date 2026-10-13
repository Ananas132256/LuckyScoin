from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


# ============================================================
#  МЕДАЛИ
# ============================================================
# Структура:
#   name    — название с эмодзи
#   desc    — описание
#   rarity  — common / rare / epic / legendary
#   unlock  — условие открытия:
#             {}               — доступна всем
#             {"level": 5}     — по уровню
#             {"sc": 1000}     — по балансу SC
#             {"games": 100}   — по количеству игр
#             {"room_level": 3}— по уровню казино

BADGES = {
    "rookie": {
        "name": "🎲 Новичок",
        "desc": "Первый шаг в LuckyScoin",
        "rarity": "common",
        "unlock": {},
    },
    "lucky": {
        "name": "🍀 Везунчик",
        "desc": "Открывается с 5 уровня",
        "rarity": "common",
        "unlock": {"level": 5},
    },
    "grinder": {
        "name": "⛏️ Старатель",
        "desc": "Открывается с 10 уровня",
        "rarity": "rare",
        "unlock": {"level": 10},
    },
    "player": {
        "name": "🎮 Игрок",
        "desc": "Сыграй 100 игр",
        "rarity": "rare",
        "unlock": {"games": 100},
    },
    "high_roller": {
        "name": "💎 Хайроллер",
        "desc": "Открывается с 25 уровня",
        "rarity": "rare",
        "unlock": {"level": 25},
    },
    "tycoon": {
        "name": "🏢 Магнат",
        "desc": "Открой зал №3 в своём казино",
        "rarity": "epic",
        "unlock": {"room_level": 3},
    },
    "rich": {
        "name": "💰 Богач",
        "desc": "Накопи 5 000 SC",
        "rarity": "epic",
        "unlock": {"sc": 5000},
    },
    "legend": {
        "name": "👑 Легенда",
        "desc": "Открывается с 50 уровня",
        "rarity": "epic",
        "unlock": {"level": 50},
    },
    "whale": {
        "name": "🐋 Кит",
        "desc": "Накопи 50 000 SC",
        "rarity": "legendary",
        "unlock": {"sc": 50000},
    },
    "immortal": {
        "name": "🔱 Бессмертный",
        "desc": "Открывается с 100 уровня",
        "rarity": "legendary",
        "unlock": {"level": 100},
    },
}


RARITY_EMOJI = {
    "common":    "⚪",
    "rare":      "🔵",
    "epic":      "🟣",
    "legendary": "🟡",
}


def slots_for_level(level: int) -> int:
    """Сколько ячеек открыто на этом уровне."""
    if level < 5:
        return 0
    if level < 25:
        return 3
    if level < 100:
        return 4
    return 5


class Badges:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "badges")(self.cb_badges)
        dp.callback_query(F.data.startswith("badge_slot_"))(self.cb_slot)
        dp.callback_query(F.data.startswith("badge_pick_"))(self.cb_pick)
        dp.callback_query(F.data.startswith("badge_remove_"))(self.cb_remove)

    # ---------- ХЕЛПЕРЫ ----------

    def _user_level(self, user_id):
        level, _ = self.brain.db.get_level_xp(user_id)
        return level

    def _owned_ids(self, user_id):
        """Медали, доступные игроку по условиям unlock."""
        u = self.brain.db.get_user(user_id)
        rooms = self.brain.db.get_rooms(user_id) or []
        room_level = max(rooms) if rooms else 0

        owned = set()
        for bid, b in BADGES.items():
            unlock = b.get("unlock", {})
            if "level" in unlock and u["level"] < unlock["level"]:
                continue
            if "sc" in unlock and u["sc"] < unlock["sc"]:
                continue
            if "lc" in unlock and u["lc"] < unlock["lc"]:
                continue
            if "games" in unlock and u["games"] < unlock["games"]:
                continue
            if "room_level" in unlock and room_level < unlock["room_level"]:
                continue
            owned.add(bid)
        return owned

    def _equipped(self, user_id):
        return self.brain.db.get_user_badges(user_id)

    # ---------- ГЛАВНЫЙ ЭКРАН ----------

    def _main_kb(self, user_id):
        level = self._user_level(user_id)
        total = slots_for_level(level)
        equipped = self._equipped(user_id)
        unlock_levels = [5, 5, 5, 25, 100]
        buttons = []

        for slot in range(5):
            if slot >= total:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 Ячейка {slot + 1} (с {unlock_levels[slot]} ур.)",
                    callback_data="locked"
                )])
                continue
            bid = equipped.get(slot)
            if bid:
                text = f"{slot + 1}. {BADGES[bid]['name']}"
            else:
                text = f"➕ Ячейка {slot + 1} (пусто)"
            buttons.append([InlineKeyboardButton(
                text=text,
                callback_data=f"badge_slot_{slot}"
            )])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def cb_badges(self, query: CallbackQuery):
        user_id = query.from_user.id
        level = self._user_level(user_id)

        if level < 5:
            text = (
                "🏅 <b>Медальки</b>\n\n"
                "🔒 Доступно с <b>5 уровня</b>.\n"
                f"Твой уровень: <b>{level}</b>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]
            ])
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
            return await query.answer()

        total = slots_for_level(level)
        owned = self._owned_ids(user_id)
        equipped = self._equipped(user_id)

        lines = [
            "🏅 <b>Медальки</b>\n",
            f"⭐ Уровень: <b>{level}</b> • Ячеек: <b>{total}/5</b>",
            f"🎖 Открыто: <b>{len(owned)}/{len(BADGES)}</b>\n",
        ]
        for slot in range(total):
            bid = equipped.get(slot)
            if bid:
                lines.append(f"{slot + 1}. {BADGES[bid]['name']}")
            else:
                lines.append(f"{slot + 1}. <i>пусто</i>")

        text = "\n".join(lines) + "\n\nВыбери ячейку, чтобы надеть/сменить медаль."

        try:
            await query.message.edit_text(text, reply_markup=self._main_kb(user_id), parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

    # ---------- ВЫБОР В ЯЧЕЙКУ ----------

    async def cb_slot(self, query: CallbackQuery):
        try:
            slot = int(query.data.replace("badge_slot_", ""))
        except ValueError:
            return await query.answer("Ошибка", show_alert=True)

        user_id = query.from_user.id
        level = self._user_level(user_id)
        total = slots_for_level(level)
        if slot >= total:
            return await query.answer("Ячейка заблокирована", show_alert=True)

        owned = self._owned_ids(user_id)
        equipped = self._equipped(user_id)

        if not owned:
            return await query.answer("У тебя пока нет медалей", show_alert=True)

        buttons = []
        for bid in owned:
            b = BADGES[bid]
            mark = " ✅" if equipped.get(slot) == bid else ""
            r = RARITY_EMOJI.get(b["rarity"], "⚪")
            buttons.append([InlineKeyboardButton(
                text=f"{r} {b['name']}{mark}",
                callback_data=f"badge_pick_{slot}_{bid}"
            )])

        current = equipped.get(slot)
        if current:
            buttons.append([InlineKeyboardButton(
                text="❌ Снять медаль",
                callback_data=f"badge_remove_{slot}"
            )])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="badges")])

        text = (
            f"🏅 <b>Ячейка {slot + 1}</b>\n\n"
            f"Доступно медалей: <b>{len(owned)}</b>\n\n"
            "<i>Нажми на медаль, чтобы надеть её.</i>"
        )
        try:
            await query.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except Exception:
            pass
        await query.answer()

    # ---------- НАДЕТЬ ----------

    async def cb_pick(self, query: CallbackQuery):
        # badge_pick_{slot}_{badge_id}
        parts = query.data.split("_", 3)
        if len(parts) != 4:
            return await query.answer("Ошибка", show_alert=True)
        try:
            slot = int(parts[2])
        except ValueError:
            return await query.answer("Ошибка", show_alert=True)
        bid = parts[3]

        user_id = query.from_user.id
        if bid not in BADGES:
            return await query.answer("Медаль не найдена", show_alert=True)

        if bid not in self._owned_ids(user_id):
            return await query.answer("Медаль ещё не открыта", show_alert=True)

        self.brain.db.set_user_badge(user_id, slot, bid)
        await query.answer(f"✅ Надето: {BADGES[bid]['name']}")

        query.data = f"badge_slot_{slot}"
        await self.cb_slot(query)

    # ---------- СНЯТЬ ----------

    async def cb_remove(self, query: CallbackQuery):
        try:
            slot = int(query.data.replace("badge_remove_", ""))
        except ValueError:
            return await query.answer("Ошибка", show_alert=True)
        user_id = query.from_user.id
        self.brain.db.remove_user_badge(user_id, slot)
        await query.answer("❌ Медаль снята")
        query.data = f"badge_slot_{slot}"
        await self.cb_slot(query)