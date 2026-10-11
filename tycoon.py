from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db import DB


class TycoonStates(StatesGroup):
    waiting_for_name = State()


MAX_HOURS = DB.CASINO_MAX_HOURS
MAX_LEVEL = DB.CASINO_MAX_LEVEL
INCOME = DB.CASINO_INCOME
COST = DB.CASINO_UPGRADE_COST
REQ = DB.CASINO_USER_REQ


def fmt(seconds):
    if seconds <= 0:
        return "0м"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"


def progress_bar(value, total, length=10):
    """Рисует прогресс-бар ▰▰▰▱▱▱"""
    if total <= 0:
        return "▱" * length
    filled = int(value / total * length)
    filled = max(0, min(length, filled))
    return "▰" * filled + "▱" * (length - filled)


class Tycoon:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "casino")(self.cb_casino)
        dp.callback_query(F.data == "tycoon_collect")(self.cb_collect)
        dp.callback_query(F.data == "tycoon_upgrade")(self.cb_upgrade)
        dp.callback_query(F.data == "tycoon_rename")(self.cb_rename_start)
        dp.callback_query(F.data == "tycoon_levels")(self.cb_levels)
        dp.callback_query(F.data == "tycoon_info")(self.cb_info)
        dp.message(TycoonStates.waiting_for_name)(self.on_name_input)

    # ---------- ОТКРЫТИЕ ----------

    async def cb_casino(self, query: CallbackQuery, state: FSMContext = None):
        if state:
            await state.clear()
        user_id = query.from_user.id
        casino = self.brain.db.get_casino(user_id)
        if not casino:
            self.brain.db.create_casino(user_id)
            casino = self.brain.db.get_casino(user_id)
        await self._render_main(query, casino)

    # ---------- ГЛАВНЫЙ ЭКРАН ----------

    async def _render_main(self, query, casino):
        user_id = casino["user_id"]
        level = casino["level"]
        income = INCOME.get(level, 0)
        pending, elapsed, _ = self.brain.db.get_pending_income(user_id)

        # Прогресс хранилища
        max_seconds = MAX_HOURS * 3600
        capped = min(elapsed, max_seconds)
        max_pending = int(income * MAX_HOURS)
        bar = progress_bar(capped, max_seconds, 10)
        percent = int(capped / max_seconds * 100) if max_seconds else 0

        if capped >= max_seconds:
            storage_line = f"📦 `{bar}` **{percent}%** — ЗАПОЛНЕНО"
            hint = "⚠️ *Собери доход — больше не копится!*"
        elif pending > 0:
            storage_line = f"📦 `{bar}` **{percent}%**"
            hint = f"⏳ До заполнения: **{fmt(max_seconds - capped)}**"
        else:
            storage_line = f"📦 `{bar}` **{percent}%**"
            hint = "*Доход начнёт копиться сразу после открытия.*"

        # Ранг
        rank = self.brain.db.get_casino_rank(user_id)

        # Юзер-уровень
        user_level, _ = self.brain.db.get_level_xp(user_id)

        text = (
            f"🏢 **{casino['name']}**\n"
            f"🏅 Место в рейтинге: **#{rank}**\n\n"
            f"⭐ Уровень казино: **{level} / {MAX_LEVEL}**\n"
            f"💵 Доход: **{income} LC/час**\n"
            f"💼 Всего заработано: **{casino['total_earned']} LC**\n"
            f"👤 Твой юзер-уровень: **{user_level}**\n\n"
            f"💰 **Накоплено: {pending} LC**\n"
            f"{storage_line}\n"
            f"{hint}\n"
        )

        # Что дальше
        if level < MAX_LEVEL:
            next_level = level + 1
            next_income = INCOME.get(next_level, 0)
            next_cost = COST.get(level, 0)
            req_lvl = REQ.get(next_level, 999)
            can_upgrade = (user_level >= req_lvl)
            mark = "✅" if can_upgrade else "🔒"
            text += (
                f"\n📈 **Следующий уровень {next_level}:**\n"
                f"  • Доход: {income} → **{next_income} LC/ч**\n"
                f"  • Цена: **{next_cost} LC**\n"
                f"  • Нужен юзер-уровень: {mark} **{req_lvl}**"
            )
        else:
            text += "\n👑 **У тебя максимальный уровень казино!**"

        # Кнопки
        buttons = []
        if pending > 0:
            buttons.append([InlineKeyboardButton(
                text=f"💵 Собрать {pending} LC",
                callback_data="tycoon_collect"
            )])
        if level < MAX_LEVEL:
            buttons.append([InlineKeyboardButton(
                text=f"📈 Апгрейд до {level + 1} ({COST.get(level, 0)} LC)",
                callback_data="tycoon_upgrade"
            )])
        buttons.append([
            InlineKeyboardButton(text="📊 Уровни",  callback_data="tycoon_levels"),
            InlineKeyboardButton(text="ℹ️ Инфо",    callback_data="tycoon_info"),
        ])
        buttons.append([InlineKeyboardButton(text="✏️ Переименовать", callback_data="tycoon_rename")])
        buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    # ---------- КНОПКИ ----------

    async def cb_collect(self, query: CallbackQuery):
        user_id = query.from_user.id
        collected = self.brain.db.collect_casino(user_id)
        if collected > 0:
            await query.answer(f"✅ Собрано {collected} LC!", show_alert=True)
        else:
            await query.answer("Пока нечего собирать — подожди немножко.", show_alert=True)
        casino = self.brain.db.get_casino(user_id)
        await self._render_main(query, casino)

    async def cb_upgrade(self, query: CallbackQuery):
        user_id = query.from_user.id
        old_casino = self.brain.db.get_casino(user_id)
        old_level = old_casino["level"]

        ok, msg = self.brain.db.upgrade_casino(user_id)
        await query.answer(msg, show_alert=True)

        if ok:
            casino = self.brain.db.get_casino(user_id)
            new_level = casino["level"]
            old_income = INCOME.get(old_level, 0)
            new_income = INCOME.get(new_level, 0)

            upgrade_text = (
                f"🎉 **АПГРЕЙД УСПЕШЕН!**\n\n"
                f"🏢 **{casino['name']}**\n"
                f"⭐ Уровень: {old_level} → **{new_level}**\n"
                f"💵 Доход: {old_income} → **{new_income} LC/ч**\n\n"
                f"Теперь ты зарабатываешь больше!\n"
                f"Не забудь собирать доход каждые {MAX_HOURS} ч."
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏢 К казино", callback_data="casino")]
            ])
            try:
                await query.message.edit_text(upgrade_text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                pass
        else:
            casino = self.brain.db.get_casino(user_id)
            await self._render_main(query, casino)

    async def cb_levels(self, query: CallbackQuery):
        user_id = query.from_user.id
        casino = self.brain.db.get_casino(user_id)
        current = casino["level"] if casino else 0

        lines = ["📊 **Таблица уровней казино**\n"]
        lines.append("`Ур. │ Доход/ч  │ Апгрейд    │ Юзер`")
        lines.append("`────┼──────────┼────────────┼─────`")
        for lvl in range(1, MAX_LEVEL + 1):
            income = INCOME.get(lvl, 0)
            cost = COST.get(lvl, 0)
            req = REQ.get(lvl, 0)
            mark = "▶️" if lvl == current else "  "
            cost_str = f"{cost:,}".replace(",", " ") if cost else "—"
            lines.append(f"`{mark}{lvl:>2} │ {income:>7}  │ {cost_str:>10} │ {req:>3}`")

        lines.append(f"\n▶️ — твой текущий уровень ({current})")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")]
        ])
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    async def cb_info(self, query: CallbackQuery):
        text = (
            "ℹ️ **Как работает своё казино**\n\n"
            "**1. Доход копится сам**\n"
            f"Твоё казино генерирует LC каждый час. Даже когда ты оффлайн.\n\n"
            "**2. Хранилище ограничено**\n"
            f"Максимум накапливается за **{MAX_HOURS} часов**. Дальше не растёт — надо заходить и собирать.\n\n"
            "**3. Апгрейды**\n"
            "Улучшаешь уровень → растёт доход в час. Требуются LC и достаточный юзер-уровень.\n\n"
            "**4. Рейтинг**\n"
            "Все казино соревнуются по уровню и общему заработку. Топ виден в лидерборде.\n\n"
            "**5. Совет**\n"
            "Заходи 2-3 раза в день, чтобы не терять доход от переполнения хранилища."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    async def cb_rename_start(self, query: CallbackQuery, state: FSMContext):
        await state.set_state(TycoonStates.waiting_for_name)
        casino = self.brain.db.get_casino(query.from_user.id)
        current = casino["name"] if casino else "Моё казино"

        text = (
            f"✏️ **Переименование казино**\n\n"
            f"Текущее название: **{current}**\n\n"
            f"Отправь новое название (от 2 до 20 символов).\n"
            f"Чтобы отменить — `/cancel`."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="casino")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    async def on_name_input(self, message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if text.startswith("/"):
            await state.clear()
            return await message.answer("Ок, отменено.")

        if not (2 <= len(text) <= 20):
            return await message.answer("❌ Название должно быть от 2 до 20 символов.")

        user_id = message.from_user.id
        casino = self.brain.db.get_casino(user_id)
        if not casino:
            return await message.answer("❌ Сначала открой казино через меню.")

        self.brain.db.rename_casino(user_id, text)
        await state.clear()
        await message.answer(f"✅ Казино переименовано в «{text}»!")