import random
import time
import asyncio
import math
from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext


class BetStates(StatesGroup):
    waiting_for_bet = State()


def _runs(symbols, skip=("🔥",)):
    """Серии одинаковых, игнорируя 🔥 (он рвёт серию)."""
    result = {}
    if not symbols:
        return result
    cur, cnt = None, 0
    for s in symbols:
        if s in skip:
            if cur and cnt > result.get(cur, 0):
                result[cur] = cnt
            cur, cnt = None, 0
            continue
        if s == cur:
            cnt += 1
        else:
            if cur and cnt > result.get(cur, 0):
                result[cur] = cnt
            cur, cnt = s, 1
    if cur and cnt > result.get(cur, 0):
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


class Game:
    # ============================================================
    #  НАСТРОЙКИ
    # ============================================================
    LEVEL_REQ = {
        "common": 0, "uncommon": 6, "rare": 15, "ultra": 50, "epic": 100,
        "advanced": 12,
    }
    STICKY_CHANCE = 0.15
    MAX_REROLLS = 100
    # Вес выпадения значка по редкости: чем реже значок, тем ниже шанс.
    ITEM_RARITY_WEIGHTS = {
        "common":    100,
        "rare":      30,
        "epic":      8,
        "legendary": 1,
    }
    # Компенсация в LC, если у игрока нет свободного слота под значок.
    # Платим LC, а не SC — SC должен оставаться редким.
    NO_SLOT_COMPENSATION_LC = 2000   # ≈ 2 SC по курсу 1000 LC = 1 SC

    PATTERNS = [
        {"name": "Пирамида", "pattern": ("A", "B", "C", "B", "A"), "action": "reroll", "mult": 1.1},
        {"name": "Зигзаг",   "pattern": ("A", "B", "A", "B", "A"), "action": "reroll", "mult": 0},
        {"name": "ДЖЕКПОТ",  "pattern": ("A", "A", "A", "A", "A"), "action": "win",    "mult": 2},
    ]

    SYMBOLS = {
        "7️⃣": {"weight": 1,   "pay": {3: 77,     4: 77,     5: 777  }, "reroll": False},
        "🎲": {"weight": 5,   "pay": {3: 50,     4: 100,    5: 200  }, "reroll": True},
        "🍀": {"weight": 50,  "pay": {3: 5,      4: 7.5,    5: 50   }, "reroll": True},
        "💣": {"weight": 200, "pay": {3: -0.5,   4: -0.75,  5: -0.99}, "reroll": False},
        "🍎": {"weight": 225, "pay": {3: 1.5,    4: 4,      5: 10   }, "reroll": False},
        "🍍": {"weight": 225, "pay": {3: 1.5,    4: 3,      5: 10   }, "reroll": False},
        "🍭": {"weight": 150, "pay": {3: 2,      4: 5,      5: 15   }, "reroll": True},
        "🍋": {"weight": 225, "pay": {3: 1.5,    4: 4,      5: 10   }, "reroll": False},
        "🪙": {"weight": 50,  "pay": {3: 5,      4: 7.5,    5: 50   }, "reroll": True},
        "⚙️": {"weight": 50,  "pay": {3: "item", 4: "item", 5: "item"}, "reroll": False},
        "💎": {"weight": 50,  "pay": {3: 5,      4: 7.5,    5: 50   }, "reroll": False},
    }

    SPIN_TYPES = {
        "common":   ("Обычная",       1,     5,         1),
        "uncommon": ("Необычная",     6,     250,       2),
        "rare":     ("Редкая",        250,   1000,      5),
        "ultra":    ("Ультраредкая",  1000,  10000,     15),
        "epic":     ("Эпическая",     10000, 1000000,   50),
        "advanced": ("Продвинутое",  100,   5000,       1.5),
    }

    SPIN_ANIM = {
        "common":   {"spin_frames": 3, "spin_delay": 1.05, "stop_delay": 1.05, "last_stop_delay": 2.00, "label": "▶️"},
        "uncommon": {"spin_frames": 3, "spin_delay": 1.05, "stop_delay": 1.10, "last_stop_delay": 2.20, "label": "⚡"},
        "rare":     {"spin_frames": 3, "spin_delay": 1.05, "stop_delay": 1.20, "last_stop_delay": 2.40, "label": "💫"},
        "ultra":    {"spin_frames": 4, "spin_delay": 1.05, "stop_delay": 1.30, "last_stop_delay": 2.60, "label": "🔥"},
        "epic":     {"spin_frames": 4, "spin_delay": 1.05, "stop_delay": 1.50, "last_stop_delay": 3.00, "label": "👾"},
        "advanced": {
            "spin_frames": 3, "spin_delay": 1.10, "stop_delay": 1.10,
            "last_stop_delay": 1.20, "fake_stops": 1, "label": "🎰",
        },
    }

    NOISE = ["🎰", "🍒", "🍋", "7️⃣", "🎲", "🍀", "⚙️", "🪙", "💎", "🔔"]

    # ============================================================
    #  ПЕРЕГРЕВ
    # ============================================================
    # (иконка, шанс на 1 ячейку, шанс на всю линию)
    OVERHEAT_STAGES = [
        ("🌀🌀🌀🌀🌀", 0.00, 0.00),   # 0
        ("🔥🌀🌀🌀🌀", 0.01, 0.00),   # 1
        ("🔥🔥🌀🌀🌀", 0.05, 0.00),   # 2
        ("🔥🔥🔥🌀🌀", 0.20, 0.05),   # 3
        ("🔥🔥🔥🔥🌀", 0.50, 0.15),   # 4
        ("🔥🔥🔥🔥🔥", 0.75, 0.50),   # 5
    ]
    FIRE_PENALTY = 0.20   # -20% за каждый 🔥
    ROULETTE_TICKET_PRICE_SC = 5
    MAX_TICKETS = 10
    ROULETTE_PRIZES = (
        {"symbol": "💰", "name": "Деньги", "chance": 35, "currency": "lc", "amount": 50},
        {"symbol": "🎁", "name": "Подарок", "chance": 30, "currency": "lc", "amount": 100},
        {"symbol": "🍀", "name": "Клевер", "chance": 20, "currency": "lc", "amount": 500},
        {"symbol": "💎", "name": "Бриллиант", "chance": 10, "currency": "lc", "amount": 5000},
        {
            "symbol": "👑", "name": "Корона", "chance": 4,
            "currency": "lc", "amount": 50000,
            "medal": "leaf", "medal_chance": 0.25,
        },
        {
            "symbol": "🌌", "name": "Галактика", "chance": 1,
            "currency": "lc", "amount": 500000,
            "medal": "three_leaf_clover", "medal_chance": 0.10,
        },
    )

    def __init__(self, brain):
        self.brain = brain
        self._last_edit = 0
        self._edit_lock = asyncio.Lock()

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "play")(self.cb_play)
        dp.callback_query(F.data.startswith("choose_"))(self.cb_choose_type)
        dp.callback_query(F.data == "advanced_patterns")(self.cb_advanced_patterns)
        dp.callback_query(F.data.startswith("again_"))(self.cb_spin_again)
        dp.callback_query(F.data == "cancel_bet")(self.cb_cancel_bet)
        dp.callback_query(F.data == "locked")(self.cb_locked)
        dp.callback_query(F.data == "roulette")(self.cb_roulette)
        dp.callback_query(F.data == "roulette_buy")(self.roulette_buy)
        dp.callback_query(F.data == "roulette_spin")(self.roulette_spin)
        dp.callback_query(F.data == "exchange")(self.cb_exchange)
        dp.message(BetStates.waiting_for_bet)(self.on_bet_input)

    # ---------- ЭФФЕКТЫ ----------

    def _effects(self, user_id):
        try:
            from item_system import get_total_effects
            return get_total_effects(self.brain, user_id) or {}
        except Exception:
            return {}

    def _pick_random_badge(self, user_id):
        from cosmetics import BADGES, is_unlocked

        user = self.brain.db.get_user(user_id)
        rooms = self.brain.db.get_rooms(user_id) or []
        room_level = max(rooms) if rooms else 0

        equipped = self.brain.db.get_user_badges(user_id)
        owned_ids = {bid for bid in equipped.values() if bid}
        badge_weights = [
            (badge_id, self.ITEM_RARITY_WEIGHTS[badge.get("rarity")])
            for badge_id, badge in BADGES.items()
            if badge.get("rarity") in self.ITEM_RARITY_WEIGHTS
            and badge_id not in owned_ids
            and is_unlocked(badge, user, room_level)
        ]
        if not badge_weights:
            return None

        badge_ids, weights = zip(*badge_weights)
        return random.choices(badge_ids, weights=weights, k=1)[0]

    def _award_badge(self, user_id):
        try:
            from cosmetics import BADGES, badge_slots_for_level

            badge_id = self._pick_random_badge(user_id)
            if badge_id is None:
                # Защита на будущее: если значков станет меньше, чем слотов.
                amount = self.NO_SLOT_COMPENSATION_LC
                self.brain.db.add_balance(user_id, "lc", amount)
                return f"🎁 Все значки уже собраны! Начислено <b>{amount} LC</b>."

            badge = BADGES.get(badge_id)
            shop_id = badge.get("shop_id") if badge else None
            if not shop_id:
                return None

            # Сначала сохраняем медаль в инвентаре, чтобы она не потерялась.
            self.brain.db.add_item(user_id, shop_id, 1)

            level = self.brain.db.get_user(user_id)["level"]
            max_slots = badge_slots_for_level(level)
            equipped = self.brain.db.get_user_badges(user_id)
            slot = next(
                (i for i in range(max_slots) if not equipped.get(i)),
                None,
            )
            name = badge["name"]
            if slot is not None:
                self.brain.db.set_user_badge(user_id, slot, badge_id)
                return f"🎁 Выпал значок: <b>{name}</b> (слот {slot + 1})"

            return f"🎁 Выпал значок: <b>{name}</b>, добавлен в инвентарь."
        except Exception as error:
            print(f"⚠️ Ошибка выдачи медали: {error}")
            return None

    # ---------- ГЕНЕРАЦИЯ ----------

    def _spin(self, reroll_count=0, effects=None):
        effects = effects or {}
        luck = effects.get("luck", 0)
        rare_symbol_bonus = effects.get("rare_symbol_bonus", 0)
        keys = list(self.SYMBOLS.keys())
        factor = max(0.5 ** reroll_count, 1e-9)
        weights = []
        for k in keys:
            w = self.SYMBOLS[k]["weight"]
            if self.SYMBOLS[k]["reroll"]:
                w *= factor
            if luck > 0:
                if k == "💣":
                    w *= max(0.1, 1 - luck)
                elif k in ("7️⃣", "🎲", "🍀"):
                    w *= (1 + luck * 2)
            if rare_symbol_bonus > 0 and k in ("7️⃣", "🎲"):
                w *= 1 + rare_symbol_bonus
            weights.append(max(w, 1e-9))

        result = []
        for _ in range(5):
            if result and random.random() < self.STICKY_CHANCE:
                result.append(result[-1])
            else:
                result.append(random.choices(keys, weights=weights, k=1)[0])
        return result

    def _spin_grid(self, reroll_count=0, effects=None, stage=0):
        """Генерирует три линии; перегрев применяется только к центральной."""
        grid = [
            self._spin(reroll_count, effects)
            for _ in range(3)
        ]
        grid[1], _, _ = self._apply_overheat(grid[1], stage, effects)
        return grid

    def _apply_overheat(self, symbols, stage, effects=None):
        """
        Применяет перегрев ПОСЛЕ выпадения символов.
        Возвращает (новая_линия, сгорела_ли_вся, было_ли_возгорание).
        """
        effects = effects or {}
        # fire_shield уменьшает шанс загорания (0.5 = -50% шанс)
        shield = effects.get("fire_shield", 0)
        icon, cell_chance, line_chance = self.OVERHEAT_STAGES[stage]

        cell_chance = max(0.0, cell_chance * (1 - shield))
        line_chance = max(0.0, line_chance * (1 - shield))

        # Шанс что вся линия сгорит
        if line_chance > 0 and random.random() < line_chance:
            return ["🔥"] * 5, True, True

        # Иначе — каждая ячейка независимо
        result = list(symbols)
        burned = False
        for i in range(5):
            if random.random() < cell_chance:
                result[i] = "🔥"
                burned = True
        return result, False, burned

    def _evaluate(self, symbols, effects=None):
        effects = effects or {}
        bomb_shield = effects.get("bomb_shield", 0)

        sym, run = _best_run(symbols)
        if run >= 3:
            pay = self.SYMBOLS[sym]["pay"].get(run, 0)
            is_item = (pay == "item")
            mult = 5.0 if is_item else float(pay)

            if sym == "💣" and mult < 0 and bomb_shield > 0:
                mult *= max(0.0, 1 - bomb_shield)

            if self.SYMBOLS[sym]["reroll"]:
                return {"action": "reroll", "mult": mult, "item": is_item,
                        "sym": sym, "run": run, "reason": "unstable"}
            return {"action": "win", "mult": mult, "item": is_item,
                    "sym": sym, "run": run}

        # Паттерны: не должны содержать 🔥
        if "🔥" not in symbols:
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

    def _evaluate_line(self, symbols, effects=None):
        """Оценивает одну линию для продвинутой крутки."""
        effects = effects or {}
        bomb_shield = effects.get("bomb_shield", 0)
        sym, run = _best_run(symbols)
        if run >= 3:
            pay = self.SYMBOLS[sym]["pay"].get(run, 0)
            is_item = pay == "item"
            mult = 5.0 if is_item else float(pay)
            if sym == "💣" and mult < 0 and bomb_shield > 0:
                mult *= max(0.0, 1 - bomb_shield)
            result = {
                "won": True,
                "mult": mult,
                "desc": f"{sym} × {run}",
                "unstable": self.SYMBOLS[sym]["reroll"],
                "item": is_item,
            }
            return result

        if "🔥" not in symbols:
            for pattern in self.PATTERNS:
                if _match_pattern(symbols, pattern["pattern"]):
                    return {
                        "won": True,
                        "mult": float(pattern.get("mult", 1)),
                        "desc": pattern.get("name", "Особый паттерн"),
                        "unstable": False,
                        "item": False,
                    }

        return {
            "won": False, "mult": 0.0, "desc": "проигрыш",
            "unstable": False, "item": False,
        }

    def _evaluate_grid(self, grid, effects=None):
        """Оценивает три линии и общий бонус за число выигравших."""
        line_results = [
            self._evaluate_line(line, effects)
            for line in grid
        ]
        lines_won = sum(result["won"] for result in line_results)
        multiplier_sum = sum(
            result["mult"] for result in line_results if result["won"]
        )
        line_bonus = 4 if lines_won == 3 else 2 if lines_won == 2 else 1
        reroll_grid = all(result["unstable"] for result in line_results)
        if reroll_grid:
            action = "reroll"
        elif lines_won:
            action = "win"
        else:
            action = "loss"
        return {
            "action": action,
            "total_mult": multiplier_sum * line_bonus,
            "lines_won": lines_won,
            "descriptions": [result["desc"] for result in line_results],
            "reroll_grid": reroll_grid,
            "line_bonus": line_bonus,
            "line_results": line_results,
            "is_item": any(result["item"] for result in line_results),
        }

    # ---------- ОТРИСОВКА ----------

    async def _safe_edit(self, message, text, **kwargs):
        async with self._edit_lock:
            while True:
                elapsed = time.time() - self._last_edit
                if elapsed < 1.1:
                    await asyncio.sleep(1.1 - elapsed)
                self._last_edit = time.time()
                try:
                    await message.edit_text(text, **kwargs)
                    return
                except TelegramRetryAfter as error:
                    elapsed = time.time() - self._last_edit
                    await asyncio.sleep(max(error.retry_after + 1, 1.1 - elapsed))
                except TelegramBadRequest:
                    return

    async def _safe_answer(self, query, *args, **kwargs):
        try:
            await query.answer(*args, **kwargs)
        except Exception:
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

    async def _render_grid(self, message, name, bet, grid_display, header, extra=""):
        title = name if name == "Продвинутое казино" else f"{name} крутка"
        text = (
            f"🎰 <b>{title}</b>\n"
            f"💰 Ставка: {bet} LC\n\n"
        )
        if extra:
            text += f"{extra}\n\n"
        text += f"{header}\n<blockquote>{grid_display}</blockquote>"
        await self._safe_edit(message, text, parse_mode="HTML")

    async def _anim_reveal_grid(self, message, name, bet, grid, cfg):
        """Плавно останавливает сетку в двух коротких кадрах."""
        for columns_shown in (2, 5):
            rows = []
            for line in grid:
                shown = line[:columns_shown]
                cells = shown + ["🌫️"] * (5 - columns_shown)
                rows.append(" | ".join(cells))
            await self._render_grid(
                message, name, bet, "\n".join(rows),
                f"{cfg['label']} <b>Стоп!</b> "
                f"<code>{columns_shown}/5</code>",
            )

    async def _anim_spin(self, message, name, bet, cfg):
        frames = min(cfg["spin_frames"], 2)
        for i in range(frames):
            rnd = " | ".join(random.choice(self.NOISE) for _ in range(5))
            speed = "⏩⏩ ▶️" if i + 1 < frames else "⏩ ▶️ ▶️"
            await self._render(message, name, bet, rnd,
                               f"{cfg['label']} <i>Крутим...</i> {speed}")

    async def _anim_reveal(self, message, name, bet, symbols, cfg, header):
        await self._render(
            message, name, bet, " | ".join(symbols),
            f"{cfg['label']} {header}",
        )

    async def _anim_overheat(self, message, name, bet, symbols_before, symbols_after):
        """Показывает возгорание и взрывы клеток рядом с бомбами."""
        burned_idx = [
            i for i in range(5)
            if symbols_before[i] != symbols_after[i]
        ]
        if not burned_idx:
            return

        exploded_idx = []
        for i in burned_idx:
            if any(
                0 <= neighbor < 5 and symbols_before[neighbor] == "💣"
                for neighbor in (i - 1, i + 1)
            ):
                exploded_idx.append(i)

        line = list(symbols_before)
        for i in burned_idx:
            line[i] = "🔥"
        await self._render(
            message, name, bet, " | ".join(line),
            "🔥 <b>ВОЗГОРАНИЕ!</b>"
        )
        await asyncio.sleep(1.1)

        if exploded_idx:
            for i in exploded_idx:
                line[i] = "💥"
                await self._render(
                    message, name, bet, " | ".join(line),
                    "💥 <b>ВЗРЫВ!</b> <i>Огонь рядом с бомбой...</i>"
                )
                await asyncio.sleep(1.1)

            for i in exploded_idx:
                line[i] = "🔥"
            await self._render(
                message, name, bet, " | ".join(line),
                "🔥 <b>Всё горит!</b>"
            )
            await asyncio.sleep(1.1)

    def _apply_chain_explosion(self, symbols):
        line = list(symbols)
        explosions = 0
        chain_order = []
        step = 0

        while True:
            # Сначала фиксируем весь шаг, чтобы взрывы срабатывали одновременно.
            detonating = [
                i for i, symbol in enumerate(line)
                if symbol == "💣"
                and (
                    (i > 0 and line[i - 1] == "🔥")
                    or (i + 1 < len(line) and line[i + 1] == "🔥")
                )
            ]
            if not detonating:
                break

            step += 1
            chain_order.append((step, detonating))
            explosions += len(detonating)
            for i in detonating:
                line[i] = "🔥"
                if i > 0:
                    line[i - 1] = "🔥"
                if i + 1 < len(line):
                    line[i + 1] = "🔥"

        return line, explosions, chain_order

    async def _anim_explosion(self, message, name, bet, new_symbols, chain_order):
        if not chain_order:
            return

        await self._render(
            message, name, bet, " | ".join(new_symbols),
            f"💥 <b>Цепная реакция: {len(chain_order)}!</b> <i>Всё полыхает...</i>"
        )
        await asyncio.sleep(1.05)

    async def _anim_reroll(self, message, name, bet, reroll_count, verdict, total):
        if verdict.get("reason") == "pattern":
            header = f"✨ <b>{verdict.get('pattern_name', 'ОСОБАЯ КОМБИНАЦИЯ')}!</b>\n<i>Перекрут...</i>"
        else:
            header = "⚡ <b>Нестабильный символ!</b>\n<i>Перекрут...</i>"
        extra = f"🔄 Реролл <b>#{reroll_count}</b> • Копилка: <b>x{total:g}</b>"
        rnd = " | ".join(random.choice(self.NOISE) for _ in range(5))
        await self._render(message, name, bet, rnd, header, extra)
        await asyncio.sleep(1.05)

    async def _anim_win(self, message, name, bet, symbols, description):
        line = " | ".join(symbols)
        await self._render(message, name, bet, line,
                           f"🎉 <b>ВЫИГРЫШ!</b> ✨ 🎉 ✨\n<i>{description}</i>")
        await asyncio.sleep(1.05)

    async def _anim_bomb(self, message, name, bet, symbols, description):
        line = " | ".join(symbols)
        await self._render(
            message, name, bet, line,
            f"💣 <b>ВЗРЫВ!</b> 🧨\n<i>{description}</i>"
        )
        await asyncio.sleep(1.05)

    async def _anim_loss(self, message, name, bet, symbols):
        line = " | ".join(symbols)
        await self._render(message, name, bet, line, "😔 <i>Ничего не выпало...</i>")
        await asyncio.sleep(1.05)

    # ---------- ГЛАВНЫЙ ЦИКЛ ----------

    async def _resolve_advanced(self, message, bet, user_id, cfg, effects, stage):
        name = "Продвинутое казино"
        reroll_count = 0
        while True:
            grid = self._spin_grid(reroll_count, effects, stage)
            await self._anim_reveal_grid(message, name, bet, grid, cfg)
            verdict = self._evaluate_grid(grid, effects)

            if verdict["reroll_grid"] and reroll_count < self.MAX_REROLLS:
                reroll_count += 1
                continue
            break

        effects["_advanced_result"] = verdict
        return (
            verdict["total_mult"],
            verdict["is_item"],
            grid,
            reroll_count,
            effects,
            "🔥" in grid[1],
            0,
        )

    async def _resolve(self, message, name, bet, spin_key, user_id):
        cfg = self.SPIN_ANIM.get(spin_key, self.SPIN_ANIM["common"])
        effects = self._effects(user_id)
        staff = self.brain.db.get_staff(user_id)
        if 6 in staff:
            effects["overheat_reduction"] = 0.25
        if 8 in staff:
            effects["rare_symbol_bonus"] = 0.10
        stage, _ = self.brain.db.get_overheat_stage(user_id)
        if spin_key == "advanced":
            return await self._resolve_advanced(
                message, bet, user_id, cfg, effects, stage
            )

        total_mult = 0.0
        is_item_any = False
        reroll_count = 0
        final_symbols = []
        final_description = ""
        any_burn = False
        total_explosions = 0

        while True:
            await self._anim_spin(message, name, bet, cfg)
            symbols = self._spin(reroll_count, effects)

            # Применяем перегрев
            symbols_before = list(symbols)
            symbols, _, burned = self._apply_overheat(symbols, stage, effects)
            if burned:
                any_burn = True

            symbols, explosions, _ = self._apply_chain_explosion(symbols)
            total_explosions += explosions

            verdict = self._evaluate(symbols, effects)
            final_symbols = symbols
            if verdict["action"] == "reroll":
                header = f"🔄 <b>Перекрут #{reroll_count + 1}</b>"
            elif explosions:
                header = f"💥 <b>Цепная реакция: {explosions}!</b>"
            elif verdict["action"] == "win" and verdict["mult"] < 0:
                header = "💣 <b>ВЗРЫВ!</b>"
            elif verdict["action"] == "win":
                header = "🎉 <b>ВЫИГРЫШ!</b>"
            elif burned:
                header = "🔥 <b>Перегрев!</b>"
            else:
                header = "😔 <i>Ничего не выпало...</i>"
            await self._anim_reveal(
                message, name, bet, symbols, cfg, header
            )

            if verdict["action"] == "win":
                total_mult += verdict["mult"]
                is_item_any = is_item_any or verdict["item"]
                if verdict.get("reason") == "pattern":
                    final_description = f"Паттерн «{verdict.get('pattern_name', '?')}»"
                else:
                    final_description = f"{verdict['sym']} × {verdict['run']}"
                break
            if verdict["action"] == "reroll":
                total_mult += verdict["mult"]
                is_item_any = is_item_any or verdict["item"]
                reroll_count += 1
                if reroll_count > self.MAX_REROLLS:
                    break
                continue
            total_mult = 0
            is_item_any = False
            break
        return total_mult, is_item_any, final_symbols, reroll_count, effects, any_burn, total_explosions

    # ---------- ЗАПУСК ----------

    async def _start_game(self, message: Message, spin_key: str, bet: int):
        user_id = message.from_user.id
        self.brain.db.add_balance(user_id, "lc", -bet)

        name, _, _, spin_mult = self.SPIN_TYPES[spin_key]
        game_title = (
            "Продвинутое казино" if spin_key == "advanced"
            else f"{name} крутка"
        )
        msg = await message.answer(f"🎰 <b>{game_title}</b>\n\nКрутим...",
                                   parse_mode="HTML")

        self.brain.db.increment_badge_rolls(user_id)

        total_mult, is_item, symbols, rerolls, effects, any_burn, explosions = await self._resolve(
            msg, name, bet, spin_key, user_id
        )

        mult_bonus = effects.get("mult_bonus", 0)
        effective_mult = total_mult * (1 + mult_bonus) if total_mult > 0 else total_mult

        # Штраф за 🔥
        advanced_result = (
            effects.get("_advanced_result") if spin_key == "advanced" else None
        )
        fire_count = (
            sum(line.count("🔥") for line in symbols)
            if spin_key == "advanced" else symbols.count("🔥")
        )
        fire_reduction = effects.get("fire_reduction", 0)
        penalty_per_fire = self.FIRE_PENALTY * (1 - min(fire_reduction, 1.0))
        fire_factor = max(0.0, 1 - penalty_per_fire * fire_count)
        win_mult = effects.get("win_mult", 1)

        if effective_mult > 0:
            win_amount = math.ceil(
                bet * effective_mult * spin_mult * win_mult * fire_factor
            )
        else:
            # Fire reduces payouts, but must not soften negative bomb multipliers.
            win_amount = math.ceil(bet * effective_mult * spin_mult)

        applied_loss = 0
        loss_was_capped = False
        if win_amount < 0:
            # The bet is already deducted, so cap the bomb penalty to the remaining LC.
            current_lc = self.brain.db.get_balance(user_id, "lc")
            applied_loss = min(abs(win_amount), max(0, current_lc))
            loss_was_capped = applied_loss < abs(win_amount)
            if applied_loss:
                self.brain.db.add_balance(user_id, "lc", -applied_loss)

        if win_amount > 0:
            self.brain.db.add_balance(user_id, "lc", win_amount)
            self.brain.db.add_result(user_id, True)
            self.brain.db.add_streak_win(user_id)
        else:
            self.brain.db.add_result(user_id, False)
            self.brain.db.add_streak_loss(user_id)

        self.brain.db.add_bet_stats(user_id, bet, win_amount)

        # Базовый прирост + ускорение от экипированных значков.
        overheat_gain = (
            1 if spin_key == "advanced"
            else 1 + int(effects.get("overheat_speed", 0))
        )
        self.brain.db.add_overheat(
            user_id,
            overheat_gain,
            reduction=effects.get("overheat_reduction", 0),
        )

        xp_gain = spin_mult * 20 * (2 if win_amount > 0 else 1)
        xp_bonus = effects.get("xp_bonus", 0)
        xp_gain = int(xp_gain * (1 + xp_bonus))
        level, xp, leveled_up = self.brain.db.add_xp(user_id, xp_gain)
        xp_needed = 100 * (level + 1)

        # --- Поломка значков ---
        break_messages = []
        try:
            from item_system import should_break, handle_break
            from cosmetics import BADGES
            equipped = self.brain.db.get_user_badges_full(user_id)
            trigger = "win" if win_amount > 0 else "loss"
            for slot in list(equipped.keys()):
                info = equipped[slot]
                bid = info["badge_id"]
                badge = BADGES.get(bid)
                if not badge:
                    continue
                if should_break(badge, "roll") or should_break(badge, trigger):
                    brk_msg = handle_break(self.brain, user_id, bid, slot)
                    if brk_msg:
                        break_messages.append(brk_msg)
                else:
                    hp = info["hp"]
                    if hp != -1:
                        new_hp = hp - 1
                        if new_hp <= 0:
                            brk_msg = handle_break(self.brain, user_id, bid, slot)
                            if brk_msg:
                                break_messages.append(brk_msg)
                        else:
                            self.brain.db.set_badge_hp(user_id, slot, new_hp)
        except Exception:
            pass

        # --- Результат ---
        if spin_key == "advanced":
            slot_grid = "\n".join(" | ".join(line) for line in symbols)
            result = f"🎰 <b>{game_title}</b>\n\n"
            result += f"💰 Ставка: {bet} LC\n\n"
            result += f"<blockquote>{slot_grid}</blockquote>\n\n"
            for index, line_result in enumerate(
                advanced_result["line_results"], start=1
            ):
                if line_result["won"]:
                    result += (
                        f"✅ Линия {index}: {line_result['desc']} "
                        f"(x{line_result['mult']:g})\n"
                    )
                else:
                    result += f"❌ Линия {index}: проигрыш\n"
            if advanced_result["lines_won"]:
                bonus_text = (
                    f" (бонус ×{advanced_result['line_bonus']})"
                    if advanced_result["line_bonus"] > 1 else ""
                )
                result += (
                    f"\n🎉 Выиграло линий: "
                    f"<b>{advanced_result['lines_won']}</b>{bonus_text}\n"
                )
            if rerolls:
                result += f"🔄 Общих рероллов: <b>{rerolls}</b>\n"
        else:
            slot_line = " | ".join(symbols)
            result = f"🎰 <b>{game_title}</b>\n\n"
            result += f"💰 Ставка: {bet} LC\n\n"
            result += f"<blockquote>{slot_line}</blockquote>\n\n"

        if rerolls > 0:
            if spin_key != "advanced":
                result += f"🔄 Рероллов: <b>{rerolls}</b>\n"

        if fire_count > 0:
            total_penalty = int(penalty_per_fire * fire_count * 100)
            result += f"🔥 Сгорело ячеек: <b>{fire_count}</b> (−{total_penalty}%)\n"

        if explosions > 0:
            result += f"💥 Взорвалось динамита: <b>{explosions}</b>\n"

        if is_item:
            award_msg = self._award_badge(user_id)
            if award_msg:
                result += award_msg + "\n"
            else:
                result += "🎁 Выбил предмет, но выдать не удалось.\n"

        if win_amount > 0:
            final_mult = effective_mult * spin_mult * fire_factor
            if spin_key == "advanced":
                result += f"💰 Итого: <b>+{win_amount} LC</b> (x{final_mult:g})"
            else:
                result += f"✅ <b>+{win_amount} LC</b> (x{final_mult:g})"
            if mult_bonus > 0:
                result += f" <i>(+{int(mult_bonus*100)}% от значков)</i>"
            result += "\n"
        elif win_amount < 0:
            result += f"💣 <b>-{applied_loss} LC</b>"
            if loss_was_capped:
                result += " <i>(баланс не может уйти в минус)</i>"
            result += "\n"
        else:
            result += "❌ Ничего...\n"

        result += f"\n⭐ +{xp_gain} XP" + (" (x2!)" if win_amount > 0 else "")
        if xp_bonus > 0:
            result += f" <i>(+{int(xp_bonus*100)}% от значков)</i>"

        if leveled_up:
            result += f"\n🎉 <b>НОВЫЙ УРОВЕНЬ: {level}!</b>"

        result += f"\n⭐ Ур. {level} — XP {xp}/{xp_needed}"
        result += f"\n💰 Баланс LC: {self.brain.db.get_balance(user_id, 'lc')}"

        # Показываем перегрев после спина
        new_stage, new_score = self.brain.db.get_overheat_stage(user_id)
        oh_icon, _, _ = self.OVERHEAT_STAGES[new_stage]
        result += f"\n🔥 Перегрев: {oh_icon} <code>({new_score}/100)</code>"

        if break_messages:
            result += "\n\n" + "\n".join(break_messages)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Ещё", callback_data=f"again_{spin_key}")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="play")]])
        await self._safe_edit(msg, result, reply_markup=kb, parse_mode="HTML")

    # ---------- МЕНЮ ----------

    async def cb_play(self, query: CallbackQuery, state: FSMContext = None):
        try:
            if state:
                await state.clear()
            user_id = query.from_user.id
            last_free = self.brain.db.get_last_free_lc(user_id)
            tickets = self.brain.db.get_tickets(user_id)
            free_ticket_awarded = False
            if time.time() - last_free >= 3600 and tickets < self.MAX_TICKETS:
                self.brain.db.add_tickets(user_id, 1)
                self.brain.db.set_last_free_lc(user_id, int(time.time()))
                tickets = self.brain.db.get_tickets(user_id)
                free_ticket_awarded = True

            lc = self.brain.db.get_balance(user_id, "lc")
            level, xp = self.brain.db.get_level_xp(user_id)
            xp_needed = 100 * (level + 1)

            # Перегрев
            oh_stage, oh_score = self.brain.db.get_overheat_stage(user_id)
            oh_icon, _, _ = self.OVERHEAT_STAGES[oh_stage]

            # Эффекты
            effects = self._effects(user_id)
            eff_line = ""
            if effects:
                try:
                    from cosmetics import describe_effect_dict
                    eff_line = f"\n✨ <i>{describe_effect_dict(effects)}</i>"
                except Exception:
                    pass

            text = (f"🎰 <b>Игровой зал LuckyScoin</b>\n\n"
                    f"💰 Баланс LC: {lc}\n"
                    f"⭐ Уровень: {level} (XP: {xp}/{xp_needed})\n"
                    f"🔥 Перегрев: {oh_icon} <code>({oh_score}/100)</code>"
                    f"{eff_line}\n\n"
                    f"Выбери тип крутки:")
            if free_ticket_awarded:
                text += "\n\n🎁 Получен бесплатный билет на рулетку!"
            elif tickets >= self.MAX_TICKETS:
                text += "\n\n🎟 Максимум билетиков на руках."

            buttons = []
            for key, (name, min_b, max_b, mult) in self.SPIN_TYPES.items():
                req = self.LEVEL_REQ[key]
                button_name = (
                    "🎰 Продвинутое казино"
                    if key == "advanced" else name
                )
                if level >= req:
                    buttons.append([InlineKeyboardButton(
                        text=f"{button_name} ({min_b}-{max_b} LC)",
                        callback_data=f"choose_{key}")])
                else:
                    buttons.append([InlineKeyboardButton(
                        text=f"🔒 {button_name} (с {req} ур.)",
                        callback_data="locked")])
            buttons.append([InlineKeyboardButton(
                text=f"🎟 Рулетка ({tickets} билетов)",
                callback_data="roulette",
            )])
            buttons.append([InlineKeyboardButton(text="💱 Обменять LC на SC", callback_data="exchange")])
            buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])

            await self._safe_edit(
                query.message, text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML",
            )
            await self._safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка игрового меню: {error}")
            await self._safe_answer(query, "Не удалось открыть игровое меню.", show_alert=True)

    async def cb_locked(self, query: CallbackQuery):
        try:
            await self._safe_answer(query, "🔒 Недостаточный уровень!", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка заблокированной крутки: {error}")

    async def _ask_bet(self, query, spin_key, state):
        if spin_key not in self.SPIN_TYPES:
            return await self._safe_answer(query, "Неизвестный тип!", show_alert=True)
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        if level < self.LEVEL_REQ.get(spin_key, 0):
            return await self._safe_answer(
                query, f"Нужен уровень {self.LEVEL_REQ[spin_key]}!",
                show_alert=True,
            )
        name, min_b, max_b, mult = self.SPIN_TYPES[spin_key]
        await state.set_state(BetStates.waiting_for_bet)
        await state.update_data(spin_key=spin_key, min_bet=min_b, max_bet=max_b)
        title = "Продвинутое казино" if spin_key == "advanced" else f"{name} крутка"
        text = (f"🎰 <b>{title}</b>\n\n"
                f"Введи ставку в LC (от {min_b} до {max_b}).")
        keyboard_rows = [
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_bet")]
        ]
        if spin_key == "advanced":
            keyboard_rows.insert(0, [InlineKeyboardButton(
                text="📐 Свои паттерны", callback_data="advanced_patterns"
            )])
        await self._safe_edit(
            query.message, text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
            parse_mode="HTML")
        await self._safe_answer(query)

    async def cb_choose_type(self, query: CallbackQuery, state: FSMContext):
        try:
            await self._ask_bet(query, query.data.split("_", 1)[1], state)
        except Exception as error:
            print(f"⚠️ Ошибка выбора типа крутки: {error}")
            await self._safe_answer(query, "Не удалось выбрать крутку.", show_alert=True)

    async def cb_spin_again(self, query: CallbackQuery, state: FSMContext):
        try:
            await self._ask_bet(query, query.data.split("_", 1)[1], state)
        except Exception as error:
            print(f"⚠️ Ошибка повторного выбора крутки: {error}")
            await self._safe_answer(query, "Не удалось повторить крутку.", show_alert=True)

    async def cb_advanced_patterns(self, query: CallbackQuery):
        try:
            # Позже здесь появится настройка собственных паттернов.
            await self._safe_answer(query, "📐 Свои паттерны — скоро!", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка заглушки паттернов: {error}")
            await self._safe_answer(query, "Не удалось открыть паттерны.", show_alert=True)

    async def cb_cancel_bet(self, query: CallbackQuery, state: FSMContext):
        await state.clear()
        await self.cb_play(query, state)

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

    # ---------- РУЛЕТКА ЗА БИЛЕТИКИ ----------

    @classmethod
    def _pick_roulette_result(cls):
        """Выбирает приз согласно заданным процентным шансам."""
        prizes = [prize for prize in cls.ROULETTE_PRIZES if prize["chance"] > 0]
        return random.choices(
            prizes,
            weights=[prize["chance"] for prize in prizes],
            k=1,
        )[0]

    def _roulette_keyboard(self):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🎰 Крутить (1 билет)", callback_data="roulette_spin"
            )],
            [InlineKeyboardButton(
                text="🛒 Купить билет (5 SC)", callback_data="roulette_buy"
            )],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="play")],
        ])

    async def cb_roulette(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            tickets = self.brain.db.get_tickets(query.from_user.id)
            from cosmetics import BADGES

            prize_lines = []
            for prize in self.ROULETTE_PRIZES:
                amount = f"{prize['amount']:,}".replace(",", " ")
                line = (
                    f"{prize['symbol']} {prize['name']} — {prize['chance']}%: "
                    f"+{amount} {prize['currency'].upper()}"
                )
                if "medal" in prize and "medal_chance" in prize:
                    medal = BADGES[prize["medal"]]
                    medal_chance = f"{prize['medal_chance'] * 100:g}%"
                    line += f" · {medal_chance} шанс на {medal['name']}"
                prize_lines.append(line)
            text = (
                "🎟 <b>Билетная рулетка</b>\n\n"
                f"🎫 Билетиков: <b>{tickets}/{self.MAX_TICKETS}</b>\n"
                + "\n".join(prize_lines)
                + "\n\n"
                "🎰 Выбери действие:"
            )
            await self._safe_edit(
                query.message, text,
                reply_markup=self._roulette_keyboard(),
                parse_mode="HTML",
            )
            await self._safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка открытия рулетки: {error}")
            await self._safe_answer(query, "Не удалось открыть рулетку.", show_alert=True)

    async def roulette_buy(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            user_id = query.from_user.id
            tickets = self.brain.db.get_tickets(user_id)
            if tickets >= self.MAX_TICKETS:
                await self._safe_answer(query, "🎟 Максимум билетиков.", show_alert=True)
                return
            balance = self.brain.db.get_balance(user_id, "sc")
            if balance < self.ROULETTE_TICKET_PRICE_SC:
                await self._safe_answer(
                    query, "Недостаточно SC. Нужно 5 SC.", show_alert=True
                )
                return

            self.brain.db.add_balance(user_id, "sc", -self.ROULETTE_TICKET_PRICE_SC)
            self.brain.db.add_tickets(user_id, 1)
            tickets = self.brain.db.get_tickets(user_id)
            text = (
                "🎟 <b>Билетная рулетка</b>\n\n"
                f"✅ Куплен 1 билет за {self.ROULETTE_TICKET_PRICE_SC} SC.\n"
                f"🎫 Билетиков: <b>{tickets}/{self.MAX_TICKETS}</b>\n"
                "🎰 Выбери действие:"
            )
            await self._safe_edit(
                query.message, text,
                reply_markup=self._roulette_keyboard(),
                parse_mode="HTML",
            )
            await self._safe_answer(query, "✅ Билет куплен!")
        except Exception as error:
            print(f"⚠️ Ошибка покупки билетика: {error}")
            await self._safe_answer(query, "Не удалось купить билет.", show_alert=True)

    async def roulette_spin(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            user_id = query.from_user.id
            if not self.brain.db.spend_ticket(user_id):
                await self._safe_answer(query, "Нет билетиков для крутки.", show_alert=True)
                return
            prize = self._pick_roulette_result()
            medal_won = (
                "medal" in prize
                and random.random() < prize["medal_chance"]
            )
            symbols = [entry["symbol"] for entry in self.ROULETTE_PRIZES]
            slots = [random.choice(symbols) for _ in range(4)] + [prize["symbol"]]
            await self._safe_answer(query)
            await self._anim_roulette(
                query.message, user_id, prize, slots, medal_won
            )
        except Exception as error:
            print(f"⚠️ Ошибка крутки рулетки: {error}")
            await self._safe_answer(query, "Не удалось выполнить крутку.", show_alert=True)

    async def _anim_roulette(self, message, user_id, prize, slots, medal_won):
        """Показывает не более пяти кадров, с паузой 1,1 секунды."""
        for frame, position in enumerate((0, 1, 2, 3, 4)):
            if frame:
                await asyncio.sleep(1.1)
            arrow = "   ".join(
                "▼" if index == position else "　"
                for index in range(len(slots))
            )
            text = (
                "🎟 <b>Билетная рулетка</b>\n\n"
                f"<code>{arrow}</code>\n"
                f"{' | '.join(slots)}\n\n"
                f"<i>Крутим... {frame + 1}/5</i>"
            )

            if frame == 4:
                self.brain.db.add_balance(
                    user_id, prize["currency"], prize["amount"]
                )
                result_line = (
                    f"🎉 Выпало: <b>{prize['symbol']} {prize['name']}</b>\n"
                    f"💰 Приз: <b>+{prize['amount']} {prize['currency'].upper()}</b>\n"
                    f"🎫 Осталось билетиков: "
                    f"<b>{self.brain.db.get_tickets(user_id)}/{self.MAX_TICKETS}</b>"
                )
                if medal_won:
                    from cosmetics import BADGES

                    badge = BADGES[prize["medal"]]
                    self.brain.db.add_item(user_id, badge["shop_id"])
                    result_line += (
                        f"\n🎖 Дополнительно получена медаль: "
                        f"<b>{badge['name']}</b>"
                    )
                text = (
                    "🎟 <b>Билетная рулетка</b>\n\n"
                    f"<code>{arrow}</code>\n"
                    f"{' | '.join(slots)}\n\n"
                    f"{result_line}"
                )

            await self._safe_edit(
                message, text,
                reply_markup=self._roulette_keyboard(),
                parse_mode="HTML",
            )

    async def cb_exchange(self, query: CallbackQuery):
        user_id = query.from_user.id
        lc = self.brain.db.get_balance(user_id, "lc")
        if lc < 1000:
            return await query.answer("Нужно минимум 1000 LC.", show_alert=True)
        amount = (lc // 1000) * 1000
        sc = amount // 1000
        self.brain.db.add_balance(user_id, "lc", -amount)
        self.brain.db.add_balance(user_id, "sc", sc)
        await query.answer(f"💱 {amount} LC → {sc} SC!", show_alert=True)
        await self.cb_play(query)