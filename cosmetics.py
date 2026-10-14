"""Каталог игровых предметов-медалей и титулов.

Добавляй новые медали в ITEMS: укажи уникальный shop_id,
price_sc, name, desc, rarity, hp и эффекты. hp="inf" задаёт вечную медаль.
"""

ITEMS = {
    # ============ ⚪ COMMON ============
    "leaf": {
        "shop_id": 21,
        "name": "🍃 Листочек",
        "desc": "+5% к удаче, навсегда.",
        "rarity": "common",
        "price_sc": 10,
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.luck = 0.05",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },
    "copper_coin": {
        "shop_id": 22,
        "name": "🪙 Медный грош",
        "desc": "+2% к множителю, навсегда.",
        "rarity": "common",
        "price_sc": 15,
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.mult_bonus = 0.02",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },
    "luck_potion": {
        "shop_id": 23,
        "name": "🧪 Зелье удачи",
        "desc": "+10% к удаче. 50 спинов, потом испаряется.",
        "rarity": "common",
        "price_sc": 40,
        "hp": 50,
        "break_on": ["roll"],
        "break_chance": 0.03,
        "effect": "set.luck = 0.10",
        "hard_effect": [],
        "after_break": {"type": "GET_SC", "amount": 20},
    },
    "three_leaf_clover": {
        "shop_id": 24,
        "name": "☘️ Трёхлистный клевер",
        "desc": "+5% удачи; +15% если серия побед 1+. 100 спинов.",
        "rarity": "common",
        "price_sc": 75,
        "hp": 100,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.luck = 0.05",
        "hard_effect": [
            {"if": "user_streak >= 1", "then": "set.luck = 0.15"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "leaf"},
    },
    "d6_shard": {
        "shop_id": 25,
        "name": "🎲 Обломок D6",
        "desc": "Осколок сломанного D6. +3% удачи, навсегда.",
        "rarity": "common",
        "price_sc": 0,
        "hidden": True,
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.luck = 0.03",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },

    # ============ 🔵 RARE ============
    "four_leaf_clover": {
        "shop_id": 26,
        "name": "🍀 Четырёхлистный клевер",
        "desc": "+15% удачи; +30% если серия побед 1+. 100 спинов.",
        "rarity": "rare",
        "price_sc": 200,
        "hp": 100,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.luck = 0.15",
        "hard_effect": [
            {"if": "user_streak >= 1", "then": "set.luck = 0.30"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "three_leaf_clover"},
    },
    "top_hat": {
        "shop_id": 27,
        "name": "🎩 Фрак",
        "desc": "+8% к множителю; +15% если уровень казино 3+.",
        "rarity": "rare",
        "price_sc": 200,
        "hp": 100,
        "break_on": ["loss"],
        "break_chance": 0.02,
        "effect": "set.mult_bonus = 0.08",
        "hard_effect": [
            {"if": "casino_level >= 3", "then": "set.mult_bonus = 0.15"},
        ],
        "after_break": {"type": "GET_SC", "amount": 50},
    },
    "d6_full": {
        "shop_id": 28,
        "name": "🎲 D6 (целый)",
        "desc": "Каждый 6-й рол даёт удачу ×3. 50 спинов.",
        "rarity": "rare",
        "price_sc": 230,
        "hp": 50,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.luck = 0.10",
        "hard_effect": [
            {
                "if": "badge_roll_count > 0 # badge_roll_count % 6 = 0",
                "then": "set.luck_mult = 3",
            },
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "d6_shard"},
    },
    "fuel_canister": {
        "shop_id": 29,
        "name": "🛢 Канистра с бензином",
        "desc": "+50% к множителю. Перегрев растёт ×2 быстрее. 40 спинов.",
        "rarity": "rare",
        "price_sc": 300,
        "hp": 40,
        "break_on": ["roll"],
        "break_chance": 0.01,
        "effect": "set.mult_bonus = 0.50, set.overheat_speed = 1",
        "hard_effect": [],
        "after_break": {"type": "GET_SC", "amount": 100},
    },
    "target": {
        "shop_id": 30,
        "name": "🎯 Мишень",
        "desc": "+10% множителя; +20% если винрейт 50%+.",
        "rarity": "rare",
        "price_sc": 400,
        "hp": 80,
        "break_on": ["loss"],
        "break_chance": 0.02,
        "effect": "set.mult_bonus = 0.10",
        "hard_effect": [
            {"if": "user_winrate >= 0.5", "then": "set.mult_bonus = 0.20"},
        ],
        "after_break": {"type": "GET_SC", "amount": 100},
    },
    "diamond": {
        "shop_id": 31,
        "name": "💎 Алмаз",
        "desc": "+5% множителя и +5% удачи, навсегда.",
        "rarity": "rare",
        "price_sc": 800,
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.mult_bonus = 0.05, set.luck = 0.05",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },
    "ice_cube": {
        "shop_id": 32,
        "name": "🧊 Ледяной куб",
        "desc": "−30% шанс возгорания. На 3+ стадии перегрева −60%.",
        "rarity": "rare",
        "price_sc": 1200,
        "hp": 100,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.fire_shield = 0.30",
        "hard_effect": [
            {"if": "user_overheat_stage >= 3", "then": "set.fire_shield = 0.60"},
        ],
        "after_break": {"type": "GET_LC", "amount": 200},
    },
    "alchemy_kit": {
        "shop_id": 33,
        "name": "⚗️ Алхимический набор",
        "desc": "+10% XP; +25% если сыграно 1000+ ставок.",
        "rarity": "rare",
        "price_sc": 1500,
        "hp": 100,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.xp_bonus = 0.10",
        "hard_effect": [
            {"if": "user_total_bets >= 1000", "then": "set.xp_bonus = 0.25"},
        ],
        "after_break": {"type": "GET_SC", "amount": 200},
    },

    # ============ 🟣 EPIC ============
    "fireball": {
        "shop_id": 34,
        "name": "🔥 Огненный шар",
        "desc": "Множитель растёт с перегревом: до ×6 на 5 стадии.",
        "rarity": "epic",
        "price_sc": 1000,
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.mult_bonus = 0.02",
        "hard_effect": [
            {"if": "user_overheat_stage = 5", "then": "set.mult_bonus = 0.60"},
            {"elif": "user_overheat_stage = 4", "then": "set.mult_bonus = 0.40"},
            {"elif": "user_overheat_stage = 3", "then": "set.mult_bonus = 0.20"},
            {"elif": "user_overheat_stage = 2", "then": "set.mult_bonus = 0.15"},
        ],
        "after_break": {"type": "NOTHING"},
    },
    "whiskey": {
        "shop_id": 35,
        "name": "🥃 Виски",
        "desc": "+20% к множителю. Ломается на победах. 50 спинов.",
        "rarity": "epic",
        "price_sc": 3000,
        "hp": 50,
        "break_on": ["win"],
        "break_chance": 0.05,
        "effect": "set.mult_bonus = 0.20",
        "hard_effect": [],
        "after_break": {"type": "GET_SC", "amount": 500},
    },
    "crystal_ball": {
        "shop_id": 36,
        "name": "🔮 Хрустальный шар",
        "desc": "+5% удачи; +25% ночью (22:00–04:00).",
        "rarity": "epic",
        "price_sc": 5000,
        "hp": 60,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.luck = 0.05",
        "hard_effect": [
            {"if": "hour_of_day >= 22 | hour_of_day <= 4", "then": "set.luck = 0.25"},
        ],
        "after_break": {"type": "GET_LC", "amount": 500},
    },
    "sun_amulet": {
        "shop_id": 37,
        "name": "☀️ Солнечный амулет",
        "desc": "+5% удачи; +25% днём (10:00–14:00).",
        "rarity": "epic",
        "price_sc": 5000,
        "hp": 60,
        "break_on": ["roll"],
        "break_chance": 0.02,
        "effect": "set.luck = 0.05",
        "hard_effect": [
            {"if": "hour_of_day >= 10 # hour_of_day <= 14", "then": "set.luck = 0.25"},
        ],
        "after_break": {"type": "GET_LC", "amount": 500},
    },
    "double_reel": {
        "shop_id": 38,
        "name": "🎰 Двойная катушка",
        "desc": "+10% множителя; +35% если серия побед 3+. 60 спинов.",
        "rarity": "epic",
        "price_sc": 8000,
        "hp": 60,
        "break_on": ["roll"],
        "break_chance": 0.01,
        "effect": "set.mult_bonus = 0.10",
        "hard_effect": [
            {"if": "user_streak >= 3", "then": "set.mult_bonus = 0.35"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "target"},
    },
    "crown": {
        "shop_id": 39,
        "name": "👑 Корона",
        "desc": "+15% множителя; +25% если рядом есть легендарка.",
        "rarity": "epic",
        "price_sc": 12000,
        "hp": 150,
        "break_on": ["loss"],
        "break_chance": 0.01,
        "effect": "set.mult_bonus = 0.15",
        "hard_effect": [
            {"if": "badges_legendary >= 1", "then": "set.mult_bonus = 0.25"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "diamond"},
    },
}

# Обратное имя для существующего кода экипировки: медали являются предметами.
BADGES = ITEMS

CRAFT_CHANCES = {
    "common": [("up", 0.60), ("same", 0.25), ("nothing", 0.15)],
    "rare": [("up", 0.60), ("same", 0.25), ("nothing", 0.15)],
    "epic": [("up", 0.60), ("same", 0.25), ("nothing", 0.15)],
}
RARITY_ORDER = ["common", "rare", "epic", "legendary"]


def get_next_rarity(rarity: str) -> str:
    """Возвращает следующую ступень редкости."""
    if rarity == "epic":
        return "epic"
    idx = RARITY_ORDER.index(rarity) if rarity in RARITY_ORDER else 0
    return RARITY_ORDER[min(idx + 1, len(RARITY_ORDER) - 1)]


TITLES = {}


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
    if "win_mult" in effect_dict:
        parts.append(f"×{effect_dict['win_mult']:g} множитель выигрыша")
    if "overheat_speed" in effect_dict:
        parts.append(f"+{effect_dict['overheat_speed']:g} к перегреву за спин")
    return " • ".join(parts) if parts else "— без бонусов —"