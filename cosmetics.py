"""
ЗНАЧКИ (артефакты) и ТИТУЛЫ.

ЗНАЧКИ — дают эффекты, надеваются в ячейки.
ТИТУЛЫ — просто надпись, показывается в профиле.

Чтобы добавить значок — скопируй любой блок и поменяй id/name/effect.
Чтобы добавить титул — то же, но без effect.

Доступные эффекты (ключ effect):
    "mult_bonus":     float — +X к множителю выигрыша (0.10 = +10%)
    "xp_bonus":       float — +X к опыту
    "bomb_shield":    float — уменьшает урон от 💣 (0.30 = -30% урона)
    "luck":           float — сдвигает веса в пользу хороших символов (0.10 = 10%)
    "reroll_bonus":   float — дополнительный множитель на длину цепочки рероллов

Условия unlock:
    {}                 — доступно всем
    {"level": 5}       — по уровню
    {"sc": 5000}       — по балансу SC
    {"lc": 1000}       — по балансу LC
    {"games": 100}     — по количеству игр
    {"wins": 50}       — по количеству побед
    {"room_level": 3}  — по уровню своего казино
"""


# ============================================================
#  ЗНАЧКИ (артефакты с баффами)
# ============================================================

BADGES = {
    "rookie": {
        "name": "🎲 Новичок",
        "desc": "Просто для красоты",
        "rarity": "common",
        "unlock": {},
        "effect": {},
    },
    "lucky": {
        "name": "🍀 Везунчик",
        "desc": "+5% к множителю выигрыша",
        "rarity": "common",
        "unlock": {"level": 5},
        "effect": {"mult_bonus": 0.05},
    },
    "hard_worker": {
        "name": "⛏️ Старатель",
        "desc": "+15% к опыту",
        "rarity": "common",
        "unlock": {"level": 10},
        "effect": {"xp_bonus": 0.15},
    },
    "bomb_defuser": {
        "name": "🛡️ Сапёр",
        "desc": "-40% урона от бомб 💣",
        "rarity": "rare",
        "unlock": {"level": 15},
        "effect": {"bomb_shield": 0.40},
    },
    "lucky_pro": {
        "name": "🍀 Про-везение",
        "desc": "+12% к множителю",
        "rarity": "rare",
        "unlock": {"level": 25},
        "effect": {"mult_bonus": 0.12},
    },
    "lucky_aura": {
        "name": "✨ Аура удачи",
        "desc": "Сдвигает веса в пользу редких символов",
        "rarity": "epic",
        "unlock": {"level": 40},
        "effect": {"luck": 0.15},
    },
    "tycoon": {
        "name": "🏢 Магнат",
        "desc": "+8% к множителю и +10% XP",
        "rarity": "epic",
        "unlock": {"room_level": 5},
        "effect": {"mult_bonus": 0.08, "xp_bonus": 0.10},
    },
    "legend": {
        "name": "👑 Легенда",
        "desc": "+20% к множителю",
        "rarity": "legendary",
        "unlock": {"level": 70},
        "effect": {"mult_bonus": 0.20},
    },
    "whale": {
        "name": "🐋 Кит",
        "desc": "+25% к множителю, -60% урона от бомб",
        "rarity": "legendary",
        "unlock": {"sc": 50000},
        "effect": {"mult_bonus": 0.25, "bomb_shield": 0.60},
    },
    # "lucky_star": {
    #     "name": "🌟 Счастливая звезда",
    #     "desc": "+8% удачи и +10% XP",
    #     "rarity": "epic",
    #     "unlock": {"level": 30},
    #     "effect": {"luck": 0.08, "xp_bonus": 0.10},
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


def describe_effect(effect: dict) -> str:
    if not effect:
        return "— без бонусов —"
    parts = []
    if "mult_bonus" in effect:
        parts.append(f"+{int(effect['mult_bonus']*100)}% множитель")
    if "xp_bonus" in effect:
        parts.append(f"+{int(effect['xp_bonus']*100)}% XP")
    if "bomb_shield" in effect:
        parts.append(f"-{int(effect['bomb_shield']*100)}% урон 💣")
    if "luck" in effect:
        parts.append(f"+{int(effect['luck']*100)}% удача")
    if "reroll_bonus" in effect:
        parts.append(f"+{int(effect['reroll_bonus']*100)}% реролл")
    return " • ".join(parts) if parts else "— без бонусов —"