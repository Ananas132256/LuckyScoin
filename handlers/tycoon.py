from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from core.database import DB
from utils import is_current_screen, nav_footer, safe_answer, with_hero


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
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        if is_current_screen(query, "casino"):
            return await safe_answer(query, "Уже здесь")
        await safe_answer(query)
        if state:
            await state.clear()
        user_id = query.from_user.id
        casino = self.brain.db.get_casino(user_id)
        if not casino:
            self.brain.db.create_casino(user_id)
            casino = self.brain.db.get_casino(user_id)

        self.brain.db.try_trigger_event(user_id)
        casino = self.brain.db.get_casino(user_id)

        await self._render_main(query, casino)

    async def _show_under_construction(self, query):
        from config import TYCOON_COMING_VERSION

        await safe_answer(query)
        text = (
            "🚧 <b>Казино на реконструкции</b>\n\n"
            "Мы полностью переделываем этот режим — он станет "
            "интереснее, глубже и прибыльнее.\n\n"
            f"⏳ Возвращение: <b>версия {TYCOON_COMING_VERSION}</b>\n\n"
            "<b>Что нового:</b>\n"
            "• 🏗 Расширенные залы с уникальными бонусами\n"
            "• 👥 Сотрудники с навыками и уровнями\n"
            "• 📅 Ежедневные задания и цели\n"
            "• 🎁 Сезонные награды для владельцев\n\n"
            "<i>Твои прошлые вложения сохраним — учтём их "
            "при запуске.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="⬅️ В меню",
                callback_data="menu",
            )
        ]])
        try:
            await query.message.edit_text(
                text, reply_markup=kb, parse_mode="HTML"
            )
        except Exception:
            pass

    # ---------- ГЛАВНЫЙ ЭКРАН ----------

    async def _render_main(self, query, casino):
        user_id = casino["user_id"]
        user = self.brain.db.get_user(user_id)
        level = casino["level"]
        income = self.brain.db.get_income_per_hour(user_id)
        pending, elapsed, _ = self.brain.db.get_pending_income(user_id)

        max_seconds = MAX_HOURS * 3600
        capped = min(elapsed, max_seconds)
        bar = progress_bar(capped, max_seconds, 10)
        percent = int(capped / max_seconds * 100) if max_seconds else 0

        if capped >= max_seconds:
            storage_line = f"📦 <code>{bar}</code> <b>{percent}%</b> — ЗАПОЛНЕНО"
            hint = "⚠️ <i>Собери доход — больше не копится!</i>"
        elif pending > 0:
            storage_line = f"📦 <code>{bar}</code> <b>{percent}%</b>"
            hint = f"⏳ До заполнения: <b>{fmt(max_seconds - capped)}</b>"
        else:
            storage_line = f"📦 <code>{bar}</code> <b>{percent}%</b>"
            hint = "<i>Доход начнёт копиться сразу после открытия.</i>"

        rank = self.brain.db.get_casino_rank(user_id)
        rank_str = f"#{rank}" if rank else "—"

        body = (
            f"🏢 <b>{casino['name']}</b>\n"
            f"🏅 Место в рейтинге: <b>{rank_str}</b>\n\n"
            f"⭐ Уровень: <b>{level} / 10</b>\n"
            f"💵 Доход: <b>{fmt_num(income)} LC/час</b>\n"
            f"💼 Всего заработано: <b>{fmt_num(casino['total_earned'])} LC</b>\n\n"
            f"🏦 Обслуживание: <b>1 SC/сутки</b>\n\n"
            f"💰 <b>Накоплено: {fmt_num(pending)} LC</b>\n"
            f"{storage_line}\n"
            f"{hint}\n"
        )

        event = casino.get("pending_event")
        event_block = ""
        event_kb = []
        if event:
            if event == "celebrity":
                event_block = "\n🌟 <b>ЗНАМЕНИТОСТЬ В КАЗИНО!</b>\n<i>Бонус ждёт — забери!</i>"
                event_kb.append([InlineKeyboardButton(text="🌟 Забрать бонус", callback_data="tycoon_event_celebrity")])
            elif event == "big_visitor":
                event_block = "\n🐋 <b>Крупный игрок зашёл!</b>\n<i>Он проиграл кучу денег — забери!</i>"
                event_kb.append([InlineKeyboardButton(text="🐋 Забрать выигрыш", callback_data="tycoon_event_big_visitor")])
            elif event == "robbery":
                event_block = "\n🚨 <b>ОГРАБЛЕНИЕ!</b>\n<i>Воры в казино! Отбить?</i>"
                event_kb.append([InlineKeyboardButton(text="🛡 Отбить", callback_data="tycoon_event_robbery")])

        body += event_block
        text = with_hero(
            body, user, extra=f"  ·  🏢 {casino['name']}"
        )

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
        buttons.extend(nav_footer("casino"))

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

    # ---------- СОБРАТЬ ----------

    async def cb_collect(self, query: CallbackQuery):
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        user_id = query.from_user.id
        collected = self.brain.db.collect_casino(user_id)
        if collected > 0:
            self.brain.db.log_event(
                user_id, "", "collect_casino", str(collected)
            )
            await safe_answer(query, f"✅ Собрано {fmt_num(collected)} LC!", show_alert=True)
        else:
            await safe_answer(query, "Пока нечего собирать.", show_alert=True)
        casino = self.brain.db.get_casino(user_id)
        await self._render_main(query, casino)

    # ---------- ПОМЕЩЕНИЯ ----------

    async def cb_rooms(self, query: CallbackQuery):
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        await safe_answer(query)
        user_id = query.from_user.id
        opened = self.brain.db.get_rooms(user_id)
        user_level, _ = self.brain.db.get_level_xp(user_id)
        lc = self.brain.db.get_balance(user_id, "lc")

        lines = [
            "🏗 <b>Помещения казино</b>\n",
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
                f"{mark} <b>{room['name']}</b> — {fmt_num(room['income'])} LC/ч\n"
                f"    <i>{room['desc']}</i> | req: ур.{room['req']}"
            )

            if can_open:
                buttons.append([InlineKeyboardButton(
                    text=f"🏗 Открыть {room['name']} ({fmt_num(room['cost'])} LC)",
                    callback_data=f"tycoon_open_{rid}"
                )])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")])
        buttons.extend(nav_footer("casino"))
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

    async def cb_open_room(self, query: CallbackQuery):
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        try:
            rid = int(query.data.replace("tycoon_open_", ""))
        except ValueError:
            return await safe_answer(query, "❌ Ошибка", show_alert=True)

        user_id = query.from_user.id
        ok, msg = self.brain.db.open_room(user_id, rid)
        await safe_answer(query, msg, show_alert=True)

        if ok:
            self.brain.db.log_event(
                user_id, "", "open_room", f"{rid}|{ROOMS[rid]['cost']}"
            )
            await self.cb_rooms(query)

    # ---------- СОТРУДНИКИ ----------

    async def cb_staff(self, query: CallbackQuery):
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        await safe_answer(query)
        user_id = query.from_user.id
        hired = self.brain.db.get_staff(user_id)
        lc = self.brain.db.get_balance(user_id, "lc")

        lines = [
            "👔 <b>Сотрудники</b>\n",
            f"💰 LC: {fmt_num(lc)}\n",
        ]

        buttons = []
        for sid, s in STAFF.items():
            is_hired = sid in hired
            mark = "✅" if is_hired else "🆓"
            lines.append(
                f"{mark} <b>{s['name']}</b> — {s['desc']}\n"
                f"    Цена: {fmt_num(s['cost'])} LC"
            )
            if not is_hired:
                buttons.append([InlineKeyboardButton(
                    text=f"👔 Нанять {s['name']} ({fmt_num(s['cost'])} LC)",
                    callback_data=f"tycoon_hire_{sid}"
                )])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")])
        buttons.extend(nav_footer("casino"))
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

    async def cb_hire_staff(self, query: CallbackQuery):
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        try:
            sid = int(query.data.replace("tycoon_hire_", ""))
        except ValueError:
            return await safe_answer(query, "❌ Ошибка", show_alert=True)

        user_id = query.from_user.id
        ok, msg = self.brain.db.hire_staff(user_id, sid)
        await safe_answer(query, msg, show_alert=True)

        if ok:
            self.brain.db.log_event(
                user_id, "", "hire_staff", f"{sid}|{STAFF[sid]['cost']}"
            )
            await self.cb_staff(query)

    # ---------- СОБЫТИЯ ----------

    async def cb_event(self, query: CallbackQuery):
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        event_type = query.data.replace("tycoon_event_", "")
        user_id = query.from_user.id

        ok, text = self.brain.db.resolve_event(user_id, event_type, "auto")
        self.brain.db.log_event(user_id, "", "event_casino", f"{event_type}")
        await safe_answer(query, text, show_alert=True)

        casino = self.brain.db.get_casino(user_id)
        await self._render_main(query, casino)

    # ---------- ПЕРЕИМЕНОВАНИЕ ----------

    async def cb_rename_start(self, query: CallbackQuery, state: FSMContext):
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        await safe_answer(query)
        await state.set_state(TycoonStates.waiting_for_name)
        casino = self.brain.db.get_casino(query.from_user.id)
        current = casino["name"] if casino else "Моё казино"
        text = (
            f"✏️ <b>Переименование казино</b>\n\n"
            f"Текущее: <b>{current}</b>\n\n"
            f"Отправь новое название (от 2 до 20 символов).\n"
            f"Чтобы отменить — <code>/cancel</code>."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="casino")],
        ] + nav_footer("casino"))
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

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
        from config import TYCOON_ENABLED
        if not TYCOON_ENABLED:
            return await self._show_under_construction(query)
        await safe_answer(query)
        user_id = query.from_user.id
        breakdown = self.brain.db.get_income_breakdown(user_id)

        text = (
            "ℹ️ <b>Как работает твоё казино</b>\n\n"
            "<b>1. Доход копится сам</b>\n"
            f"Казино генерирует LC каждый час, пока ты оффлайн.\n\n"
            "<b>2. Хранилище ограничено</b>\n"
            f"Максимум за <b>{MAX_HOURS} часов</b>. Дальше не растёт.\n\n"
            "<b>3. Помещения</b>\n"
            "Открываешь залы → растёт доход в час. Каждый новый зал требует LC и юзер-уровень.\n\n"
            "<b>4. Сотрудники</b>\n"
            "Нанятые сотрудники дают бонус к общему доходу. Охрана защищает от ограблений.\n\n"
            "<b>5. События</b>\n"
            "Раз в час случайно заходят знаменитости (бонус) или воры (ограбление).\n\n"
            f"<b>Сейчас у тебя:</b>\n"
            f"• Доход с залов: {fmt_num(breakdown['base'])} LC/ч\n"
            f"• Бонус сотрудников: +{int(breakdown['bonus_pct']*100)}% ({fmt_num(breakdown['bonus_lc'])} LC/ч)\n"
            f"• Итого: <b>{fmt_num(breakdown['total'])} LC/ч</b>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")],
        ] + nav_footer("casino"))
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass