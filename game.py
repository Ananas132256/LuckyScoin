import random
import time
import asyncio
import math
from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext


class BetStates(StatesGroup):
    waiting_for_bet = State()


# ============================================================
#  КОНСТАНТЫ
# ============================================================

EXCHANGE_LC_TO_SC = 1000    # 1000 LC = 1 SC
EXCHANGE_SC_TO_LC = 500     # 1 SC = 500 LC

TYPE_ALIASES = {
    "обычное": "common", "обычная": "common", "обычный": "common", "common": "common",
    "необычное": "uncommon", "необычная": "uncommon", "необычный": "uncommon", "uncommon": "uncommon",
    "редкое": "rare", "редкая": "rare", "редкий": "rare", "rare": "rare",
    "ультра": "ultra", "ультраредкое": "ultra", "ультраредкая": "ultra", "ultra": "ultra",
}


# ============================================================
#  ХЕЛПЕРЫ
# ============================================================

def _runs(symbols):
    result = {}
    if not symbols:
        return result
    cur, cnt = symbols[0], 1
    for s in symbols[1:]:
        if s == cur:
            cnt += 1
        else:
            if cnt > result.get(cur, 0):
                result[cur] = cnt
            cur, cnt = s, 1
    if cnt > result.get(cur, 0):
        result[cur] = cnt
    return result


def _best_run(symbols):
    r = _runs(symbols)
    if not r:
        return None, 0
    sym = max(r, key=r.get)
    return sym, r[sym]


def _match_pattern(symbols, pattern):
    if len(symbols) != len(pattern):
        return False
    label_to_sym = {}
    sym_to_label = {}
    for s, label in zip(symbols, pattern):
        if label == "_":
            continue
        if label in label_to_sym:
            if label_to_sym[label] != s:
                return False
        else:
            if s in sym_to_label:
                return False
            label_to_sym[label] = s
            sym_to_label[s] = label
    return True


# ============================================================
#  ИГРА
# ============================================================

