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


def _max_consecutive(symbols):
    result = {}
    if not symbols:
        return result
    current = symbols[0]
    count = 1
    for s in symbols[1:]:
        if s == current:
            count += 1
        else:
            if count > result.get(current, 0):
                result[current] = count
            current = s
            count = 1
    if count > result.get(current, 0):
        result[current] = count
    return result


def _has_consecutive_triple(symbols):
    return any(v >= 3 for v in _max_consecutive(symbols).values())


class Game:
    LEVEL_REQ = {"common": 0, "uncommon": 5, "rare": 25, "ultra": 100}
    STICKY_CHANCE = 0.2

    def __init__(self, brain):
        self.brain = brain

        self.symbols = {
            "7️⃣": {"weight": 1,   "pay": {3: 77,   4: 77,   5: 777},   "reroll": True},
            "🎲": {"weight": 0.5, "pay": {3: 100,  4: 100,  5: 1000},  "reroll": True},
            "🍀": {"weight": 200,  "pay": {3: 7.5,   4: 10,   5: 100},   "reroll": True},
            "💣": {"weight": 15,  "pay": {3: -0.5, 4: -1, 5: -20}, "reroll": True},
            "🍎": {"weight": 215, "pay": {3: 2,    4: 4,    5: 20},    "reroll": False},
            "🍍": {"weight": 250, "pay": {3: 1.5,    4: 3,    5: 15},    "reroll": False},
            "🍊": {"weight": 225, "pay": {3: 2,    4: 4,    5: 20},    "reroll": False},
            "🍋": {"weight": 215, "pay": {3: 2,    4: 4,    5: 20},    "reroll": False},
            "🪙": {"weight": 40,  "pay": {3: 5,    4: 5,    5: 50},    "reroll": False},
            "⚙️": {"weight": 9,   "pay": {3: "item", 4: "item", 5: "item"}, "reroll": True},
        }

        self.spin_types = {
            "common":   ("Обычная",       1,   5,    1),
            "uncommon": ("Необычная",     5,   250,   1.5),
            "rare":     ("Редкая",        25,  1000,  5),
            "ultra":    ("Ультраредкая",  100, 999999999, 100),
        }

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "play")(self.cb_play)
        dp.callback_query(F.data.startswith("choose_"))(self.cb_choose_type)
        dp.callback_query(F.data.startswith("again_"))(self.cb_spin_again)
        dp.callback_query(F.data == "cancel_bet")(self.cb_cancel_bet)
        dp.callback_query(F.data == "locked")(self.cb_locked)
        dp.message(BetStates.waiting_for_bet)(self.on_bet_input)
        dp.callback_query(F.data == "free_lc")(self.cb_free_lc)
        dp.callback_query(F.data == "exchange")(self.cb_exchange)
        dp.callback_query(F.data == "buy_sc")(self.cb_buy_sc)

    # ---------- ЛОГИКА ----------

    def _get_symbols(self):
        keys = list(self.symbols.keys())
        weights = [self.symbols[k]["weight"] for k in keys]

        result = []
        for i in range(5):
            if result and random.random() < self.STICKY_CHANCE:
                result.append(result[-1])
            else:
                result.append(random.choices(keys, weights=weights, k=1)[0])
        return result

    def _needs_reroll(self, symbols):
        # Если есть тройка 🎲 — это выигрыш, не рероллим
        dice_count = symbols.count("🎲")
        if dice_count >= 3:
            return False

        # 🎲 1-2 штуки → всегда реролл
        if 1 <= dice_count <= 2:
            return True

        # Остальные проверки
        if _has_consecutive_triple(symbols):
            return False
        reroll_count = sum(1 for s in symbols if self.symbols[s]["reroll"])
        if not (1 <= reroll_count <= 2):
            return False
        compressed = [s for s in symbols if not self.symbols[s]["reroll"]]
        return _has_consecutive_triple(compressed)

    def _calculate_win(self, symbols, bet, spin_mult):
        runs = _max_consecutive(symbols)
        win_amount = 0
        is_item = False
        for sym, run_len in runs.items():
            if run_len < 3:
                continue
            pay_data = self.symbols[sym]["pay"].get(run_len, 0)
            if isinstance(pay_data, str) and pay_data == "item":
                is_item = True
                win_amount += bet * 5 * spin_mult
            else:
                win_amount += bet * pay_data * spin_mult
        return math.ceil(win_amount), is_item

    async def _safe_edit(self, message, text, **kwargs):
        try:
            await message.edit_text(text, **kwargs)
        except TelegramBadRequest:
            pass

        # ---------- КОНФИГ АНИМАЦИИ ПО ТИПУ КРУТКИ ----------
    SPIN_ANIM = {
        "common": {
            "spin_frames": 5,       # сколько кадров кручения
            "spin_delay": 0.16,     # стартовая задержка кадра
            "stop_delay": 0.45,     # задержка остановки каждого символа
            "last_stop_delay": 0.75,
            "fake_stops": 0,        # фейковые остановки
            "label": "▶️",
        },
        "uncommon": {
            "spin_frames": 6,
            "spin_delay": 0.17,
            "stop_delay": 0.5,
            "last_stop_delay": 0.85,
            "fake_stops": 1,
            "label": "⚡",
        },
        "rare": {
            "spin_frames": 8,
            "spin_delay": 0.18,
            "stop_delay": 0.55,
            "last_stop_delay": 0.95,
            "fake_stops": 2,
            "label": "💫",
        },
        "ultra": {
            "spin_frames": 10,
            "spin_delay": 0.2,
            "stop_delay": 0.6,
            "last_stop_delay": 1.1,
            "fake_stops": 3,
            "label": "🔥",
        },
    }

    def _frame(self, inner: str, header: str = "") -> str:
        """Рисует рамку вокруг содержимого. inner — до 21 символа внутри."""
        pad = 21 - len(inner)
        if pad < 0:
            pad = 0
        inner_padded = inner + " " * pad
        line = f"║ {inner_padded} ║"
        top = "╔═══════════════════════╗"
        bot = "╚═══════════════════════╝"
        if header:
            return f"{header}\n{top}\n{line}\n{bot}"
        return f"{top}\n{line}\n{bot}"

    async def _animate_slots(self, message, name, bet):
        spin_key = None
        # Определяем тип крутки по имени (можно было передать, но так совместимо)
        for k, (n, *_rest) in self.spin_types.items():
            if n == name:
                spin_key = k
                break
        cfg = self.SPIN_ANIM.get(spin_key or "common", self.SPIN_ANIM["common"])

        noise = ["🎰", "🍒", "🍋", "7️⃣", "🎲", "🍀", "⚙️", "🪙", "💎", "🔔"]

        # -------- СТАДИЯ 1: ПОДГОТОВКА --------
        await self._safe_edit(
            message,
            f"🎰 **{name} крутка**\n"
            f"💰 Ставка: {bet} LC\n\n"
            f"{cfg['label']} *Подготовка...*\n\n"
            f"{self._frame('⬜ | ⬜ | ⬜ | ⬜ | ⬜')}",
            parse_mode="Markdown"
        )
        await asyncio.sleep(0.4)

        # -------- СТАДИЯ 2: КРУЧЕНИЕ --------
        for i in range(cfg["spin_frames"]):
            rnd = [random.choice(noise) for _ in range(5)]
            line = " | ".join(rnd)
            speed = ["▶️ ▶️ ▶️", "⏩ ⏩ ⏩", "⏩ ⏩", "▶️ ▶️ ▶️", "⏩ ⏩ ⏩"][i % 5]
            await self._safe_edit(
                message,
                f"🎰 **{name} крутка**\n"
                f"💰 Ставка: {bet} LC\n\n"
                f"{cfg['label']} *Крутим...* {speed}\n\n"
                f"{self._frame(line)}",
                parse_mode="Markdown"
            )
            # Замедление к концу кручения
            delay = cfg["spin_delay"] + i * 0.012
            await asyncio.sleep(delay)

        # -------- СТАДИЯ 3: ГЕНЕРАЦИЯ РЕЗУЛЬТАТА --------
        symbols = self._get_symbols()
        need_reroll = self._needs_reroll(symbols)

         # -------- СТАДИЯ 4: ФЕЙКОВЫЕ ОСТАНОВКИ --------
        for fake_i in range(cfg["fake_stops"]):
            # Случайные символы — никакого hint
            fake_line = " | ".join([random.choice(noise) for _ in range(5)])

            await self._safe_edit(
                message,
                f"🎰 **{name} крутка**\n"
                f"💰 Ставка: {bet} LC\n\n"
                f"😮 *Остановка...* {cfg['label']}\n\n"
                f"{self._frame(fake_line)}",
                parse_mode="Markdown"
            )
            await asyncio.sleep(0.7)

            # Резко снова крутим
            for j in range(3):
                rnd = [random.choice(noise) for _ in range(5)]
                line = " | ".join(rnd)
                await self._safe_edit(
                    message,
                    f"🎰 **{name} крутка**\n"
                    f"💰 Ставка: {bet} LC\n\n"
                    f"🌀 *Обманка! Ещё крутим...*\n\n"
                    f"{self._frame(line)}",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(0.15)

        # -------- СТАДИЯ 5: РЕАЛЬНАЯ ОСТАНОВКА ПО ОДНОМУ --------
        shown = []
        for idx, s in enumerate(symbols):
            shown.append(s)
            # Пустые слоты — показать ещё крутящиеся
            rest = ["🌫️"] * (5 - len(shown))
            display = " | ".join(shown + rest)
            stop_sound = "💥" if idx == 4 else "🔔"
            await self._safe_edit(
                message,
                f"🎰 **{name} крутка**\n"
                f"💰 Ставка: {bet} LC\n\n"
                f"{cfg['label']} *Остановка...* {stop_sound}\n\n"
                f"{self._frame(display)}",
                parse_mode="Markdown"
            )
            if idx == 4:
                await asyncio.sleep(cfg["last_stop_delay"])
            else:
                await asyncio.sleep(cfg["stop_delay"])

        # -------- СТАДИЯ 6: ОЦЕНКА РЕЗУЛЬТАТА --------
        runs = _max_consecutive(symbols)
        best_run = max(runs.values()) if runs else 0
        best_sym = max(runs, key=runs.get) if runs else None

        final_line = " | ".join(symbols)
        final_frame = self._frame(final_line)

        # Близкий промах — 2 одинаковых
        near_miss = (best_run == 2 and best_sym in ("7️⃣", "🎲", "🍀", "💣", "💎"))

        if near_miss:
            await self._safe_edit(
                message,
                f"🎰 **{name} крутка**\n"
                f"💰 Ставка: {bet} LC\n\n"
                f"😱 **ОЙ, ЧУТЬ-ЧУТЬ!**\n\n"
                f"{final_frame}\n"
                f"_{best_sym} {best_sym} — нужен ещё один {best_sym}..._",
                parse_mode="Markdown"
            )
            await asyncio.sleep(1.2)

        # -------- СТАДИЯ 7: РЕРОЛЛ --------
        if need_reroll:
            await asyncio.sleep(0.3)
            for i in range(4):
                rnd = [random.choice(noise) for _ in range(5)]
                line = " | ".join(rnd)
                await self._safe_edit(
                    message,
                    f"🎰 **{name} крутка**\n"
                    f"💰 Ставка: {bet} LC\n\n"
                    f"🔄 **РЕРОЛЛ!** Шанс на бонус...\n\n"
                    f"{self._frame(line)}",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(0.22 - i * 0.02)

            await asyncio.sleep(0.3)
            return await self._animate_slots(message, name, bet)

        # -------- СТАДИЯ 8: ФИНАЛЬНЫЙ ЭФФЕКТ --------
        if best_run >= 3:
            for i in range(3):
                sparkles = ["✨ 🎉 ✨", "🎊 🏆 🎊", "💥 ✨ 💥"][i]
                await self._safe_edit(
                    message,
                    f"🎰 **{name} крутка**\n"
                    f"💰 Ставка: {bet} LC\n\n"
                    f"🎉 **ВЫИГРЫШ!** {sparkles}\n\n"
                    f"{final_frame}",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(0.3)
        else:
            await self._safe_edit(
                message,
                f"🎰 **{name} крутка**\n"
                f"💰 Ставка: {bet} LC\n\n"
                f"😔 *Нет тройки...*\n\n"
                f"{final_frame}",
                parse_mode="Markdown"
            )
            await asyncio.sleep(0.6)

        return symbols

    # ---------- МЕНЮ ИГРЫ ----------

    async def cb_play(self, query: CallbackQuery, state: FSMContext = None):
        if state:
            await state.clear()
        user_id = query.from_user.id
        lc_balance = self.brain.db.get_balance(user_id, "lc")
        level, xp = self.brain.db.get_level_xp(user_id)
        xp_needed = 100 * (level + 1)

        last_free = self.brain.db.get_last_free_lc(user_id)
        can_get_free = (time.time() - last_free) > 3600

        text = (
            f"🎰 **Игровой зал LuckyScoin**\n\n"
            f"💰 Баланс LC: {lc_balance}\n"
            f"⭐ Уровень: {level} (XP: {xp}/{xp_needed})\n\n"
            f"Выбери тип крутки:"
        )
        if can_get_free:
            text += "\n\n🎁 Доступны бесплатные LC!"

        buttons = []
        for key, (name, min_b, max_b, mult) in self.spin_types.items():
            req = self.LEVEL_REQ[key]
            if level >= req:
                buttons.append([InlineKeyboardButton(
                    text=f"{name} ({min_b}-{max_b} LC)",
                    callback_data=f"choose_{key}"
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 {name} (с {req} ур.)",
                    callback_data="locked"
                )])

        if can_get_free:
            buttons.append([InlineKeyboardButton(text="🎁 Забрать бесплатные LC", callback_data="free_lc")])
        buttons.append([InlineKeyboardButton(text="💱 Обменять LC на SC", callback_data="exchange")])
        buttons.append([InlineKeyboardButton(text="💰 Купить SC", callback_data="buy_sc")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await self._safe_edit(query.message, text, reply_markup=kb, parse_mode="Markdown")
        await query.answer()

    async def cb_locked(self, query: CallbackQuery):
        await query.answer("🔒 Недостаточный уровень!", show_alert=True)

    async def _ask_bet(self, query, spin_key, state):
        if spin_key not in self.spin_types:
            return await query.answer("Неизвестный тип!", show_alert=True)

        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        if level < self.LEVEL_REQ.get(spin_key, 0):
            return await query.answer(f"Нужен уровень {self.LEVEL_REQ[spin_key]}!", show_alert=True)

        name, min_b, max_b, mult = self.spin_types[spin_key]
        await state.set_state(BetStates.waiting_for_bet)
        await state.update_data(spin_key=spin_key, min_bet=min_b, max_bet=max_b)

        text = (
            f"🎰 **{name} крутка**\n\n"
            f"Введи ставку в LC (от {min_b} до {max_b}).\n"
            f"Отправь число сообщением."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_bet")]
        ])
        await self._safe_edit(query.message, text, reply_markup=kb, parse_mode="Markdown")
        await query.answer()

    async def cb_choose_type(self, query: CallbackQuery, state: FSMContext):
        key = query.data.split("_", 1)[1]
        await self._ask_bet(query, key, state)

    async def cb_spin_again(self, query: CallbackQuery, state: FSMContext):
        key = query.data.split("_", 1)[1]
        await self._ask_bet(query, key, state)

    async def cb_cancel_bet(self, query: CallbackQuery, state: FSMContext):
        await state.clear()
        await self.cb_play(query, state)

    async def on_bet_input(self, message: Message, state: FSMContext):
        text = (message.text or "").strip()

        if text.startswith("/"):
            await state.clear()
            return await message.answer("Ок, отменено. Используй меню.")

        data = await state.get_data()
        spin_key = data.get("spin_key")
        min_b = data.get("min_bet", 1)
        max_b = data.get("max_bet", 3)
        if spin_key is None:
            await state.clear()
            return

        try:
            bet = int(text)
        except ValueError:
            return await message.answer(f"Введи число от {min_b} до {max_b}.")

        if not (min_b <= bet <= max_b):
            return await message.answer(f"Ставка должна быть от {min_b} до {max_b}.")

        user_id = message.from_user.id
        lc_balance = self.brain.db.get_balance(user_id, "lc")
        if lc_balance < bet:
            return await message.answer(f"Недостаточно LC. У тебя {lc_balance}.")

        await state.clear()
        self.brain.db.add_balance(user_id, "lc", -bet)

        name, _, _, spin_mult = self.spin_types[spin_key]
        msg = await message.answer(f"🎰 **{name} крутка**\n\nКрутим...", parse_mode="Markdown")

        symbols = await self._animate_slots(msg, name, bet)
        win_amount, is_item = self._calculate_win(symbols, bet, spin_mult)

        if win_amount > 0:
            self.brain.db.add_balance(user_id, "lc", win_amount)
            self.brain.db.add_result(user_id, True)
        else:
            self.brain.db.add_result(user_id, False)

        # XP (2x при победе)
        xp_gain = spin_mult * 20
        if win_amount > 0:
            xp_gain *= 2
        level, xp, leveled_up = self.brain.db.add_xp(user_id, xp_gain)
        xp_needed = 100 * (level + 1)

        slot_line = " | ".join(symbols)
        result_text = f"🎰 **{name} крутка**\n\n"
        result_text += f"💰 Ставка: {bet} LC\n"
        result_text += f"Линия: {slot_line}\n\n"

        if is_item:
            result_text += "🎁 Ты выбил случайный предмет!\n"
        elif win_amount > 0:
            result_text += f"✅ Выигрыш: +{win_amount} LC\n"
        elif win_amount < 0:
            result_text += f"💣 Бомбы: {win_amount} LC\n"
        else:
            result_text += "❌ Нет тройки — проигрыш\n"

        if win_amount > 0:
            result_text += f"\n⭐ +{xp_gain} XP (x2 за победу!)"
        else:
            result_text += f"\n⭐ +{xp_gain} XP"
        if leveled_up:
            result_text += f"\n🎉 **НОВЫЙ УРОВЕНЬ: {level}!**"
        result_text += f"\n⭐ Ур. {level} — XP {xp}/{xp_needed}"
        result_text += f"\n💰 Баланс LC: {self.brain.db.get_balance(user_id, 'lc')}"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Крутить еще", callback_data=f"again_{spin_key}")],
            [InlineKeyboardButton(text="⬅️ В меню",      callback_data="play")]
        ])
        await self._safe_edit(msg, result_text, reply_markup=kb, parse_mode="Markdown")

    # ---------- ПРОЧИЕ ----------

    async def cb_free_lc(self, query: CallbackQuery):
        user_id = query.from_user.id
        last_free = self.brain.db.get_last_free_lc(user_id)
        if (time.time() - last_free) < 3600:
            remaining = 3600 - (time.time() - last_free)
            return await query.answer(f"Подожди еще {int(remaining // 60)} мин.", show_alert=True)

        self.brain.db.add_balance(user_id, "lc", 15)
        self.brain.db.set_last_free_lc(user_id, int(time.time()))
        await query.answer("🎁 Ты получил 15 бесплатных LC!", show_alert=True)
        await self.cb_play(query)

    async def cb_exchange(self, query: CallbackQuery):
        user_id = query.from_user.id
        lc = self.brain.db.get_balance(user_id, "lc")
        if lc < 20:
            return await query.answer(f"Нужно минимум 20 LC. У тебя: {lc}", show_alert=True)
        amount = (lc // 20) * 20
        sc_gained = amount // 20
        self.brain.db.add_balance(user_id, "lc", -amount)
        self.brain.db.add_balance(user_id, "sc", sc_gained)
        await query.answer(f"💱 Обменяно {amount} LC → {sc_gained} SC!", show_alert=True)
        await self.cb_play(query)

    async def cb_buy_sc(self, query: CallbackQuery):
        await query.answer("💰 Покупка SC пока в разработке!", show_alert=True)