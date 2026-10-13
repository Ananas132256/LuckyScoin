from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from cosmetics import (
    BADGES, TITLES, RARITY_EMOJI, badge_slots_for_level,
    is_unlocked, describe_effect,
)


class Inventory:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "inv")(self.cb_inv)
        dp.callback_query(F.data == "inv_badges")(self.cb_badges)
        dp.callback_query(F.data == "inv_titles")(self.cb_titles)
        dp.callback_query(F.data.startswith("inv_slot_"))(self.cb_slot)
        dp.callback_query(F.data.startswith("inv_badge_pick_"))(self.cb_badge_pick)
        dp.callback_query(F.data.startswith("inv_badge_remove_"))(self.cb_badge_remove)
        dp.callback_query(F.data.startswith("inv_title_pick_"))(self.cb_title_pick)

    def _ctx(self, user_id):
        u = self.brain.db.get_user(user_id)
        rooms = self.brain.db.get_rooms(user_id) or []
        room_level = max(rooms) if rooms else 0
        return u, room_level

    def _owned(self, pool: dict, u: dict, room_level: int):
        return {bid for bid, b in pool.items() if is_unlocked(b, u, room_level)}

    async def cb_inv(self, query: CallbackQuery):
        user_id = query.from_user.id
        u, room_level = self._ctx(user_id)

        equipped = self.brain.db.get_user_badges(user_id)
        badge_names = [BADGES[b]["name"] for b in equipped.values()
                       if b and b in BADGES]
        title_name = self.brain.db.get_title(user_id)

        effects = self.brain.db.get_active_effects(user_id)
        effects_line = describe_effect(effects)

        owned_badges = self._owned(BADGES, u, room_level)
        owned_titles = self._owned(TITLES, u, room_level)

        badges_line = " • ".join(badge_names) if badge_names else "<i>пусто</i>"

        text = (
            "🎒 <b>Инвентарь</b>\n\n"
            f"🏷 Титул: <b>{title_name}</b>\n"
            f"🏅 Значки: {badges_line}\n\n"
            f"✨ <b>Активные эффекты:</b>\n<i>{effects_line}</i>\n\n"
            f"📦 Открыто: 🏷 {len(owned_titles)}/{len(TITLES)}  •  🏅 {len(owned_badges)}/{len(BADGES)}\n\n"
            "Выбери раздел:"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏅 Значки (баффы)", callback_data="inv_badges")],
            [InlineKeyboardButton(text="🏷 Титулы",         callback_data="inv_titles")],
            [InlineKeyboardButton(text="⬅️ Назад",         callback_data="menu")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

    async def cb_badges(self, query: CallbackQuery):
        user_id = query.from_user.id
        u, room_level = self._ctx(user_id)
        level = u["level"]

        if level < 5:
            text = (
                "🏅 <b>Значки</b>\n\n"
                "🔒 Доступно с <b>5 уровня</b>.\n"
                f"Твой уровень: <b>{level}</b>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="inv")],
            ])
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
            return await query.answer()

        total = badge_slots_for_level(level)
        equipped = self.brain.db.get_user_badges(user_id)
        owned = self._owned(BADGES, u, room_level)

        lines = [
            "🏅 <b>Значки — артефакты с баффами</b>\n",
            f"⭐ Уровень: <b>{level}</b>  •  Ячеек: <b>{total}/5</b>",
            f"🎖 Открыто: <b>{len(owned)}/{len(BADGES)}</b>\n",
        ]
        for slot in range(total):
            bid = equipped.get(slot)
            if bid:
                b = BADGES[bid]
                lines.append(f"{slot + 1}. {b['name']} — <i>{describe_effect(b.get('effect', {}))}</i>")
            else:
                lines.append(f"{slot + 1}. <i>пусто</i>")

        unlock_lvl = [5, 5, 5, 25, 100]
        buttons = []
        for slot in range(5):
            if slot >= total:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 Ячейка {slot + 1} (с {unlock_lvl[slot]} ур.)",
                    callback_data="locked"
                )])
                continue
            bid = equipped.get(slot)
            label = f"{slot + 1}. {BADGES[bid]['name']}" if bid else f"➕ Ячейка {slot + 1}"
            buttons.append([InlineKeyboardButton(
                text=label, callback_data=f"inv_slot_{slot}"
            )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="inv")])

        try:
            await query.message.edit_text(
                "\n".join(lines) + "\n\nВыбери ячейку:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except Exception:
            pass
        await query.answer()

    async def cb_slot(self, query: CallbackQuery):
        try:
            slot = int(query.data.replace("inv_slot_", ""))
        except ValueError:
            return await query.answer("Ошибка", show_alert=True)

        user_id = query.from_user.id
        u, room_level = self._ctx(user_id)
        if slot >= badge_slots_for_level(u["level"]):
            return await query.answer("Ячейка заблокирована", show_alert=True)

        owned = self._owned(BADGES, u, room_level)
        equipped = self.brain.db.get_user_badges(user_id)

        if not owned:
            return await query.answer("Нет доступных значков", show_alert=True)

        buttons = []
        for bid in owned:
            b = BADGES[bid]
            mark = " ✅" if equipped.get(slot) == bid else ""
            r = RARITY_EMOJI.get(b["rarity"], "⚪")
            buttons.append([InlineKeyboardButton(
                text=f"{r} {b['name']}{mark}",
                callback_data=f"inv_badge_pick_{slot}_{bid}"
            )])

        if equipped.get(slot):
            buttons.append([InlineKeyboardButton(
                text="❌ Снять значок",
                callback_data=f"inv_badge_remove_{slot}"
            )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="inv_badges")])

        text = (
            f"🏅 <b>Ячейка {slot + 1}</b>\n\n"
            f"Доступно значков: <b>{len(owned)}</b>\n\n"
            "<i>Нажми, чтобы надеть. Эффекты применяются сразу.</i>"
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

    async def cb_badge_pick(self, query: CallbackQuery):
        parts = query.data.split("_", 4)
        if len(parts) != 5:
            return await query.answer("Ошибка", show_alert=True)
        try:
            slot = int(parts[3])
        except ValueError:
            return await query.answer("Ошибка", show_alert=True)
        bid = parts[4]

        user_id = query.from_user.id
        if bid not in BADGES:
            return await query.answer("Значок не найден", show_alert=True)
        u, room_level = self._ctx(user_id)
        if bid not in self._owned(BADGES, u, room_level):
            return await query.answer("Значок ещё не открыт", show_alert=True)

        self.brain.db.set_user_badge(user_id, slot, bid)
        await query.answer(f"✅ Надето: {BADGES[bid]['name']}")
        query.data = f"inv_slot_{slot}"
        await self.cb_slot(query)

    async def cb_badge_remove(self, query: CallbackQuery):
        try:
            slot = int(query.data.replace("inv_badge_remove_", ""))
        except ValueError:
            return await query.answer("Ошибка", show_alert=True)
        user_id = query.from_user.id
        self.brain.db.remove_user_badge(user_id, slot)
        await query.answer("❌ Значок снят")
        query.data = f"inv_slot_{slot}"
        await self.cb_slot(query)

    async def cb_titles(self, query: CallbackQuery):
        user_id = query.from_user.id
        u, room_level = self._ctx(user_id)
        owned = self._owned(TITLES, u, room_level)
        current = self.brain.db.get_title(user_id)

        lines = [
            "🏷 <b>Титулы — просто для красоты</b>\n",
            f"🎖 Открыто: <b>{len(owned)}/{len(TITLES)}</b>\n",
            f"Сейчас: <b>{current}</b>\n",
            "<i>Титулы не дают бонусов. Они украшают профиль.</i>\n",
        ]
        buttons = []
        for tid, t in TITLES.items():
            r = RARITY_EMOJI.get(t["rarity"], "⚪")
            if tid in owned:
                mark = " ✅" if t["name"] == current else ""
                buttons.append([InlineKeyboardButton(
                    text=f"{r} {t['name']}{mark}",
                    callback_data=f"inv_title_pick_{tid}"
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 {t['name']}",
                    callback_data="locked"
                )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="inv")])

        try:
            await query.message.edit_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except Exception:
            pass
        await query.answer()

    async def cb_title_pick(self, query: CallbackQuery):
        tid = query.data.replace("inv_title_pick_", "")
        user_id = query.from_user.id
        if tid not in TITLES:
            return await query.answer("Титул не найден", show_alert=True)
        u, room_level = self._ctx(user_id)
        if tid not in self._owned(TITLES, u, room_level):
            return await query.answer("Титул ещё не открыт", show_alert=True)

        self.brain.db.set_title(user_id, TITLES[tid]["name"])
        await query.answer(f"✅ Титул: {TITLES[tid]['name']}")
        await self.cb_titles(query)