class Game:
    LEVEL_REQ = {"common": 0, "uncommon": 5, "rare": 25, "ultra": 100}
    STICKY_CHANCE = 0.3
    MAX_REROLLS = 30

    PATTERNS = [
        {"name": "Пирамида", "pattern": ("A", "B", "C", "B", "A"), "action": "reroll", "mult": 0},
        {"name": "Зигзаг",   "pattern": ("A", "B", "A", "B", "A"), "action": "reroll", "mult": 0},
    ]

    SYMBOLS = {
        "7️⃣": {"weight": 1,   "pay": {3: 77,   4: 77,   5: 777},   "reroll": True},
        "🎲": {"weight": 0.5, "pay": {3: 100,  4: 100,  5: 1000},  "reroll": True},
        "🍀": {"weight": 200, "pay": {3: 7.5,  4: 10,   5: 100},   "reroll": True},
        "💣": {"weight": 15,  "pay": {3: -0.5, 4: -1,   5: -20},   "reroll": True},
        "🍎": {"weight": 215, "pay": {3: 2,    4: 4,    5: 20},    "reroll": False},
        "🍍": {"weight": 250, "pay": {3: 1.5,  4: 3,    5: 15},    "reroll": False},
        "🍊": {"weight": 225, "pay": {3: 2,    4: 4,    5: 20},    "reroll": False},
        "🍋": {"weight": 215, "pay": {3: 2,    4: 4,    5: 20},    "reroll": False},
        "🪙": {"weight": 40,  "pay": {3: 5,    4: 5,    5: 50},    "reroll": False},
        "⚙️": {"weight": 9,   "pay": {3: "item", 4: "item", 5: "item"}, "reroll": True},
    }

    SPIN_TYPES = {
        "common":   ("Обычная",       1,   5,         1),
        "uncommon": ("Необычная",     5,   250,       1.5),
        "rare":     ("Редкая",        25,  1000,      5),
        "ultra":    ("Ультраредкая",  100, 999999999, 100),
    }

    SPIN_ANIM = {
        "common":   {"spin_frames": 8,  "spin_delay": 0.09, "stop_delay": 0.32, "last_stop_delay": 0.55, "fake_stops": 0, "label": "▶️"},
        "uncommon": {"spin_frames": 10, "spin_delay": 0.09, "stop_delay": 0.36, "last_stop_delay": 0.65, "fake_stops": 1, "label": "⚡"},
        "rare":     {"spin_frames": 12, "spin_delay": 0.10, "stop_delay": 0.40, "last_stop_delay": 0.80, "fake_stops": 2, "label": "💫"},
        "ultra":    {"spin_frames": 16, "spin_delay": 0.10, "stop_delay": 0.45, "last_stop_delay": 1.00, "fake_stops": 3, "label": "🔥"},
    }

    NOISE = ["🎰", "🍒", "🍋", "7️⃣", "🎲", "🍀", "⚙️", "🪙", "💎", "🔔"]

    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        # callback'и
        dp.callback_query(F.data == "play")(self.cb_play)
        dp.callback_query(F.data.startswith("choose_"))(self.cb_choose_type)
        dp.callback_query(F.data.startswith("again_"))(self.cb_spin_again)
        dp.callback_query(F.data == "cancel_bet")(self.cb_cancel_bet)
        dp.callback_query(F.data == "locked")(self.cb_locked)
        dp.callback_query(F.data == "free_lc")(self.cb_free_lc)
        dp.callback_query(F.data == "exchange")(self.cb_exchange)
        dp.callback_query(F.data == "buy_sc")(self.cb_buy_sc)
        # FSM (должен быть раньше текстовых команд!)
        dp.message(BetStates.waiting_for_bet)(self.on_bet_input)
        # текстовые команды
        dp.message(F.text.func(lambda t: bool(t) and t.strip().lower().startswith("крутить")))(self.cmd_spin_text)
        dp.message(F.text.func(lambda t: bool(t) and t.strip().lower().startswith("обмен")))(self.cmd_exchange_text)

    # ---------------------------------------------------------
    #  ГЕНЕРАЦИЯ И ОЦЕНКА
    # ---------------------------------------------------------
    def _spin(self, reroll_count=0):
        keys = list(self.SYMBOLS.keys())
        factor = 0.5 ** reroll_count
        weights = []
        for k in keys:
            w = self.SYMBOLS[k]["weight"]
            if self.SYMBOLS[k]["reroll"]:
                w *= factor
            weights.append(w)
        result = []
        for _ in range(5):
            if result and random.random() < self.STICKY_CHANCE:
                result.append(result[-1])
            else:
                result.append(random.choices(keys, weights=weights, k=1)[0])
        return result

    def _evaluate(self, symbols):
        sym, run = _best_run(symbols)
        if run >= 3:
            pay = self.SYMBOLS[sym]["pay"].get(run, 0)
            is_item = (pay == "item")
            mult = 5.0 if is_item else float(pay)
            if self.SYMBOLS[sym]["reroll"]:
                return {"action": "reroll", "mult": mult, "item": is_item,
                        "sym": sym, "run": run, "reason": "unstable"}
            return {"action": "win", "mult": mult, "item": is_item,
                    "sym": sym, "run": run}
        for p in self.PATTERNS:
            if _match_pattern(symbols, p["pattern"]):
                return {
                    "action": p.get("action", "reroll"),
                    "mult": float(p.get("mult", 1)),
                    "item": False,
                    "sym": None, "run": 0,
                    "reason": "pattern",
                    "pattern_name": p.get("name", "?"),
                }
        return {"action": "loss"}

    # ---------------------------------------------------------
    #  ОТРИСОВКА
    # ---------------------------------------------------------
    async def _safe_edit(self, message, text, **kwargs):
        try:
            await message.edit_text(text, **kwargs)
        except TelegramBadRequest:
            pass

    async def _render(self, message, name, bet, line_display, header, extra=""):
        text = (
            f"🎰 <b>{name} крутка</b>\n"
            f"💰 Ставка: {bet} LC\n\n"
            f"{header}\n"
        )
        if extra:
            text += f"{extra}\n"
        text += f"\n<blockquote>{line_display}</blockquote>"
        await self._safe_edit(message, text, parse_mode="HTML")

    # ---------------------------------------------------------
    #  АНИМАЦИИ
    # ---------------------------------------------------------
    async def _anim_spin(self, message, name, bet, cfg):
        await self._render(message, name, bet, "⬜ | ⬜ | ⬜ | ⬜ | ⬜",
                           f"{cfg['label']} <i>Подготовка...</i>")
        await asyncio.sleep(0.30)
        frames = cfg["spin_frames"]
        base_delay = cfg["spin_delay"]
        for i in range(frames):
            rnd = " | ".join(random.choice(self.NOISE) for _ in range(5))
            progress = i / max(1, frames - 1)
            if progress < 0.5:
                speed_factor = 1 - progress * 1.6
            else:
                speed_factor = 0.2 + (progress - 0.5) * 3.0
            delay = base_delay * max(0.15, speed_factor)
            if progress < 0.5:
                speed = "⏩ ⏩ ⏩"
            elif progress < 0.8:
                speed = "⏩ ⏩ ▶️"
            else:
                speed = "⏩ ▶️ ▶️"
            await self._render(message, name, bet, rnd,
                               f"{cfg['label']} <i>Крутим...</i> {speed}")
            await asyncio.sleep(delay)
        for _ in range(cfg["fake_stops"]):
            fake = " | ".join(random.choice(self.NOISE) for _ in range(5))
            await self._render(message, name, bet, fake, "😮 <i>Остановка...</i>")
            await asyncio.sleep(0.55)
            for _ in range(3):
                rnd = " | ".join(random.choice(self.NOISE) for _ in range(5))
                await self._render(message, name, bet, rnd, "🌀 <i>Обманка!</i>")
                await asyncio.sleep(0.10)
            for _ in range(2):
                rnd = " | ".join(random.choice(self.NOISE) for _ in range(5))
                await self._render(message, name, bet, rnd, "⏩ <i>Ещё крутим!</i>")
                await asyncio.sleep(0.08)

    async def _anim_reveal(self, message, name, bet, symbols, cfg):
        shown = []
        for idx, final_sym in enumerate(symbols):
            shown.append(final_sym)
            rest = ["🌫️"] * (5 - len(shown))
            for _ in range(2):
                shake = random.choice(self.NOISE)
                temp = shown[:-1] + [shake] + rest
                await self._render(
                    message, name, bet, " | ".join(temp),
                    f"{cfg['label']} <i>Остановка...</i> <code>{idx + 1}/5</code>"
                )
                await asyncio.sleep(0.12)
            display = " | ".join(shown + rest)
            sound = "💥" if idx == 4 else "🔔"
            await self._render(
                message, name, bet, display,
                f"{cfg['label']} <b>Стоп!</b> {sound} <code>{idx + 1}/5</code>"
            )
            if idx == 4:
                await asyncio.sleep(cfg["last_stop_delay"])
            else:
                await asyncio.sleep(cfg["stop_delay"] + idx * 0.10)

    async def _anim_reroll(self, message, name, bet, reroll_count, verdict, total):
        if verdict.get("reason") == "pattern":
            header = f"✨ <b>{verdict.get('pattern_name', 'ОСОБАЯ КОМБИНАЦИЯ')}!</b>\n<i>Перекрут...</i>"
        else:
            header = "⚡ <b>Нестабильный символ!</b>\n<i>Перекрут...</i>"
        extra = f"🔄 Реролл <b>#{reroll_count}</b> • Копилка: <b>x{total:g}</b>"
        for _ in range(4):
            rnd = " | ".join(random.choice(self.NOISE) for _ in range(5))
            await self._render(message, name, bet, rnd, header, extra)
            await asyncio.sleep(0.16)
        await asyncio.sleep(0.20)

    async def _anim_win(self, message, name, bet, symbols, description):
        line = " | ".join(symbols)
        for spark in ["✨ 🎉 ✨", "🎊 🏆 🎊", "💥 ✨ 💥"]:
            await self._render(message, name, bet, line,
                               f"🎉 <b>ВЫИГРЫШ!</b> {spark}\n<i>{description}</i>")
            await asyncio.sleep(0.28)

    async def _anim_loss(self, message, name, bet, symbols):
        line = " | ".join(symbols)
        await self._render(message, name, bet, line, "😔 <i>Ничего не выпало...</i>")
        await asyncio.sleep(0.55)

    # ---------------------------------------------------------
    #  ГЛАВНЫЙ ЦИКЛ
    # ---------------------------------------------------------
    async def _resolve(self, message, name, bet, spin_key):
        cfg = self.SPIN_ANIM.get(spin_key, self.SPIN_ANIM["common"])
        total_mult = 0.0
        is_item_any = False
        reroll_count = 0
        final_symbols = []
        final_description = ""
        while True:
            await self._anim_spin(message, name, bet, cfg)
            symbols = self._spin(reroll_count)
            await self._anim_reveal(message, name, bet, symbols, cfg)
            verdict = self._evaluate(symbols)
            final_symbols = symbols
            if verdict["action"] == "win":
                total_mult += verdict["mult"]
                is_item_any = is_item_any or verdict["item"]
                if verdict.get("reason") == "pattern":
                    final_description = f"Паттерн «{verdict.get('pattern_name', '?')}»"
                else:
                    final_description = f"{verdict['sym']} × {verdict['run']}"
                await self._anim_win(message, name, bet, symbols, final_description)
                break
            if verdict["action"] == "reroll":
                total_mult += verdict["mult"]
                is_item_any = is_item_any or verdict["item"]
                reroll_count += 1
                if reroll_count > self.MAX_REROLLS:
                    break
                await self._anim_reroll(message, name, bet, reroll_count,
                                        verdict, total_mult)
                continue
            total_mult = 0
            is_item_any = False
            await self._anim_loss(message, name, bet, symbols)
            break
        return total_mult, is_item_any, final_symbols, reroll_count

    # ---------------------------------------------------------
    #  ЗАПУСК ИГРЫ (общая функция для callback и текста)
    # ---------------------------------------------------------
    async def _start_game(self, message: Message, spin_key: str, bet: int):
        user_id = message.from_user.id
        self.brain.db.add_balance(user_id, "lc", -bet)

        name, _, _, spin_mult = self.SPIN_TYPES[spin_key]
        msg = await message.answer(f"🎰 <b>{name} крутка</b>\n\nКрутим...",
                                   parse_mode="HTML")

        total_mult, is_item, symbols, rerolls = await self._resolve(msg, name, bet, spin_key)
        win_amount = math.ceil(bet * total_mult * spin_mult) if total_mult > 0 else 0

        if win_amount > 0:
            self.brain.db.add_balance(user_id, "lc", win_amount)
            self.brain.db.add_result(user_id, True)
        else:
            self.brain.db.add_result(user_id, False)

        xp_gain = spin_mult * 20 * (2 if win_amount > 0 else 1)
        level, xp, leveled_up = self.brain.db.add_xp(user_id, xp_gain)
        xp_needed = 100 * (level + 1)

        slot_line = " | ".join(symbols)
        result = f"🎰 <b>{name} крутка</b>\n\n"
        result += f"💰 Ставка: {bet} LC\n\n"
        result += f"<blockquote>{slot_line}</blockquote>\n\n"
        if rerolls > 0:
            result += f"🔄 Рероллов: <b>{rerolls}</b>\n"
        if is_item:
            result += "🎁 Выбил предмет!\n"
        if win_amount > 0:
            result += f"✅ <b>+{win_amount} LC</b> (x{total_mult * spin_mult:g})\n"
        elif win_amount < 0:
            result += f"💣 <b>{win_amount} LC</b>\n"
        else:
            result += "❌ Ничего...\n"
        result += f"\n⭐ +{xp_gain} XP" + (" (x2!)" if win_amount > 0 else "")
        if leveled_up:
            result += f"\n🎉 <b>НОВЫЙ УРОВЕНЬ: {level}!</b>"
        result += f"\n⭐ Ур. {level} — XP {xp}/{xp_needed}"
        result += f"\n💰 Баланс LC: {self.brain.db.get_balance(user_id, 'lc')}"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Ещё", callback_data=f"again_{spin_key}")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="play")]])
        await self._safe_edit(msg, result, reply_markup=kb, parse_mode="HTML")

    # ---------------------------------------------------------
    #  МЕНЮ (callback)
    # ---------------------------------------------------------
    async def cb_play(self, query: CallbackQuery, state: FSMContext = None):
        if state:
            await state.clear()
        user_id = query.from_user.id
        lc = self.brain.db.get_balance(user_id, "lc")
        level, xp = self.brain.db.get_level_xp(user_id)
        xp_needed = 100 * (level + 1)
        last_free = self.brain.db.get_last_free_lc(user_id)
        can_get_free = (time.time() - last_free) > 3600

        text = (f"🎰 <b>Игровой зал LuckyScoin</b>\n\n"
                f"💰 Баланс LC: {lc}\n"
                f"⭐ Уровень: {level} (XP: {xp}/{xp_needed})\n\n"
                f"Выбери тип крутки:")
        if can_get_free:
            text += "\n\n🎁 Доступны бесплатные LC!"

        buttons = []
        for key, (name, min_b, max_b, mult) in self.SPIN_TYPES.items():
            req = self.LEVEL_REQ[key]
            if level >= req:
                buttons.append([InlineKeyboardButton(
                    text=f"{name} ({min_b}-{max_b} LC)",
                    callback_data=f"choose_{key}")])
            else:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 {name} (с {req} ур.)",
                    callback_data="locked")])
        if can_get_free:
            buttons.append([InlineKeyboardButton(text="🎁 Забрать бесплатные LC", callback_data="free_lc")])
        buttons.append([InlineKeyboardButton(text="💱 Обменять LC на SC", callback_data="exchange")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])

        await self._safe_edit(query.message, text,
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                              parse_mode="HTML")
        await query.answer()

    async def cb_locked(self, query: CallbackQuery):
        await query.answer("🔒 Недостаточный уровень!", show_alert=True)

    async def _ask_bet(self, query, spin_key, state):
        if spin_key not in self.SPIN_TYPES:
            return await query.answer("Неизвестный тип!", show_alert=True)
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        if level < self.LEVEL_REQ.get(spin_key, 0):
            return await query.answer(f"Нужен уровень {self.LEVEL_REQ[spin_key]}!", show_alert=True)
        name, min_b, max_b, mult = self.SPIN_TYPES[spin_key]
        await state.set_state(BetStates.waiting_for_bet)
        await state.update_data(spin_key=spin_key, min_bet=min_b, max_bet=max_b)
        text = (f"🎰 <b>{name} крутка</b>\n\n"
                f"Введи ставку в LC (от {min_b} до {max_b}).")
        await self._safe_edit(
            query.message, text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_bet")]]),
            parse_mode="HTML")
        await query.answer()

    async def cb_choose_type(self, query: CallbackQuery, state: FSMContext):
        await self._ask_bet(query, query.data.split("_", 1)[1], state)

    async def cb_spin_again(self, query: CallbackQuery, state: FSMContext):
        await self._ask_bet(query, query.data.split("_", 1)[1], state)

    async def cb_cancel_bet(self, query: CallbackQuery, state: FSMContext):
        await state.clear()
        await self.cb_play(query, state)

    # ---------------------------------------------------------
    #  ВВОД СТАВКИ (FSM)
    # ---------------------------------------------------------
    async def on_bet_input(self, message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if text.startswith("/"):
            await state.clear()
            return await message.answer("Ок, отменено.")

        data = await state.get_data()
        spin_key = data.get("spin_key")
        min_b, max_b = data.get("min_bet", 1), data.get("max_bet", 3)
        if spin_key is None:
            await state.clear()
            return

        try:
            bet = int(text)
        except ValueError:
            return await message.answer(f"Введи число от {min_b} до {max_b}.")
        if not (min_b <= bet <= max_b):
            return await message.answer(f"Ставка от {min_b} до {max_b}.")

        user_id = message.from_user.id
        if self.brain.db.get_balance(user_id, "lc") < bet:
            return await message.answer(
                f"Недостаточно LC. У тебя {self.brain.db.get_balance(user_id, 'lc')}.")

        await state.clear()
        await self._start_game(message, spin_key, bet)

    # ---------------------------------------------------------
    #  ТЕКСТОВАЯ КОМАНДА «крутить ...»
    # ---------------------------------------------------------
    async def cmd_spin_text(self, message: Message, state: FSMContext):
        await state.clear()
        args = message.text.strip().split()
        user_id = message.from_user.id

        # крутить (без аргументов)
        if len(args) == 1:
            return await message.answer(
                "🎰 <b>Текстовые команды для круток</b>\n\n"
                "<code>крутить обычное 5</code>\n"
                "<code>крутить необычное 50</code>\n"
                "<code>крутить редкое 100</code>\n"
                "<code>крутить ультра 200</code>\n\n"
                "<i>Типы: обычное, необычное, редкое, ультра</i>",
                parse_mode="HTML"
            )

        # крутить <тип>
        type_str = args[1].lower()
        spin_key = TYPE_ALIASES.get(type_str)
        if not spin_key:
            return await message.answer(
                "❓ Неизвестный тип. Доступные: обычное, необычное, редкое, ультра"
            )

        level, _ = self.brain.db.get_level_xp(user_id)
        if level < self.LEVEL_REQ.get(spin_key, 0):
            return await message.answer(f"🔒 Нужен уровень {self.LEVEL_REQ[spin_key]}")

        name, min_b, max_b, _ = self.SPIN_TYPES[spin_key]

        # крутить <тип> (без ставки) — ждём ввод
        if len(args) == 2:
            await state.set_state(BetStates.waiting_for_bet)
            await state.update_data(spin_key=spin_key, min_bet=min_b, max_bet=max_b)
            return await message.answer(
                f"🎰 <b>{name} крутка</b>\n\n"
                f"Введи ставку (от {min_b} до {max_b} LC):",
                parse_mode="HTML"
            )

        # крутить <тип> <ставка>
        try:
            bet = int(args[2])
        except ValueError:
            return await message.answer("❌ Ставка должна быть числом.")
        if not (min_b <= bet <= max_b):
            return await message.answer(f"❌ Ставка от {min_b} до {max_b}.")

        if self.brain.db.get_balance(user_id, "lc") < bet:
            return await message.answer(
                f"❌ Недостаточно LC. У тебя {self.brain.db.get_balance(user_id, 'lc')}.")

        await self._start_game(message, spin_key, bet)

    # ---------------------------------------------------------
    #  ОБМЕННИК — КНОПКА
    # ---------------------------------------------------------
    async def cb_exchange(self, query: CallbackQuery):
        text = (
            "💱 <b>Обмен валют</b>\n\n"
            f"LC → SC: <b>{EXCHANGE_LC_TO_SC} LC</b> = <b>1 SC</b>\n"
            f"SC → LC: <b>1 SC</b> = <b>{EXCHANGE_SC_TO_LC} LC</b>\n\n"
            "<b>Как обменять:</b>\n"
            "<code>обмен 2000 lc</code> — продать 2000 LC\n"
            "<code>обмен 3 sc</code> — продать 3 SC\n\n"
            "<i>Можно указывать любую сумму — сколько хочешь перевести.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="play")]
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer()

    # ---------------------------------------------------------
    #  ОБМЕННИК — ТЕКСТ
    # ---------------------------------------------------------
    async def cmd_exchange_text(self, message: Message):
        args = message.text.strip().split()
        user_id = message.from_user.id

        # обмен (без аргументов) — справка
        if len(args) < 3:
            return await message.answer(
                "💱 <b>Обмен валют</b>\n\n"
                f"LC → SC: <b>{EXCHANGE_LC_TO_SC} LC</b> = <b>1 SC</b>\n"
                f"SC → LC: <b>1 SC</b> = <b>{EXCHANGE_SC_TO_LC} LC</b>\n\n"
                "Напиши: <code>обмен 2000 lc</code> или <code>обмен 3 sc</code>",
                parse_mode="HTML"
            )

        # Парсим сумму
        try:
            amount = int(args[1])
        except ValueError:
            return await message.answer("❌ Сумма должна быть числом.")
        if amount <= 0:
            return await message.answer("❌ Сумма должна быть больше 0.")

        currency = args[2].lower()
        if currency not in ("lc", "sc"):
            return await message.answer("❌ Валюта: <b>lc</b> или <b>sc</b>.",
                                        parse_mode="HTML")

        # ===== LC → SC =====
        if currency == "lc":
            if amount < EXCHANGE_LC_TO_SC:
                return await message.answer(
                    f"❌ Минимум {EXCHANGE_LC_TO_SC} LC для обмена.")
            balance = self.brain.db.get_balance(user_id, "lc")
            if balance < amount:
                return await message.answer(
                    f"❌ У тебя только {balance} LC.")

            gained_sc = amount // EXCHANGE_LC_TO_SC
            used_lc = gained_sc * EXCHANGE_LC_TO_SC
            self.brain.db.add_balance(user_id, "lc", -used_lc)
            self.brain.db.add_balance(user_id, "sc", gained_sc)
            return await message.answer(
                f"💱 Обменяно <b>{used_lc} LC</b> → <b>{gained_sc} SC</b>",
                parse_mode="HTML"
            )

        # ===== SC → LC =====
        balance = self.brain.db.get_balance(user_id, "sc")
        if balance < amount:
            return await message.answer(
                f"❌ У тебя только {balance} SC.")

        gained_lc = amount * EXCHANGE_SC_TO_LC
        self.brain.db.add_balance(user_id, "sc", -amount)
        self.brain.db.add_balance(user_id, "lc", gained_lc)
        return await message.answer(
            f"💱 Обменяно <b>{amount} SC</b> → <b>{gained_lc} LC</b>",
            parse_mode="HTML"
        )

    # ---------------------------------------------------------
    #  ПРОЧИЕ
    # ---------------------------------------------------------
    async def cb_free_lc(self, query: CallbackQuery):
        user_id = query.from_user.id
        last = self.brain.db.get_last_free_lc(user_id)
        if (time.time() - last) < 3600:
            return await query.answer(
                f"Подожди {int((3600 - (time.time() - last)) // 60)} мин.",
                show_alert=True)
        self.brain.db.add_balance(user_id, "lc", 15)
        self.brain.db.set_last_free_lc(user_id, int(time.time()))
        await query.answer("🎁 +15 LC!", show_alert=True)
        await self.cb_play(query)

    async def cb_buy_sc(self, query: CallbackQuery):
        await query.answer("💰 В разработке!", show_alert=True)