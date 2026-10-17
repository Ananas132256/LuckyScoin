import random
import time
import asyncio
import math
import html
from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from utils import (
    format_sc, is_current_screen, nav_footer, safe_answer, with_hero,
)


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


class Game:
    # ============================================================
    #  НАСТРОЙКИ
    # ============================================================
    LEVEL_REQ = {
        "mini": 0, "safe": 1, "common": 3, "uncommon": 5,
        "rare": 25, "ultra": 50, "epic": 100,
        "advanced": 12, "hardcore": 65,
    }
    STICKY_CHANCE = 0.20
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

    SYMBOLS = {
        "7️⃣": {"weight": 1,   "pay": {3: 77,     4: 77,     5: 777  }, "reroll": False},
        "🎲": {"weight": 5,   "pay": {3: 50,     4: 100,    5: 200  }, "reroll": True},
        "🍀": {"weight": 50,  "pay": {3: 5,      4: 7.5,    5: 25   }, "reroll": True},
        "💣": {"weight": 200, "pay": {3: -0.5,   4: -0.75,  5: -0.99}, "reroll": False},
        "🍎": {"weight": 225, "pay": {3: 1.5,    4: 4,      5: 8   }, "reroll": False},
        "🍍": {"weight": 225, "pay": {3: 1.5,    4: 4,      5: 8   }, "reroll": False},
        "🍭": {"weight": 150, "pay": {3: 2,      4: 5,      5: 10   }, "reroll": True},
        "🍋": {"weight": 225, "pay": {3: 1.5,    4: 4,      5: 8   }, "reroll": False},
        "🪙": {"weight": 50,  "pay": {3: 5,      4: 7.5,    5: 25   }, "reroll": True},
        "⚙️": {"weight": 50,  "pay": {3: "item", 4: "item", 5: "item"}, "reroll": False},
        "💎": {"weight": 50,  "pay": {3: 5,      4: 7.5,    5: 25   }, "reroll": False},
        "🌀": {"weight": 5,   "pay": {},         "reroll": False, "special": "cyclone"},
    }

    SYMBOL_GROUPS = {
        "fruits": {"🍎", "🍍", "🍭", "🍋"},
        "specials": {"7️⃣", "🎲", "🍀", "🪙", "⚙️", "💎"},
        "bombs": {"💣"},
        "all": set(SYMBOLS) - {"🔥"},
    }

    PATTERNS = [
    # ============ ВЕРТИКАЛИ (5) ============
    {"name": "Вертикаль 1", "cells": [(0, 0), (1, 0), (2, 0)], "group": "all", "same": True, "mult": 3},
    {"name": "Вертикаль 2", "cells": [(0, 1), (1, 1), (2, 1)], "group": "all", "same": True, "mult": 3},
    {"name": "Вертикаль 3", "cells": [(0, 2), (1, 2), (2, 2)], "group": "all", "same": True, "mult": 3},
    {"name": "Вертикаль 4", "cells": [(0, 3), (1, 3), (2, 3)], "group": "all", "same": True, "mult": 3},
    {"name": "Вертикаль 5", "cells": [(0, 4), (1, 4), (2, 4)], "group": "all", "same": True, "mult": 3},

    # ============ ДИАГОНАЛИ ↘ (3) ============
    {"name": "Диагональ ↘ 1", "cells": [(0, 0), (1, 1), (2, 2)], "group": "all", "same": True, "mult": 3},
    {"name": "Диагональ ↘ 2", "cells": [(0, 1), (1, 2), (2, 3)], "group": "all", "same": True, "mult": 3},
    {"name": "Диагональ ↘ 3", "cells": [(0, 2), (1, 3), (2, 4)], "group": "all", "same": True, "mult": 3},

    # ============ ДИАГОНАЛИ ↗ (3) ============
    {"name": "Диагональ ↗ 3", "cells": [(0, 2), (1, 1), (2, 0)], "group": "all", "same": True, "mult": 3},
    {"name": "Диагональ ↗ 4", "cells": [(0, 3), (1, 2), (2, 1)], "group": "all", "same": True, "mult": 3},
    {"name": "Диагональ ↗ 5", "cells": [(0, 4), (1, 3), (2, 2)], "group": "all", "same": True, "mult": 3},

    # ============ КРЕСТЫ (3) ============
    {"name": "Крест 2", "cells": [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)], "group": "all", "same": True, "mult": 5},
    {"name": "Крест 3", "cells": [(0, 2), (1, 1), (1, 2), (1, 3), (2, 2)], "group": "all", "same": True, "mult": 5},
    {"name": "Крест 4", "cells": [(0, 3), (1, 2), (1, 3), (1, 4), (2, 3)], "group": "all", "same": True, "mult": 5},

    # ============ РАМКА (1) ============
    {"name": "Рамка", "cells": [(0, 0), (0, 4), (2, 0), (2, 4)], "group": "all", "same": True, "mult": 4},

    # ============ ДЖЕКПОТ (1) ============
    {"name": "ДЖЕКПОТ", "cells": [(r, c) for r in range(3) for c in range(5)], "group": "all", "same": True, "mult": 50},
]

    SPIN_TYPES = {
        "mini":      ("Mini",      1,     3,       1),
        "safe":      ("Safe",      5,     25,      0.9),
        "common":    ("Common",    1,     5,       1  ),
        "uncommon":  ("Uncommon",  10,    1000,    2  ),
        "rare":      ("Rare",      1000,  10000,   4  ),
        "ultra":     ("Ultra",     10000, 100000,  8  ),
        "epic":      ("Epic",      100000,1000000, 16 ),
        "advanced":  ("Advanced",  5000,   5000,    0.5),
        "hardcore":  ("Hardcore",  100000,10000000,32 ),
    }
    REGULAR_SPINS = (
        "mini", "safe", "common", "uncommon", "rare", "ultra", "epic",
    )
    EFFECT_SPINS = ("advanced", "hardcore")
    FRUIT_SYMBOLS = ("🍎", "🍍", "🍭", "🍋")
    HARDCORE_SYMBOLS = (*FRUIT_SYMBOLS, "💣")

    SPIN_ANIM = {
        "common":   {"spin_frames": 3, "spin_delay": 0.1, "stop_delay": 0.1, "last_stop_delay": 0.10, "label": "▶️"},
        "uncommon": {"spin_frames": 3, "spin_delay": 0.1, "stop_delay": 0.1, "last_stop_delay": 0.1, "label": "⚡"},
        "rare":     {"spin_frames": 3, "spin_delay": 0.1, "stop_delay": 0.1, "last_stop_delay": 0.1, "label": "💫"},
        "ultra":    {"spin_frames": 3, "spin_delay": 0.1, "stop_delay": 0.1, "last_stop_delay": 0.1, "label": "🔥"},
        "epic":     {"spin_frames": 3, "spin_delay": 0.1, "stop_delay": 0.1, "last_stop_delay": 0.1, "label": "👾"},
        "advanced": {
            "spin_frames": 5, "spin_delay": 0.1, "stop_delay": 0.1,
            "last_stop_delay": 0.1, "label": "🎰",
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
        ("🔥🔥🔥🔥🔥", 0.50, 0.25),   # 5
    ]
    FIRE_PENALTY = 0.20   # -20% за каждый 🔥
    ROULETTE_TICKET_PRICE_SC = 5
    MAX_TICKETS = 10
    ROULETTE_PRIZES = (
        {"symbol": "💰", "name": "Деньги", "chance": 35, "currency": "lc", "amount": 1000},
        {"symbol": "🎁", "name": "", "chance": 30, "currency": "lc", "amount": 2500},
        {"symbol": "🍀", "name": "Клевер", "chance": 20, "currency": "lc", "amount": 5000},
        {"symbol": "💎", "name": "Бриллиант", "chance": 10, "currency": "lc", "amount": 10000},
        {
            "symbol": "👑", "name": "Корона", "chance": 4,
            "currency": "lc", "amount": 100000,
            "medal": "leaf", "medal_chance": 0.25,
        },
        {
            "symbol": "🌌", "name": "Галактика", "chance": 1,
            "currency": "lc", "amount": 500000,
            "medal": "four_leaf_clover", "medal_chance": 0.10,
        },
    )

    def __init__(self, brain):
        self.brain = brain
        self._last_edit = 0
        self._edit_lock = asyncio.Lock()

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "play")(self.cb_play)
        dp.callback_query(F.data == "regular_list")(self.cb_regular_list)
        dp.callback_query(F.data == "effects_list")(self.cb_effects_list)
        dp.callback_query(F.data.startswith("choose_"))(self.cb_choose_type)
        dp.callback_query(F.data.startswith("again_"))(self.cb_spin_again)
        dp.callback_query(F.data == "cancel_bet")(self.cb_cancel_bet)
        dp.callback_query(F.data == "locked")(self.cb_locked)
        dp.callback_query(F.data == "roulette")(self.cb_roulette)
        dp.callback_query(F.data == "roulette_buy")(self.roulette_buy)
        dp.callback_query(F.data == "roulette_spin")(self.roulette_spin)
        dp.message(BetStates.waiting_for_bet)(self.on_bet_input)

    # ---------- ЭФФЕКТЫ ----------

    def _effects(self, user_id):
        try:
            from content.effects import get_total_effects
            return get_total_effects(self.brain, user_id) or {}
        except Exception:
            return {}

    def _pick_random_badge(self, user_id):
        from content.catalog import BADGES, is_unlocked

        user = self.brain.db.get_user(user_id)
        rooms = self.brain.db.get_rooms(user_id) or []
        room_level = max(rooms) if rooms else 0

        equipped = self.brain.db.get_user_badges(user_id)
        owned_ids = {bid for bid in equipped.values() if bid}
        # Hidden badges are reserved for specific game events, not random drops.
        badge_weights = [
            (badge_id, self.ITEM_RARITY_WEIGHTS[badge.get("rarity")])
            for badge_id, badge in BADGES.items()
            if badge.get("rarity") in self.ITEM_RARITY_WEIGHTS
            and not badge.get("hidden")
            and badge_id not in owned_ids
            and is_unlocked(badge, user, room_level)
        ]
        if not badge_weights:
            return None

        badge_ids, weights = zip(*badge_weights)
        return random.choices(badge_ids, weights=weights, k=1)[0]

    def _award_badge(self, user_id):
        try:
            from content.catalog import BADGES, badge_slots_for_level

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
            self.brain.db.add_item(user_id, shop_id, 1, soulbound=True)

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

    def _cyclone_equipped(self, user_id):
        if user_id is None:
            return False
        return "halloween_cyclone" in self.brain.db.get_user_badges(
            user_id
        ).values()

    def _apply_cyclone(self, symbols, user_id):
        result = list(symbols)
        if "🌀" not in result or not self._cyclone_equipped(user_id):
            return result
        n = len(result)
        index = next(
            (position for position, symbol in enumerate(result) if symbol == "🌀"),
            None,
        )
        if index is None or n < 2:
            return result

        left = (index - 1) % n
        right = (index + 1) % n
        result[left], result[right] = result[right], result[left]

        from collections import Counter
        counts = Counter(
            symbol for position, symbol in enumerate(result)
            if position != index and symbol != "🌀"
        )
        if not counts:
            return result

        max_count = max(counts.values())
        candidates = [
            symbol for symbol, count in counts.items()
            if count == max_count
        ]

        def pay_value(symbol):
            pay = self.SYMBOLS.get(symbol, {}).get("pay", {})
            return max(
                (
                    value for value in pay.values()
                    if isinstance(value, (int, float))
                ),
                default=0,
            )

        winner = max(
            candidates,
            key=lambda symbol: (pay_value(symbol), -result.index(symbol)),
        )
        result[index] = winner
        return result

    @staticmethod
    def _jack_multipliers(bet, now=None):
        from config import (
            HALLOWEEN_END, HALLOWEEN_JACK_END, HALLOWEEN_START,
        )
        from utils import in_date_range

        cash_multiplier = 3 if bet % 2 == 0 else 1
        xp_multiplier = 2 if bet % 2 else 1
        if in_date_range(HALLOWEEN_START, (2026, 10, 30), now):
            cash_multiplier *= 2
            xp_multiplier *= 2
        elif in_date_range(HALLOWEEN_JACK_END, HALLOWEEN_END, now):
            cash_multiplier *= 3
            xp_multiplier *= 3
        return cash_multiplier, xp_multiplier

    def _spin(self, reroll_count=0, effects=None, spin_key=None, user_id=None):
        effects = effects or {}
        luck = effects.get("luck", 0)
        rare_symbol_bonus = effects.get("rare_symbol_bonus", 0)
        if spin_key == "mini" or spin_key == "safe":
            keys = list(self.FRUIT_SYMBOLS)
        elif spin_key == "hardcore":
            keys = list(self.HARDCORE_SYMBOLS)
        else:
            keys = list(self.SYMBOLS.keys())
            if not self._cyclone_equipped(user_id):
                keys.remove("🌀")
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
        cell_count = 3 if spin_key == "mini" else 5
        for _ in range(cell_count):
            if result and random.random() < self.STICKY_CHANCE:
                result.append(result[-1])
            else:
                result.append(random.choices(keys, weights=weights, k=1)[0])
        return result

    def _spin_grid(self, reroll_count=0, effects=None, stage=0, user_id=None):
        """Генерирует три линии; перегрев применяется только к центральной."""
        grid = [
            self._spin(reroll_count, effects, "advanced", user_id)
            for _ in range(3)
        ]
        grid[1], _, _ = self._apply_overheat(grid[1], stage, effects)
        return grid

    def _apply_overheat(self, symbols, stage, effects=None):
        """
        Применяет перегрев ПОСЛЕ выпадения символов.
        Возвращает (новая_линия, сгорела_ли_вся, индексы_сгоревших_ячеек).
        """
        effects = effects or {}
        # fire_shield уменьшает шанс загорания (0.5 = -50% шанс)
        shield = effects.get("fire_shield", 0)
        icon, cell_chance, line_chance = self.OVERHEAT_STAGES[stage]

        cell_chance = max(0.0, cell_chance * (1 - shield))
        line_chance = max(0.0, line_chance * (1 - shield))

        # Шанс что вся линия сгорит
        if line_chance > 0 and random.random() < line_chance:
            return ["🔥"] * len(symbols), True, list(range(len(symbols)))

        # Иначе — каждая ячейка независимо
        result = list(symbols)
        burned_indices = []
        for i in range(len(symbols)):
            if random.random() < cell_chance:
                result[i] = "🔥"
                burned_indices.append(i)
        return result, False, burned_indices

    def _evaluate(self, symbols, effects=None, spin_key=None, user_id=None):
        effects = effects or {}
        bomb_shield = effects.get("bomb_shield", 0)
        symbols = self._apply_cyclone(symbols, user_id)

        sym, run = _best_run(symbols)
        if run >= 3:
            pay = self.SYMBOLS[sym]["pay"].get(run, 0)
            is_item = (pay == "item")
            mult = 5.0 if is_item else float(pay)

            if sym == "💣" and mult < 0 and bomb_shield > 0:
                mult *= max(0.0, 1 - bomb_shield)

            if self.SYMBOLS[sym]["reroll"] and spin_key != "mini":
                return {"action": "reroll", "mult": mult, "item": is_item,
                        "sym": sym, "run": run, "reason": "unstable",
                        "symbols": symbols}
            return {"action": "win", "mult": mult, "item": is_item,
                    "sym": sym, "run": run, "symbols": symbols}

        return {"action": "loss", "symbols": symbols}

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

        return {
            "won": False, "mult": 0.0, "desc": "проигрыш",
            "unstable": False, "item": False,
        }

    def _match_grid_pattern(self, grid, pattern):
        cells = pattern.get("cells")
        if cells is None:
            cells = pattern.get("template")
        if not cells:
            return 0

        symbols = []
        for row, column in cells:
            if column == "c":
                return 0
            if not (0 <= row < len(grid) and 0 <= column < len(grid[row])):
                return 0
            symbols.append(grid[row][column])

        group = pattern.get("group")
        if group is not None:
            allowed_symbols = self.SYMBOL_GROUPS.get(group)
            if allowed_symbols is None or any(
                symbol not in allowed_symbols for symbol in symbols
            ):
                return 0
        if pattern.get("same", False) and len(set(symbols)) != 1:
            return 0
        return pattern["mult"]

    def _expand_patterns(self):
        """Expand grid templates into their concrete cell positions."""
        expanded = []
        for pattern in self.PATTERNS:
            cells = pattern.get("cells")
            if cells is not None:
                expanded.append(pattern)
            elif "template" in pattern:
                for column in range(5):
                    expanded.append({
                        **{
                            key: value for key, value in pattern.items()
                            if key != "template"
                        },
                        "name": (
                            f"{pattern['name']} (столбец {column + 1})"
                        ),
                        "cells": [
                            (row, column)
                            for row, _ in pattern["template"]
                        ],
                    })
            elif pattern.get("template_fn") == "diag_down":
                for start_column in range(3):
                    expanded.append({
                        **{
                            key: value for key, value in pattern.items()
                            if key != "template_fn"
                        },
                        "name": (
                            f"{pattern['name']} "
                            f"(старт {start_column + 1})"
                        ),
                        "cells": [
                            (0, start_column),
                            (1, start_column + 1),
                            (2, start_column + 2),
                        ],
                    })
            elif pattern.get("template_fn") == "diag_up":
                for start_column in range(2, 5):
                    expanded.append({
                        **{
                            key: value for key, value in pattern.items()
                            if key != "template_fn"
                        },
                        "name": (
                            f"{pattern['name']} "
                            f"(старт {start_column + 1})"
                        ),
                        "cells": [
                            (0, start_column),
                            (1, start_column - 1),
                            (2, start_column - 2),
                        ],
                    })
            elif pattern.get("template_fn") == "cross":
                for center_column in range(1, 4):
                    expanded.append({
                        **{
                            key: value for key, value in pattern.items()
                            if key != "template_fn"
                        },
                        "name": (
                            f"{pattern['name']} "
                            f"(центр {center_column + 1})"
                        ),
                        "cells": [
                            (0, center_column),
                            (1, center_column - 1),
                            (1, center_column),
                            (1, center_column + 1),
                            (2, center_column),
                        ],
                    })
        return expanded

    async def _anim_pattern_check(self, message, bet, grid, user_id):
        """Check each grid pattern in sequence with highlight and result frames."""
        original = [list(line) for line in grid]
        fast = self.brain.db.get_fast_anim(user_id) == 1
        delay_hl = 0.15 if fast else 0.35
        delay_rv = 0.10 if fast else 0.25
        delay_ok = 0.35 if fast else 0.60
        matched = []
        original_display = "\n".join(" | ".join(line) for line in original)

        for pattern in self._expand_patterns():
            cells = pattern["cells"]
            highlighted = [list(line) for line in original]
            for row, column in cells:
                highlighted[row][column] = "🟨"
            await self._render_grid(
                message,
                "Продвинутое казино",
                bet,
                "\n".join(" | ".join(line) for line in highlighted),
                f"🔎 Проверка: <b>{html.escape(pattern['name'])}</b>",
                user_id=user_id,
            )
            await asyncio.sleep(delay_hl)

            multiplier = self._match_grid_pattern(original, pattern)
            await self._render_grid(
                message,
                "Продвинутое казино",
                bet,
                original_display,
                (
                    f"🔎 Проверка: <b>{html.escape(pattern['name'])}</b>"
                    if multiplier > 0
                    else f"❌ Не совпало: <b>{html.escape(pattern['name'])}</b>"
                ),
                user_id=user_id,
            )
            if multiplier > 0:
                matched.append((pattern, multiplier))
                await asyncio.sleep(delay_rv)
                marked = [list(line) for line in original]
                for row, column in cells:
                    marked[row][column] = "✅"
                await self._render_grid(
                    message,
                    "Продвинутое казино",
                    bet,
                    "\n".join(" | ".join(line) for line in marked),
                    (
                        f"✅ Совпало: <b>{html.escape(pattern['name'])}</b>"
                        f" — x{multiplier:g}"
                    ),
                    user_id=user_id,
                )
                await asyncio.sleep(delay_ok)
            else:
                await asyncio.sleep(delay_rv)

        await self._render_grid(
            message,
            "Продвинутое казино",
            bet,
            original_display,
            "🎰 <b>Итог...</b>",
            user_id=user_id,
        )
        await asyncio.sleep(0.3 if fast else 0.5)
        return matched

    def _evaluate_grid(self, grid, effects=None):
        """Оценивает три линии и общий бонус за число выигравших."""
        matching_patterns = []
        for pattern in self._expand_patterns():
            multiplier = self._match_grid_pattern(grid, pattern)
            if multiplier:
                matching_patterns.append((pattern, multiplier))

        if matching_patterns:
            pattern, multiplier = max(
                matching_patterns,
                key=lambda match: match[1],
            )
            return {
                "action": "win",
                "pattern": pattern["name"],
                "mult": multiplier,
                "total_mult": multiplier,
                "lines_won": 0,
                "descriptions": [],
                "reroll_grid": False,
                "line_bonus": 1,
                "line_results": [
                    {
                        "won": False,
                        "mult": 0.0,
                        "desc": "проигрыш",
                        "unstable": False,
                        "item": False,
                    }
                    for _ in grid
                ],
                "is_item": False,
            }

        line_results = [
            self._evaluate_line(line, effects)
            for line in grid
        ]
        lines_won = sum(result["won"] for result in line_results)
        multiplier_sum = sum(
            result["mult"] for result in line_results if result["won"]
        )
        line_bonus = 4 if lines_won == 3 else 2 if lines_won == 2 else 1
        reroll_grid = (
            all(result["unstable"] for result in line_results)
            and not any(result["won"] for result in line_results)
        )
        if reroll_grid:
            action = "reroll"
        elif lines_won:
            action = "win"
        else:
            action = "loss"
        return {
            "action": action,
            "total_mult": 0.0 if reroll_grid else multiplier_sum * line_bonus,
            "lines_won": lines_won,
            "descriptions": [result["desc"] for result in line_results],
            "reroll_grid": reroll_grid,
            "line_bonus": line_bonus,
            "line_results": line_results,
            "is_item": any(result["item"] for result in line_results),
        }

    # ---------- ОТРИСОВКА ----------

    async def _safe_edit(self, message, text, user_id=None, **kwargs):
        async with self._edit_lock:
            while True:
                interval = (
                    0.3
                    if user_id is not None
                    and self.brain.db.get_fast_anim(user_id) == 1
                    else 1.1
                )
                elapsed = time.time() - self._last_edit
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)
                try:
                    await message.edit_text(text, **kwargs)
                    self._last_edit = time.time()
                    return
                except TelegramRetryAfter as error:
                    await asyncio.sleep(error.retry_after + 1)
                except TelegramBadRequest:
                    return

    async def _render(
        self, message, name, bet, line_display, header, extra="", user_id=None,
    ):
        text = (
            f"🎰 <b>{name} крутка</b>\n"
            f"💰 Ставка: {bet} LC\n\n"
            f"{header}\n"
        )
        if extra:
            text += f"{extra}\n"
        text += f"\n<blockquote>{line_display}</blockquote>"
        await self._safe_edit(
            message, text, user_id=user_id, parse_mode="HTML"
        )

    async def _render_grid(
        self, message, name, bet, grid_display, header, user_id=None, extra="",
    ):
        title = name if name == "Продвинутое казино" else f"{name} крутка"
        text = (
            f"🎰 <b>{title}</b>\n"
            f"💰 Ставка: {bet} LC\n\n"
        )
        if extra:
            text += f"{extra}\n\n"
        text += f"{header}\n<blockquote>{grid_display}</blockquote>"
        await self._safe_edit(
            message, text, user_id=user_id, parse_mode="HTML"
        )

    async def _anim_reveal_grid(self, message, name, bet, grid, cfg, user_id):
        """Reveal the advanced grid one column at a time."""
        for column in range(5):
            rows = []
            for line in grid:
                cells = line[:column] + ["🌫️"] * (5 - column)
                cells[column] = random.choice(
                    [symbol for symbol in self.NOISE if symbol != line[column]]
                )
                rows.append(" | ".join(cells))
            await self._render_grid(
                message, name, bet, "\n".join(rows),
                f"{cfg['label']} <i>Крутим...</i> "
                f"<code>{column * 2 + 1}/11</code>",
                user_id,
            )
            rows = [
                " | ".join(line[:column + 1] + ["🌫️"] * (4 - column))
                for line in grid
            ]
            await self._render_grid(
                message, name, bet, "\n".join(rows),
                f"{cfg['label']} <i>Крутим...</i> "
                f"<code>{column * 2 + 2}/11</code>",
                user_id,
            )

        await self._render_grid(
            message, name, bet,
            "\n".join(" | ".join(line) for line in grid),
            f"{cfg['label']} <b>Стоп!</b>",
            user_id,
        )

    async def _anim_spin(self, message, name, bet, cfg, final_symbols, user_id):
        cell_count = len(final_symbols)
        frame_count = cell_count * 2 + 1
        for column in range(cell_count):
            fake = random.choice(
                [symbol for symbol in self.NOISE if symbol != final_symbols[column]]
            )
            for current_symbol, frame in (
                (fake, column * 2 + 1),
                (final_symbols[column], column * 2 + 2),
            ):
                display = (
                    final_symbols[:column]
                    + [current_symbol]
                    + ["🌫️"] * (cell_count - column - 1)
                )
                await self._render(
                    message, name, bet, " | ".join(display),
                    f"{cfg['label']} <i>Крутим...</i> "
                    f"<code>{frame}/{frame_count}</code>",
                    user_id=user_id,
                )

        await self._render(
            message, name, bet, " | ".join(final_symbols),
            f"{cfg['label']} <b>Стоп!</b>",
            user_id=user_id,
        )

    async def _anim_reveal(self, message, name, bet, symbols, cfg, header, user_id):
        await self._render(
            message, name, bet, " | ".join(symbols),
            f"{cfg['label']} {header}",
            user_id=user_id,
        )

    def _apply_chain_explosion(self, symbols):
        line = list(symbols)
        explosions = 0
        chain_order = []
        frontier = [i for i, symbol in enumerate(line) if symbol == "🔥"]
        step = 0

        while frontier:
            newly_burning = set()
            for i in frontier:
                for neighbor in (i - 1, i + 1):
                    if (
                        0 <= neighbor < len(line)
                        and line[neighbor] not in ("🔥", "💣")
                    ):
                        newly_burning.add(neighbor)
            if not newly_burning:
                break

            # Fire spreads through ordinary cells; bombs stay intact for _evaluate.
            step += 1
            chain_order.append((step, sorted(newly_burning)))
            explosions += len(newly_burning)
            for i in newly_burning:
                line[i] = "🔥"
            frontier = list(newly_burning)

        return line, explosions, chain_order

    async def _anim_explosion(
        self, message, name, bet, new_symbols, chain_order, user_id,
    ):
        if not chain_order:
            return

        await self._render(
            message, name, bet, " | ".join(new_symbols),
            f"💥 <b>Цепная реакция: {len(chain_order)}!</b> "
            "<i>Всё полыхает...</i>",
            user_id=user_id,
        )

    async def _anim_heat_ignite(
        self, message, name, bet, symbols_before, burned_indices, stage,
        user_id,
    ):
        """Show each overheat ignition in its own frame."""
        if not burned_indices:
            return

        line = list(symbols_before)
        await self._render(
            message, name, bet, " | ".join(line),
            "🔥 <b>Что-то возгорается…</b>",
            user_id=user_id,
        )
        for index in sorted(burned_indices):
            line[index] = "🔥"
            await self._render(
                message, name, bet, " | ".join(line),
                f"🔥 <b>Стадия {stage}/5</b>",
                user_id=user_id,
            )

    async def _anim_unstable_reroll(
        self, message, name, bet, symbols, sym, run, reroll_count,
        accumulated_mult, user_id,
    ):
        """Hide symbols from left to right before the next full spin."""
        label = sym if sym is not None else "Паттерн"
        extra = (
            f"{label} × {run}  •  реролл #{reroll_count}"
            f"  •  копилка x{accumulated_mult:g}"
        )
        for hidden_count in range(1, 6):
            hidden_count = min(hidden_count, len(symbols))
            display = ["🌫️"] * hidden_count + symbols[hidden_count:]
            await self._render(
                message, name, bet, " | ".join(display),
                f"🔄 <b>Перекрут #{reroll_count}</b> "
                f"<code>{hidden_count}/5</code>",
                extra,
                user_id=user_id,
            )

    def _highlight_cells(self, symbols, sym, run, wrap_open="「", wrap_close="」"):
        if sym is None or run == 0:
            return list(symbols)
        return [
            f"{wrap_open}{symbol}{wrap_close}" if symbol == sym else symbol
            for symbol in symbols
        ]

    async def _celebrate_win_by_size(self, message, name, bet, symbols,
                                     mult, sym, run, user_id):
        """Choose celebration intensity by multiplier size."""
        line = " | ".join(symbols)
        frames = []

        if mult >= 100:
            highlighted = self._highlight_cells(symbols, sym, run)
            sparkling = [
                ("✨" if index % 2 == 0 else "💫")
                if sym is not None and run != 0 and symbol == sym
                else symbol
                for index, symbol in enumerate(symbols)
            ]
            frames = [
                (
                    " | ".join(highlighted),
                    "🎰🤑🎰 <b>БАРАБАНЫ РАСКАЛЕНЫ!</b>\n"
                    f"✨ <b>{sym} × {run}!!!</b> ✨",
                ),
                (" | ".join(sparkling), "🎆 <b>ДЖЕКПОТ!</b> 🎆"),
                (line, f"🏆 <b>x{mult:g} ОТ СТАВКИ!</b>"),
            ]
        elif mult >= 20:
            money_line = [
                "💰" if sym is not None and run != 0 and symbol == sym else symbol
                for symbol in symbols
            ]
            frames = [
                (line, "🎉 <b>Крупный выигрыш!</b>"),
                (
                    " | ".join(money_line),
                    f"💸 <b>{sym} × {run}</b> — x{mult:g}\n"
                    "✅ <b>+ деньги в карман!</b>",
                ),
            ]
        elif mult >= 5:
            frames = [(line, f"✨ <b>{sym} × {run}</b>")]
        else:
            frames = [(line, f"🙂 <b>{sym} × {run}</b> — +мелочь")]

        for frame_line, header in frames[:3]:
            await self._render(
                message, name, bet, frame_line, header, user_id=user_id
            )

    async def _cinematic_bomb_explosion(
        self, message, name, bet, symbols_before, symbols_after,
        damage_amount, run_count, user_id,
    ):
        """Show a two-frame bomb blast, or a third frame when fire spreads."""
        blast_indices = [
            index for index, symbol in enumerate(symbols_after)
            if symbol == "💥"
        ]
        blast_line = list(symbols_before)
        for index in blast_indices:
            blast_line[index] = "💥"

        has_fire = "🔥" in symbols_after
        frames = [
            (
                symbols_before,
                "💥 <b>Взрыв!</b>",
                f"💣×{run_count}  •  ×{abs(damage_amount):g} к выплате",
            ),
            (
                blast_line,
                "💥 <b>Взрыв!</b>",
                "<i>Бомбы детонировали.</i>",
            ),
        ]
        if has_fire:
            frames.append((
                symbols_after,
                "🔥 <b>Огонь от бомб!</b>",
                "<i>Горящие клетки после взрыва.</i>",
            ))
        for symbols, header, extra in frames:
            await self._render(
                message, name, bet, " | ".join(symbols), header, extra,
                user_id=user_id,
            )

    # ---------- ГЛАВНЫЙ ЦИКЛ ----------

    async def _resolve_advanced(self, message, bet, user_id, cfg, effects, stage):
        name = "Продвинутое казино"
        reroll_count = 0
        accumulated_mult = 0.0
        while True:
            grid = self._spin_grid(reroll_count, effects, stage, user_id)
            grid = [
                self._apply_cyclone(line, user_id)
                for line in grid
            ]
            await self._anim_reveal_grid(
                message, name, bet, grid, cfg, user_id
            )
            pre_verdict = self._evaluate_grid(grid, effects)
            if not pre_verdict["reroll_grid"]:
                await self._anim_pattern_check(
                    message, bet, grid, user_id
                )
            verdict = pre_verdict

            if verdict["reroll_grid"]:
                if reroll_count < self.MAX_REROLLS:
                    accumulated_mult += verdict["total_mult"]
                    reroll_count += 1
                    continue

                # A grid still rerolling at the cap is a loss, never a payout.
                verdict["action"] = "loss"
                verdict["total_mult"] = 0.0
                verdict["is_item"] = False
                verdict["reroll_grid"] = False
            else:
                verdict["total_mult"] += accumulated_mult
            break

        return (
            verdict["total_mult"],
            verdict["is_item"],
            grid,
            reroll_count,
            effects,
            "🔥" in grid[1],
            0,
            verdict,
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
        if spin_key == "hardcore":
            stage = 5
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
            symbols = self._spin(
                reroll_count, effects, spin_key, user_id
            )
            await self._anim_spin(
                message, name, bet, cfg, symbols, user_id
            )

            symbols_before = list(symbols)
            # Применяем перегрев
            symbols, _, burned_indices = self._apply_overheat(
                symbols, stage, effects
            )
            if burned_indices:
                any_burn = True
                await self._anim_heat_ignite(
                    message, name, bet, symbols_before, burned_indices,
                    stage, user_id,
                )

            symbols, explosions, chain_order = self._apply_chain_explosion(
                symbols
            )
            total_explosions += explosions
            verdict = self._evaluate(
                symbols, effects, spin_key, user_id
            )
            symbols = verdict.get("symbols", symbols)
            final_symbols = symbols
            if chain_order and not (
                verdict["action"] == "win" and verdict["mult"] < 0
            ):
                await self._anim_explosion(
                    message, name, bet, symbols, chain_order, user_id
                )
            final_symbols = symbols
            if verdict["action"] == "reroll":
                total_mult += verdict["mult"]
                is_item_any = is_item_any or verdict["item"]
                reroll_sym = verdict.get("sym")
                if verdict.get("reason") == "pattern":
                    reroll_sym = verdict.get("pattern_name", "Паттерн")
                await self._anim_unstable_reroll(
                    message, name, bet, symbols,
                    reroll_sym, verdict["run"], reroll_count + 1, total_mult,
                    user_id,
                )
                reroll_count += 1
                if reroll_count > self.MAX_REROLLS:
                    break
                continue
            elif explosions:
                header = f"💥 <b>Цепная реакция: {explosions}!</b>"
            elif verdict["action"] == "win" and verdict["mult"] < 0:
                header = "💣 <b>ВЗРЫВ!</b>"
            elif verdict["action"] == "win":
                header = "🎉 <b>ВЫИГРЫШ!</b>"
            elif burned_indices:
                header = "🔥 <b>Перегрев!</b>"
            else:
                header = "😔 <i>Ничего не выпало...</i>"
            if verdict["action"] == "win" and verdict["mult"] < 0:
                run_count = verdict["run"]
                symbols_after = list(symbols)
                for start in range(len(symbols) - run_count + 1):
                    if all(
                        symbol == "💣"
                        for symbol in symbols[start:start + run_count]
                    ):
                        for index in range(start, start + run_count):
                            symbols_after[index] = "💥"
                        break
                await self._cinematic_bomb_explosion(
                    message, name, bet, symbols, symbols_after,
                    verdict["mult"], run_count, user_id,
                )
            elif verdict["action"] == "win":
                win_sym = verdict.get("sym")
                win_run = verdict["run"]
                if verdict.get("reason") == "pattern":
                    win_sym = verdict.get("pattern_name", "Паттерн")
                    win_run = 0
                if verdict["mult"] > 0:
                    await self._celebrate_win_by_size(
                        message, name, bet, symbols,
                        verdict["mult"], win_sym, win_run, user_id,
                    )
            else:
                await self._anim_reveal(
                    message, name, bet, symbols, cfg, header, user_id
                )

            if verdict["action"] == "win":
                total_mult += verdict["mult"]
                is_item_any = is_item_any or verdict["item"]
                if verdict.get("reason") == "pattern":
                    final_description = f"Паттерн «{verdict.get('pattern_name', '?')}»"
                else:
                    final_description = f"{verdict['sym']} × {verdict['run']}"
                break
            total_mult = 0
            is_item_any = False
            break
        return (
            total_mult, is_item_any, final_symbols, reroll_count, effects,
            any_burn, total_explosions, None,
        )

    # ---------- ЗАПУСК ----------

    async def _start_game(self, message: Message, spin_key: str, bet: int):
        user_id = message.from_user.id
        if spin_key != "hardcore":
            return await self._start_game_inner(message, spin_key, bet)

        saved_overheat = self.brain.db.get_overheat_score(user_id)
        self.brain.db.set_overheat_score(user_id, 50)
        try:
            await self._start_game_inner(message, spin_key, bet)
        finally:
            self.brain.db.set_overheat_score(user_id, saved_overheat)

    async def _start_game_inner(
        self, message: Message, spin_key: str, bet: int,
    ):
        in_hardcore = spin_key == "hardcore"
        user_id = message.from_user.id
        if not self.brain.db.subtract_balance_if_available(user_id, "lc", bet):
            balance = self.brain.db.get_balance(user_id, "lc")
            await message.answer(
                f"Недостаточно LC. У тебя {balance}."
            )
            return
        user = self.brain.db.get_user(user_id)
        username = user["username"] or ""

        name, _, _, spin_mult = self.SPIN_TYPES[spin_key]
        game_title = (
            "Продвинутое казино" if spin_key == "advanced"
            else f"{name} крутка"
        )
        msg = await message.answer(f"🎰 <b>{game_title}</b>\n\nКрутим...",
                                   parse_mode="HTML")

        self.brain.db.increment_badge_rolls(user_id)

        (
            total_mult, is_item, symbols, rerolls, effects, any_burn,
            explosions, advanced_result,
        ) = await self._resolve(msg, name, bet, spin_key, user_id)

        mult_bonus = effects.get("mult_bonus", 0)
        effective_mult = total_mult * (1 + mult_bonus) if total_mult > 0 else total_mult

        # Штраф за 🔥
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

        equipped_badges = self.brain.db.get_user_badges(user_id)
        jack_active = "halloween_jack" in equipped_badges.values()
        jack_xp_multiplier = 1
        jack_cash_multiplier = 1
        if jack_active:
            jack_cash_multiplier, jack_xp_multiplier = (
                self._jack_multipliers(bet)
            )
            win_amount = int(win_amount * jack_cash_multiplier)

        self.brain.db.log_event(
            user_id, username, "spin",
            f"{spin_key}|{bet}|{win_amount}"
        )

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

        total_lost_this_spin = bet + applied_loss if win_amount < 0 else 0
        stats_win_amount = -total_lost_this_spin if win_amount < 0 else win_amount
        self.brain.db.add_bet_stats(user_id, bet, stats_win_amount)

        # Базовый прирост + ускорение от экипированных значков.
        overheat_gain = (
            1 if spin_key == "advanced"
            else 1 + int(effects.get("overheat_speed", 0))
        )
        if not in_hardcore:
            self.brain.db.add_overheat(
                user_id,
                overheat_gain,
                reduction=effects.get("overheat_reduction", 0),
            )

        bet_factor = min(1 + bet / 500, 10)
        xp_gain = int(
            spin_mult * 20 * (2 if win_amount > 0 else 1) * bet_factor
        )
        xp_bonus = effects.get("xp_bonus", 0)
        xp_gain = int(xp_gain * (1 + xp_bonus))
        xp_gain *= jack_xp_multiplier
        level, xp, leveled_up = self.brain.db.add_xp(user_id, xp_gain)
        if leveled_up:
            self.brain.db.log_event(
                user_id, username, "level_up", str(level)
            )
        xp_needed = 100 * (level + 1)

        # --- Поломка значков ---
        break_messages = []
        try:
            from content.effects import should_break, handle_break
            from content.catalog import BADGES
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
            if advanced_result.get("pattern"):
                result += (
                    f"✨ Паттерн сетки: <b>{advanced_result['pattern']}</b> "
                    f"(×{advanced_result['mult']:g})\n"
                )
            else:
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

        if jack_active:
            result += "\n🎃 <b>Джек активен!</b>\n"

        if win_amount > 0:
            final_mult = (
                effective_mult * spin_mult * fire_factor * jack_cash_multiplier
            )
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
        if in_hardcore:
            new_stage, new_score = 5, 50
        else:
            new_stage, new_score = self.brain.db.get_overheat_stage(user_id)
        oh_icon, _, _ = self.OVERHEAT_STAGES[new_stage]
        result += f"\n🔥 Перегрев: {oh_icon} <code>({new_score}/50)</code>"

        if break_messages:
            result += "\n\n" + "\n".join(break_messages)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Ещё", callback_data=f"again_{spin_key}")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="play")],
        ] + nav_footer("play"))
        await self._safe_edit(
            msg, result, user_id=user_id,
            reply_markup=kb, parse_mode="HTML",
        )

    # ---------- МЕНЮ ----------

    async def cb_regular_list(self, query: CallbackQuery):
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        buttons = []
        for spin_key in self.REGULAR_SPINS:
            name, min_bet, max_bet, _ = self.SPIN_TYPES[spin_key]
            required_level = self.LEVEL_REQ[spin_key]
            if level >= required_level:
                text = f"{name} ({min_bet}-{max_bet} LC)"
                callback_data = f"choose_{spin_key}"
            else:
                text = f"🔒 {name} (с {required_level} ур.)"
                callback_data = "locked"
            buttons.append([InlineKeyboardButton(
                text=text, callback_data=callback_data
            )])
        buttons.append([InlineKeyboardButton(
            text="⬅️ Назад", callback_data="play"
        )])
        buttons.extend(nav_footer("play"))
        await self._safe_edit(
            query.message,
            "🎰 <b>Обычные крутки</b>\n\nВыбери тип:",
            user_id=user_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML",
        )
        await safe_answer(query)

    async def cb_effects_list(self, query: CallbackQuery):
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        buttons = []
        for spin_key in self.EFFECT_SPINS:
            name, min_bet, max_bet, _ = self.SPIN_TYPES[spin_key]
            required_level = self.LEVEL_REQ[spin_key]
            if level >= required_level:
                text = f"{name} ({min_bet}-{max_bet} LC)"
                callback_data = f"choose_{spin_key}"
            else:
                text = f"🔒 {name} (с {required_level} ур.)"
                callback_data = "locked"
            buttons.append([InlineKeyboardButton(
                text=text, callback_data=callback_data
            )])
        buttons.append([InlineKeyboardButton(
            text="⬅️ Назад", callback_data="play"
        )])
        buttons.extend(nav_footer("play"))
        await self._safe_edit(
            query.message,
            "✨ <b>Крутки с эффектами</b>\n\nВыбери тип:",
            user_id=user_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML",
        )
        await safe_answer(query)

    async def cb_play(self, query: CallbackQuery, state: FSMContext = None):
        if is_current_screen(query, "play"):
            return await safe_answer(query, "Уже здесь")
        try:
            if state:
                await state.clear()
            user_id = query.from_user.id
            tickets = self.brain.db.get_tickets(user_id)

            user = self.brain.db.get_user(user_id)
            # Перегрев
            oh_stage, oh_score = self.brain.db.get_overheat_stage(user_id)
            oh_icon, _, _ = self.OVERHEAT_STAGES[oh_stage]

            # Эффекты
            effects = self._effects(user_id)
            eff_line = ""
            if effects:
                try:
                    from content.catalog import describe_effect_dict
                    eff_line = f"\n✨ <i>{describe_effect_dict(effects)}</i>"
                except Exception:
                    pass

            body = (f"🎰 <b>Игровой зал LuckyScoin</b>\n\n"
                    f"🔥 Перегрев: {oh_icon} <code>({oh_score}/50)</code>"
                    f"{eff_line}\n\n"
                    f"Выбери тип крутки:")
            if tickets >= self.MAX_TICKETS:
                body += "\n\n🎟 Максимум билетиков на руках."
            text = with_hero(body, user)

            buttons = [
                [InlineKeyboardButton(
                    text="🎰 Обычные",
                    callback_data="regular_list",
                )],
                [InlineKeyboardButton(
                    text="✨ С эффектами",
                    callback_data="effects_list",
                )],
            ]
            buttons.append([InlineKeyboardButton(
                text=f"🎟 Рулетка ({tickets} билетов)",
                callback_data="roulette",
            )])
            buttons.extend(nav_footer("play"))

            await self._safe_edit(
                query.message, text, user_id=user_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML",
            )
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка игрового меню: {error}")
            await safe_answer(query, "Не удалось открыть игровое меню.", show_alert=True)

    async def cb_locked(self, query: CallbackQuery):
        try:
            await safe_answer(query, "🔒 Недостаточный уровень!", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка заблокированной крутки: {error}")

    async def _ask_bet(self, query, spin_key, state):
        if spin_key not in self.SPIN_TYPES:
            return await safe_answer(query, "Неизвестный тип!", show_alert=True)
        user_id = query.from_user.id
        level, _ = self.brain.db.get_level_xp(user_id)
        if level < self.LEVEL_REQ.get(spin_key, 0):
            return await safe_answer(
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
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_bet")],
        ]
        keyboard_rows.extend(nav_footer("play"))
        await self._safe_edit(
            query.message, text, user_id=query.from_user.id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
            parse_mode="HTML")
        await safe_answer(query)

    async def cb_choose_type(self, query: CallbackQuery, state: FSMContext):
        try:
            await self._ask_bet(query, query.data.split("_", 1)[1], state)
        except Exception as error:
            print(f"⚠️ Ошибка выбора типа крутки: {error}")
            await safe_answer(query, "Не удалось выбрать крутку.", show_alert=True)

    async def cb_spin_again(self, query: CallbackQuery, state: FSMContext):
        try:
            await self._ask_bet(query, query.data.split("_", 1)[1], state)
        except Exception as error:
            print(f"⚠️ Ошибка повторного выбора крутки: {error}")
            await safe_answer(query, "Не удалось повторить крутку.", show_alert=True)

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
        ] + nav_footer("play"))

    async def cb_roulette(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            tickets = self.brain.db.get_tickets(query.from_user.id)
            from content.catalog import BADGES

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
                query.message, text, user_id=query.from_user.id,
                reply_markup=self._roulette_keyboard(),
                parse_mode="HTML",
            )
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка открытия рулетки: {error}")
            await safe_answer(query, "Не удалось открыть рулетку.", show_alert=True)

    async def roulette_buy(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            user_id = query.from_user.id
            tickets = self.brain.db.get_tickets(user_id)
            if tickets >= self.MAX_TICKETS:
                await safe_answer(query, "🎟 Максимум билетиков.", show_alert=True)
                return
            balance = self.brain.db.get_balance(user_id, "sc")
            if balance < self.ROULETTE_TICKET_PRICE_SC:
                await safe_answer(
                    query, "Недостаточно SC. Нужно 5 SC.", show_alert=True
                )
                return

            if not self.brain.db.subtract_balance_if_available(
                user_id, "sc", self.ROULETTE_TICKET_PRICE_SC
            ):
                await safe_answer(
                    query, "Недостаточно SC. Нужно 5 SC.", show_alert=True
                )
                return
            self.brain.db.add_tickets(user_id, 1)
            tickets = self.brain.db.get_tickets(user_id)
            text = (
                "🎟 <b>Билетная рулетка</b>\n\n"
                f"✅ Куплен 1 билет за {self.ROULETTE_TICKET_PRICE_SC} SC.\n"
                f"🎫 Билетиков: <b>{tickets}/{self.MAX_TICKETS}</b>\n"
                "🎰 Выбери действие:"
            )
            await self._safe_edit(
                query.message, text, user_id=user_id,
                reply_markup=self._roulette_keyboard(),
                parse_mode="HTML",
            )
            await safe_answer(query, "✅ Билет куплен!")
        except Exception as error:
            print(f"⚠️ Ошибка покупки билетика: {error}")
            await safe_answer(query, "Не удалось купить билет.", show_alert=True)

    async def roulette_spin(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            user_id = query.from_user.id
            if not self.brain.db.spend_ticket(user_id):
                await safe_answer(query, "Нет билетиков для крутки.", show_alert=True)
                return
            prize = self._pick_roulette_result()
            self.brain.db.log_event(
                user_id, "", "roulette",
                f"{prize['name']}|{prize['amount']}"
            )
            medal_won = (
                "medal" in prize
                and random.random() < prize["medal_chance"]
            )
            symbols = [entry["symbol"] for entry in self.ROULETTE_PRIZES]
            win_position = random.randint(0, 4)
            slots = [random.choice(symbols) for _ in range(5)]
            slots[win_position] = prize["symbol"]
            await safe_answer(query)
            await self._anim_roulette(
                query.message, user_id, prize, slots, medal_won, win_position
            )
        except Exception as error:
            print(f"⚠️ Ошибка крутки рулетки: {error}")
            await safe_answer(query, "Не удалось выполнить крутку.", show_alert=True)

    async def _anim_roulette(
        self, message, user_id, prize, slots, medal_won, win_position
    ):
        """Показывает пять кадров рулетки с остановкой на призе."""
        total_frames = 5
        for frame in range(total_frames):
            if frame < total_frames - 1:
                position = random.choice([
                    index for index in range(len(slots))
                    if index != win_position
                ])
            else:
                position = win_position
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

            if frame == total_frames - 1:
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
                    from content.catalog import BADGES

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
                message, text, user_id=user_id,
                reply_markup=self._roulette_keyboard(),
                parse_mode="HTML",
            )
