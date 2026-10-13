"""
ЗНАЧКИ (артефакты) и ТИТУЛЫ.

ЗНАЧКИ — дают эффекты, надеваются в ячейки, могут сломаться.
ТИТУЛЫ — просто надпись.

Структура значка:
    name         — название с эмодзи
    desc         — короткое описание
    rarity       — common / rare / epic / legendary
    unlock       — условие открытия (см. is_unlocked)
    hp           — сколько спинов живёт ("inf" = вечный)
    break_on     — когда может сломаться: ["roll"], ["win"], ["loss"]
    break_chance — шанс поломки при триггере (0.05 = 5%)
    effect       — строка: "set.mult_bonus = 0.05" или "give.user_sc = 1000"
    hard_effect  — список условий (см. ниже)
    after_break  — {"type": "NOTHING"} / {"type": "GET_SC", "amount": 100} / ...

Формат EFFECT:
    "set.переменная = значение"    — установить
    "give.переменная = значение"   — прибавить

HARD_EFFECT:
    [
        {"if": "user_level >= 50",   "then": "set.mult_bonus = 0.20"},
        {"elif": "user_level >= 25", "then": "set.mult_bonus = 0.15"},
        {"else": "set.mult_bonus = 0.10"},
    ]
    Операторы: >=, <=, !=, =, >, <, !
    | = ИЛИ, # = И

Переменные (см. db.get_extended_stats):
    user_level, user_sc, user_lc, user_games, user_wins, user_losses, user_xp,
    user_streak, user_max_streak, user_winrate, user_total_bets, user_total_won,
    user_total_lost, casino_level, casino_rooms, casino_staff, casino_income,
    badges_count, badges_legendary, hour_of_day, day_of_week
"""


# ============================================================
#  ЗНАЧКИ (артефакты с баффами + HP)
# ============================================================

