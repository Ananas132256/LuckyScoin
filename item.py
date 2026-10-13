"""
ПРЕДМЕТЫ — экипируются, работают вечно, могут сломаться.

EFFECT: одна строка вида
    "set.mult_bonus = 0.10"
    "give.user_sc = 1000"

HARD_EFFECT: список условий
    [
        {"if": "user_level >= 50",   "then": "set.mult_bonus = 0.20"},
        {"elif": "user_level >= 25", "then": "set.mult_bonus = 0.15"},
        {"else": "set.mult_bonus = 0.10"},
    ]

Операторы в if: >=, <=, !=, =, >, <, !
    | — ИЛИ
    # — И

Переменные (см. db.get_extended_stats):
    user_level, user_sc, user_lc, user_games, user_wins, user_losses, user_xp,
    user_streak, user_max_streak, user_winrate, user_total_bets, user_total_won,
    user_total_lost, casino_level, casino_rooms, casino_staff, casino_income,
    badges_count, badges_legendary, hour_of_day, day_of_week
"""


ITEMS = {
    # ============ ⚪ ОБЫЧНЫЕ ============
    "iron_ring": {
        "name": "💍 Железное кольцо",
        "desc": "+1% к множителю",
        "rarity": "common",
        "buy": 500,
        "hp": 100,
        "break_on": ["loss"],
        "break_chance": 0.02,
        "effect": "set.mult_bonus = 0.01",
        "hard_effect": [],
        "after_break": {"type": "GET_SC", "amount": 50},
    },
    "wooden_amulet": {
        "name": "🌿 Деревянный амулет",
        "desc": "+5% XP",
        "rarity": "common",
        "buy": 800,
        "hp": 80,
        "break_on": ["roll"],
        "break_chance": 0.03,
        "effect": "set.xp_bonus = 0.05",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },

    # ============ 🔵 РЕДКИЕ ============
    "silver_pendant": {
        "name": "📿 Серебряный медальон",
        "desc": "+7% к множителю (x2 на серии 5+)",
        "rarity": "rare",
        "buy": 5000,
        "hp": 150,
        "break_on": ["loss"],
        "break_chance": 0.03,
        "effect": "set.mult_bonus = 0.07",
        "hard_effect": [
            {"if": "user_streak >= 5", "then": "set.mult_bonus = 0.14"},
        ],
        "after_break": {"type": "GET_SC", "amount": 500},
    },
    "lucky_horseshoe": {
        "name": "🍀 Подкова удачи",
        "desc": "+10% удачи (ночью x2)",
        "rarity": "rare",
        "buy": 6000,
        "hp": 120,
        "break_on": ["roll"],
        "break_chance": 0.04,
        "effect": "set.luck = 0.10",
        "hard_effect": [
            {"if": "hour_of_day >= 0 # hour_of_day <= 6", "then": "set.luck = 0.20"},
        ],
        "after_break": {"type": "GET_LC", "amount": 100},
    },
    "smart_scroll": {
        "name": "📜 Свиток мудрости",
        "desc": "Растёт вместе с уровнем",
        "rarity": "rare",
        "buy": 10000,
        "hp": 50,
        "break_on": ["win"],
        "break_chance": 0.10,
        "effect": "set.mult_bonus = 0.05",
        "hard_effect": [
            {"if": "user_level >= 100", "then": "set.mult_bonus = 0.30"},
            {"elif": "user_level >= 50", "then": "set.mult_bonus = 0.15"},
            {"elif": "user_level >= 25", "then": "set.mult_bonus = 0.10"},
        ],
        "after_break": {"type": "GET_SC", "amount": 1000},
    },

    # ============ 🟣 ЭПИЧЕСКИЕ ============
    "golden_ring": {
        "name": "💛 Золотое кольцо",
        "desc": "+15% к множителю",
        "rarity": "epic",
        "buy": 25000,
        "hp": 200,
        "break_on": ["loss"],
        "break_chance": 0.02,
        "effect": "set.mult_bonus = 0.15",
        "hard_effect": [
            {"if": "user_level >= 50 # casino_level >= 5", "then": "set.mult_bonus = 0.25"},
            {"elif": "user_level >= 30", "then": "set.mult_bonus = 0.20"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "silver_pendant"},
    },
    "bomb_cloak": {
        "name": "🛡 Плащ сапёра",
        "desc": "-50% урона от бомб",
        "rarity": "epic",
        "buy": 18000,
        "hp": 100,
        "break_on": ["loss"],
        "break_chance": 0.05,
        "effect": "set.bomb_shield = 0.50",
        "hard_effect": [],
        "after_break": {"type": "GET_SC", "amount": 2000},
    },

    # ============ 🟡 ЛЕГЕНДАРНЫЕ ============
    "phoenix_feather": {
        "name": "🔥 Перо феникса",
        "desc": "Вечный: +25% к множителю",
        "rarity": "legendary",
        "buy": 100000,
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.mult_bonus = 0.25",
        "hard_effect": [
            {"if": "user_level >= 100", "then": "set.mult_bonus = 0.40"},
            {"if": "user_sc >= 100000", "then": "set.xp_bonus = 0.30"},
        ],
        "after_break": {"type": "NOTHING"},
    },
    "crown": {
        "name": "👑 Корона",
        "desc": "+30% к множителю",
        "rarity": "legendary",
        "buy": 150000,
        "hp": 500,
        "break_on": ["loss"],
        "break_chance": 0.01,
        "effect": "set.mult_bonus = 0.30",
        "hard_effect": [
            {"if": "badges_legendary >= 1 # casino_level >= 8",
             "then": "set.mult_bonus = 0.50"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "golden_ring"},
    },
}


RARITY_EMOJI = {
    "common":    "⚪",
    "rare":      "🔵",
    "epic":      "🟣",
    "legendary": "🟡",
}

MAX_ITEM_SLOTS = 3