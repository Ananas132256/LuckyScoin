"""Каталог игровых предметов-медалей и титулов.

Добавляй новые медали в ITEMS: укажи уникальный shop_id,
price_sc, name, desc, rarity, hp и эффекты. hp="inf" задаёт вечную медаль.
"""

ITEMS = {
    "leaf": {
        "shop_id": 21,
        "name": "🍃 Листочек",
        "desc": "+5% удачи, бесконечное число использований",
        "rarity": "common",
        "price_sc": 10,
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.luck = 0.05",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },
    "three_leaf_clover": {
        "shop_id": 22,
        "name": "☘️ Трёхлистный клевер",
        "desc": "+5% удачи; +15%, если предыдущий ролл был выигрышным. 100 спинов",
        "rarity": "common",
        "price_sc": 75,
        "hp": 100,
        "break_on": [],
        "break_chance": 0,
        "effect": "set.luck = 0.05",
        "hard_effect": [
            {"if": "user_streak >= 1", "then": "set.luck = 0.15"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "leaf"},
    },
    "four_leaf_clover": {
        "shop_id": 23,
        "name": "🍀 Четырёхлистный клевер",
        "desc": "+15% удачи; +30%, если предыдущий ролл был выигрышным. 100 спинов",
        "rarity": "rare",
        "price_sc": 200,
        "hp": 100,
        "break_on": [],
        "break_chance": 0,
        "effect": "set.luck = 0.15",
        "hard_effect": [
            {"if": "user_streak >= 1", "then": "set.luck = 0.30"},
        ],
        "after_break": {"type": "GET_ITEM", "item_id": "three_leaf_clover"},
    },
    "d6_full": {
        "shop_id": 24,
        "name": "🎲 D6 (целый)",
        "desc": "Каждый 6-й рол: удача ×3. 50 использований.",
        "rarity": "rare",
        "unlock": {},
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
    "d6_shard": {
        "shop_id": 25,
        "name": "🎲 Обломок D6",
        "desc": "Осколок сломанного D6. +3% удачи.",
        "rarity": "common",
        "unlock": {},
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "set.luck = 0.03",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },
    "fireball": {
        "shop_id": 26,
        "name": "🔥 Огненный шар",
        "desc": "Множитель выигрыша зависит от перегрева: стадия 0 — ×0,2; 1 — ×1; 2 — ×1,5; 3 — ×2; 4 — ×4; 5 — ×6. Бесконечное число использований.",
        "rarity": "epic",
        "price_sc": 1000,
        "hp": "inf",
        "break_on": [],
        "break_chance": 0,
        "effect": "",
        "hard_effect": [
            {"if": "user_overheat_stage = 0", "then": "set.win_mult = 0.2"},
            {"if": "user_overheat_stage = 1", "then": "set.win_mult = 1"},
            {"if": "user_overheat_stage = 2", "then": "set.win_mult = 1.5"},
            {"if": "user_overheat_stage = 3", "then": "set.win_mult = 2"},
            {"if": "user_overheat_stage = 4", "then": "set.win_mult = 4"},
            {"if": "user_overheat_stage >= 5", "then": "set.win_mult = 6"},
        ],
        "after_break": {"type": "NOTHING"},
    },
    "gasoline_canister": {
        "shop_id": 27,
        "name": "⛽ Канистра с бензином",
        "desc": "Ускоряет перегрев (+1 очко за спин) и увеличивает выигрышный множитель в 1,5 раза. 40 использований.",
        "rarity": "rare",
        "price_sc": 300,
        "hp": 40,
        "break_on": [],
        "break_chance": 0,
        "effect": "set.overheat_speed = 1, set.win_mult = 1.5",
        "hard_effect": [],
        "after_break": {"type": "NOTHING"},
    },
}

# Обратное имя для существующего кода экипировки: медали являются предметами.
BADGES = ITEMS
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