BADGES = {
    "rookie": {
        "name": "🎲 Новичок",
        "desc": "Просто для красоты",
        "rarity": "common",
        "unlock": {},
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },
    "lucky": {
        "name": "🍀 Везунчик",
        "desc": "+5% к множителю",
        "rarity": "common",
        "unlock": {"level": 5},
        "hp": 100,
        "break_on": ["loss"],
        "break_chance": 0.02,
        "effect": "set.mult_bonus = 0.05",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },
    "hard_worker": {
        "name": "⛏️ Старатель",
        "desc": "+15% XP",
        "rarity": "common",
        "unlock": {"level": 10},
        "hp": 150,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.xp_bonus = 0.15",
        "hard_effect": [],
        "after_break": {"type": "GET_SC", "amount": 100},
    },
    "bomb_defuser": {
        "name": "🛡 Сапёр",
        "desc": "-40% урона от бомб 💣",
        "rarity": "rare",
        "unlock": {"level": 15},
        "hp": 120,
        "break_on": ["loss"],
        "break_chance": 0.03,
        "effect": "set.bomb_shield = 0.40",
        "hard_effect": [],
        "after_break": {"type": "GET_SC", "amount": 500},
    },
    "lucky_pro": {
        "name": "🍀 Про-везение",
        "desc": "+12% к множителю",
        "rarity": "rare",
        "unlock": {"level": 25},
        "hp": 150,
        "break_on": ["loss"],
        "break_chance": 0.03,
        "effect": "set.mult_bonus = 0.12",
        "hard_effect": [],
        "after_break": {"type": "GET_LC", "amount": 100},
    },
    "streak_master": {
        "name": "🔥 На волне",
        "desc": "Растёт при серии побед",
        "rarity": "epic",
        "unlock": {"level": 30},
        "hp": 200,
        "break_on": ["loss"],
        "break_chance": 0.04,
        "effect": "set.mult_bonus = 0.05",
        "hard_effect": [
            {"if": "user_streak >= 10", "then": "set.mult_bonus = 0.30"},
            {"elif": "user_streak >= 5", "then": "set.mult_bonus = 0.20"},
            {"elif": "user_streak >= 3", "then": "set.mult_bonus = 0.10"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "lucky_pro"},
    },
    "night_owl": {
        "name": "🦉 Ночная сова",
        "desc": "Ночью удача выше",
        "rarity": "epic",
        "unlock": {"level": 40},
        "hp": 180,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.luck = 0.05",
        "hard_effect": [
            {"if": "hour_of_day >= 0 # hour_of_day <= 6", "then": "set.luck = 0.25"},
        ],
        "after_break": {"type": "GET_LC", "amount": 200},
    },
    "tycoon": {
        "name": "🏢 Магнат",
        "desc": "Бонус за развитое казино",
        "rarity": "epic",
        "unlock": {"room_level": 5},
        "hp": 250,
        "break_on": ["loss"],
        "break_chance": 0.02,
        "effect": "set.mult_bonus = 0.08",
        "hard_effect": [
            {"if": "casino_level >= 8", "then": "set.mult_bonus = 0.20"},
            {"if": "casino_rooms >= 7", "then": "set.xp_bonus = 0.10"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "golden_ring"},
    },
    "golden_ring": {
        "name": "💛 Золотое кольцо",
        "desc": "+15% к множителю",
        "rarity": "epic",
        "unlock": {"level": 55},
        "hp": 300,
        "break_on": ["loss"],
        "break_chance": 0.02,
        "effect": "set.mult_bonus = 0.15",
        "hard_effect": [
            {"if": "user_level >= 80 # casino_level >= 7", "then": "set.mult_bonus = 0.25"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "lucky_pro"},
    },
    "legend": {
        "name": "👑 Легенда",
        "desc": "+20% к множителю",
        "rarity": "legendary",
        "unlock": {"level": 70},
        "hp": 500,
        "break_on": ["loss"],
        "break_chance": 0.01,
        "effect": "set.mult_bonus = 0.20",
        "hard_effect": [],
        "after_break": {"type": "GET_ITEM", "item_id": "golden_ring"},
    },
    "phoenix": {
        "name": "🔥 Перо феникса",
        "desc": "Вечный: +25% к множителю",
        "rarity": "legendary",
        "unlock": {"level": 100},
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.mult_bonus = 0.25",
        "hard_effect": [
            {"if": "user_level >= 150", "then": "set.mult_bonus = 0.40"},
            {"if": "user_sc >= 100000", "then": "set.xp_bonus = 0.30"},
        ],
        "after_break": {"type": "NOTHING"},
    },
    "whale": {
        "name": "🐋 Кит",
        "desc": "+25% к множителю и защита от бомб",
        "rarity": "legendary",
        "unlock": {"sc": 50000},
        "hp": 400,
        "break_on": ["loss"],
        "break_chance": 0.01,
        "effect": "set.mult_bonus = 0.25",
        "hard_effect": [
            {"if": "badges_legendary >= 2", "then": "set.mult_bonus = 0.40"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "legend"},
    },
    # -------- ПРИМЕР для добавления --------
    # "collector": {
    #     "name": "🎖 Коллекционер",
    #     "desc": "+15% XP и +5% к множителю",
    #     "rarity": "epic",
    #     "unlock": {"level": 75},
    #     "hp": 300,
    #     "break_on": ["roll"],
    #     "break_chance": 0.02,
    #     "effect": "set.mult_bonus = 0.05",
    #     "hard_effect": [
    #         {"if": "user_level >= 100", "then": "set.xp_bonus = 0.15"},
    #     ],
    #     "after_break": {"type": "GET_SC", "amount": 2000},
    # },
}


# ============================================================
#  ТИТУЛЫ (просто надпись)
# ============================================================

TITLES = {
    "newbie": {
        "name": "🎲 Новичок",
        "desc": "Стартовый титул",
        "rarity": "common",
        "unlock": {},
    },
    "lucky": {
        "name": "🍀 Везунчик",
        "desc": "С 5 уровня",
        "rarity": "common",
        "unlock": {"level": 5},
    },
    "rich": {
        "name": "💎 Богач",
        "desc": "С 25 уровня",
        "rarity": "rare",
        "unlock": {"level": 25},
    },
    "high_roller": {
        "name": "🔥 Хайроллер",
        "desc": "С 50 уровня",
        "rarity": "epic",
        "unlock": {"level": 50},
    },
    "legend": {
        "name": "👑 Легенда",
        "desc": "С 100 уровня",
        "rarity": "legendary",
        "unlock": {"level": 100},
    },
    "tycoon": {
        "name": "🏢 Магнат",
        "desc": "Открой 5 залов в своём казино",
        "rarity": "epic",
        "unlock": {"room_level": 5},
    },
    "whale": {
        "name": "🐋 Кит",
        "desc": "Накопи 100 000 SC",
        "rarity": "legendary",
        "unlock": {"sc": 100000},
    },
}


# ============================================================
#  ОБЩЕЕ
# ============================================================

RARITY_EMOJI = {
    "common":    "⚪",
    "rare":      "🔵",
    "epic":      "🟣",
    "legendary": "🟡",
}


def badge_slots_for_level(level: int) -> int:
    if level < 5:
        return 0
    if level < 25:
        return 3
    if level < 100:
        return 4
    return 5


def is_unlocked(item: dict, u: dict, room_level: int = 0) -> bool:
    unlock = item.get("unlock", {})
    if "level" in unlock and u.get("level", 0) < unlock["level"]:
        return False
    if "sc" in unlock and u.get("sc", 0) < unlock["sc"]:
        return False
    if "lc" in unlock and u.get("lc", 0) < unlock["lc"]:
        return False
    if "games" in unlock and u.get("games", 0) < unlock["games"]:
        return False
    if "wins" in unlock and u.get("wins", 0) < unlock["wins"]:
        return False
    if "room_level" in unlock and room_level < unlock["room_level"]:
        return False
    return True


def describe_effect_dict(effect_dict: dict) -> str:
    """Красивое описание эффектов-словаря (результат парсинга)."""
    if not effect_dict:
        return "— без бонусов —"
    parts = []
    if "mult_bonus" in effect_dict:
        parts.append(f"+{int(effect_dict['mult_bonus']*100)}% множитель")
    if "xp_bonus" in effect_dict:
        parts.append(f"+{int(effect_dict['xp_bonus']*100)}% XP")
    if "bomb_shield" in effect_dict:
        parts.append(f"-{int(effect_dict['bomb_shield']*100)}% урон 💣")
    if "luck" in effect_dict:
        parts.append(f"+{int(effect_dict['luck']*100)}% удача")
    if "reroll_bonus" in effect_dict:
        parts.append(f"+{int(effect_dict['reroll_bonus']*100)}% реролл")
    return " • ".join(parts) if parts else "— без бонусов —"