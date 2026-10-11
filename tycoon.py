from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db import DB


class TycoonStates(StatesGroup):
    waiting_for_name = State()


MAX_HOURS = DB.CASINO_MAX_HOURS
ROOMS = DB.ROOMS
STAFF = DB.STAFF


def fmt(seconds):
    if seconds <= 0:
        return "0м"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"


def progress_bar(value, total, length=10):
    if total <= 0:
        return "▱" * length
    filled = int(value / total * length)
    filled = max(0, min(length, filled))
    return "▰" * filled + "▱" * (length - filled)


def fmt_num(n):
    """1200000 → 1 200 000"""
    return f"{n:,}".replace(",", " ")


class Tycoon:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "casino")(self.cb_casino)
        dp.callback_query(F.data == "tycoon_collect")(self.cb_collect)
        dp.callback_query(F.data == "tycoon_rooms")(self.cb_rooms)
        dp.callback_query(F.data.startswith("tycoon_open_"))(self.cb_open_room)
        dp.callback_query(F.data == "tycoon_staff")(self.cb_staff)
        dp.callback_query(F.data.startswith("tycoon_hire_"))(self.cb_hire_staff)
        dp.callback_query(F.data == "tycoon_rename")(self.cb_rename_start)
        dp.callback_query(F.data == "tycoon_info")(self.cb_info)
        dp.callback_query(F.data.startswith("tycoon_event_"))(self.cb_event)
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

        # Пробуем тригернуть событие
        self.brain.db.try_trigger_event(user_id)
        casino = self.brain.db.get_casino(user_id)

        await self._render_main(query, casino)

    # ---------- ГЛАВНЫЙ ЭКРАН ----------

    async def _render_main(self, query, casino):
        user_id = casino["user_id"]
        level = casino["level"]
        income = self.brain.db.get_income_per_hour(user_id)
        pending, elapsed, _ = self.brain.db.get_pending_income(user_id)

        max_seconds = MAX_HOURS * 3600
        capped = min(elapsed, max_seconds)
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

        rank = self.brain.db.get_casino_rank(user_id)
        rank_str = f"#{rank}" if rank else "—"

        text = (
            f"🏢 **{casino['name']}**\n"
            f"🏅 Место в рейтинге: **{rank_str}**\n\n"
            f"⭐ Уровень: **{level} / 10**\n"
            f"💵 Доход: **{fmt_num(income)} LC/час**\n"
            f"💼 Всего заработано: **{fmt_num(casino['total_earned'])} LC**\n\n"
            f"💰 **Накоплено: {fmt_num(pending)} LC**\n"
            f"{storage_line}\n"
            f"{hint}\n"
        )

        # Событие
        event = casino.get("pending_event")
        event_block = ""
        event_kb = []
        if event:
            if event == "celebrity":
                event_block = "\n🌟 **ЗНАМЕНИТОСТЬ В КАЗИНО!**\n_Бонус ждёт — забери!_"
                event_kb.append([InlineKeyboardButton(text="🌟 Забрать бонус", callback_data="tycoon_event_celebrity")])
            elif event == "big_visitor":
                event_block = "\n🐋 **Крупный игрок зашёл!**\n_Он проиграл кучу денег — забери!_"
                event_kb.append([InlineKeyboardButton(text="🐋 Забрать выигрыш", callback_data="tycoon_event_big_visitor")])
            elif event == "robbery":
                event_block = "\n🚨 **ОГРАБЛЕНИЕ!**\n_Воры в казино! Отбить?_"
                event_kb.append([InlineKeyboardButton(text="🛡 Отбить", callback_data="tycoon_event_robbery")])

        text += event_block

        buttons = []
        if pending > 0:
            buttons.append([InlineKeyboardButton(
                text=f"💵 Собрать {fmt_num(pending)} LC",
                callback_data="tycoon_collect"
            )])

        buttons.extend(event_kb)

        buttons.append([
            InlineKeyboardButton(text="🏗 Помещения", callback_data="tycoon_rooms"),
            InlineKeyboardButton(text="👔 Сотрудники", callback_data="tycoon_staff"),
        ])
        buttons.append([
            InlineKeyboardButton(text="ℹ️ Инфо", callback_data="tycoon_info"),
            InlineKeyboardButton(text="✏️ Имя", callback_data="tycoon_rename"),
        ])
        buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    # ---------- СОБРАТЬ ----------

    async def cb_collect(self, query: CallbackQuery):
        user_id = query.from_user.id
        collected = self.brain.db.collect_casino(user_id)
        if collected > 0:
            await query.answer(f"✅ Собрано {fmt_num(collected)} LC!", show_alert=True)
        else:
            await query.answer("Пока нечего собирать.", show_alert=True)
        casino = self.brain.db.get_casino(user_id)
        await self._render_main(query, casino)

    # ---------- ПОМЕЩЕНИЯ ----------

    async def cb_rooms(self, query: CallbackQuery):
        user_id = query.from_user.id
        opened = self.brain.db.get_rooms(user_id)
        user_level, _ = self.brain.db.get_level_xp(user_id)
        lc = self.brain.db.get_balance(user_id, "lc")

        lines = [
            "🏗 **Помещения казино**\n",
            f"⭐ Твой юзер-уровень: {user_level}",
            f"💰 LC: {fmt_num(lc)}\n",
        ]

        buttons = []
        for rid, room in ROOMS.items():
            is_open = rid in opened
            can_open = (
                not is_open
                and (rid == 1 or (rid - 1) in opened)
                and user_level >= room["req"]
            )

            if is_open:
                mark = "✅"
            elif can_open:
                mark = "🔓"
            else:
                mark = "🔒"

            lines.append(
                f"{mark} **{room['name']}** — {fmt_num(room['income'])} LC/ч\n"
                f"    _{room['desc']}_ | req: ур.{room['req']}"
            )

            if can_open:
                buttons.append([InlineKeyboardButton(
                    text=f"🏗 Открыть {room['name']} ({fmt_num(room['cost'])} LC)",
                    callback_data=f"tycoon_open_{rid}"
                )])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    async def cb_open_room(self, query: CallbackQuery):
        try:
            rid = int(query.data.replace("tycoon_open_", ""))
        except ValueError:
            return await query.answer("❌ Ошибка", show_alert=True)

        user_id = query.from_user.id
        ok, msg = self.brain.db.open_room(user_id, rid)
        await query.answer(msg, show_alert=True)

        # После покупки — обновить экран помещений
        if ok:
            await self.cb_rooms(query)

    # ---------- СОТРУДНИКИ ----------

    async def cb_staff(self, query: CallbackQuery):
        user_id = query.from_user.id
        hired = self.brain.db.get_staff(user_id)
        lc = self.brain.db.get_balance(user_id, "lc")

        lines = [
            "👔 **Сотрудники**\n",
            f"💰 LC: {fmt_num(lc)}\n",
        ]

        buttons = []
        for sid, s in STAFF.items():
            is_hired = sid in hired
            mark = "✅" if is_hired else "🆓"
            lines.append(
                f"{mark} **{s['name']}** — {s['desc']}\n"
                f"    Цена: {fmt_num(s['cost'])} LC"
            )
            if not is_hired:
                buttons.append([InlineKeyboardButton(
                    text=f"👔 Нанять {s['name']} ({fmt_num(s['cost'])} LC)",
                    callback_data=f"tycoon_hire_{sid}"
                )])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()

    async def cb_hire_staff(self, query: CallbackQuery):
        try:
            sid = int(query.data.replace("tycoon_hire_", ""))
        except ValueError:
            return await query.answer("❌ Ошибка", show_alert=True)

        user_id = query.from_user.id
        ok, msg = self.brain.db.hire_staff(user_id, sid)
        await query.answer(msg, show_alert=True)

        if ok:
            await self.cb_staff(query)

    # ---------- СОБЫТИЯ ----------

    async def cb_event(self, query: CallbackQuery):
        event_type = query.data.replace("tycoon_event_", "")
        user_id = query.from_user.id

        ok, text = self.brain.db.resolve_event(user_id, event_type, "auto")
        await query.answer(text, show_alert=True)

        casino = self.brain.db.get_casino(user_id)
        await self._render_main(query, casino)

    # ---------- ПЕРЕИМЕНОВАНИЕ ----------

    async def cb_rename_start(self, query: CallbackQuery, state: FSMContext):
        await state.set_state(TycoonStates.waiting_for_name)
        casino = self.brain.db.get_casino(query.from_user.id)
        current = casino["name"] if casino else "Моё казино"
        text = (
            f"✏️ **Переименование казино**\n\n"
            f"Текущее: **{current}**\n\n"
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

    # ---------- ИНФО ----------

    async def cb_info(self, query: CallbackQuery):
        user_id = query.from_user.id
        breakdown = self.brain.db.get_income_breakdown(user_id)

        text = (
            "ℹ️ **Как работает твоё казино**\n\n"
            "**1. Доход копится сам**\n"
            f"Казино генерирует LC каждый час, пока ты оффлайн.\n\n"
            "**2. Хранилище ограничено**\n"
            f"Максимум за **{MAX_HOURS} часов**. Дальше не растёт.\n\n"
            "**3. Помещения**\n"
            "Открываешь залы → растёт доход в час. Каждый новый зал требует LC и юзер-уровень.\n\n"
            "**4. Сотрудники**\n"
            "Нанятые сотрудники дают бонус к общему доходу. Охрана защищает от ограблений.\n\n"
            "**5. События**\n"
            "Раз в час случайно заходят знаменитости (бонус) или воры (ограбление).\n\n"
            f"**Сейчас у тебя:**\n"
            f"• Доход с залов: {fmt_num(breakdown['base'])} LC/ч\n"
            f"• Бонус сотрудников: +{int(breakdown['bonus_pct']*100)}% ({fmt_num(breakdown['bonus_lc'])} LC/ч)\n"
            f"• Итого: **{fmt_num(breakdown['total'])} LC/ч**"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await query.answer()