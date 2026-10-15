"""
Парсер эффектов медалей.
EFFECT: "set.переменная = значение"  или  "give.переменная = значение"
HARD_EFFECT: список блоков с if/elif/else
"""

import random


# ---------- ПАРСЕР СТРОКИ ----------

def parse_effect_string(s: str):
    """
    "set.mult_bonus = 0.10"  →  ("set", "mult_bonus", 0.1)
    "give.user_sc = 1000"    →  ("give", "user_sc", 1000)
    """
    if not s:
        return None
    s = s.strip()
    if "=" not in s:
        return None
    left, right = s.split("=", 1)
    left, right = left.strip(), right.strip()
    if "." not in left:
        return None
    action, var = left.split(".", 1)
    action = action.strip().lower()
    var = var.strip()

    try:
        if right.replace(".", "", 1).lstrip("-").isdigit():
            val = float(right) if "." in right else int(right)
        else:
            val = float(right)
    except ValueError:
        return None
    return action, var, val


# ---------- УСЛОВИЯ ----------

_OPS = [">=", "<=", "!=", ">", "<", "=", "!"]


def _eval_part(part: str, stats: dict) -> bool:
    part = part.strip()
    for op in _OPS:
        if op in part:
            left, right = part.split(op, 1)
            left, right = left.strip(), right.strip()
            if "%" in left:
                stat_name, divisor = left.split("%", 1)
                try:
                    left_val = float(stats.get(stat_name.strip(), 0)) % float(divisor)
                except (ValueError, TypeError, ZeroDivisionError):
                    return False
            else:
                left_val = stats.get(left, 0)
            try:
                if right.replace(".", "", 1).lstrip("-").isdigit():
                    right_val = float(right) if "." in right else int(right)
                else:
                    right_val = float(right)
            except ValueError:
                right_val = right
            try:
                lv = float(left_val)
                rv = float(right_val)
                if op == "=":  return lv == rv
                if op == "!=": return lv != rv
                if op == ">":  return lv > rv
                if op == ">=": return lv >= rv
                if op == "<":  return lv < rv
                if op == "<=": return lv <= rv
            except (ValueError, TypeError):
                return False
    return False


def eval_condition(cond_str: str, stats: dict) -> bool:
    """# = И, | = ИЛИ"""
    if not cond_str:
        return False
    for or_part in cond_str.split("|"):
        and_parts = [p.strip() for p in or_part.split("#")]
        if all(_eval_part(p, stats) for p in and_parts):
            return True
    return False


# ---------- ПРИМЕНЕНИЕ ЭФФЕКТОВ ----------

def _normalize_effects(effect_input):
    """Normalize effect strings, including comma-separated and list formats."""
    if isinstance(effect_input, str):
        effect_strings = [effect_input]
    elif isinstance(effect_input, list):
        effect_strings = effect_input
    else:
        return []

    return [
        effect.strip()
        for effect_string in effect_strings
        if isinstance(effect_string, str)
        for effect in effect_string.split(",")
        if effect.strip()
    ]


def apply_effects(effect_strings, effects: dict):
    for s in _normalize_effects(effect_strings):
        parsed = parse_effect_string(s)
        if not parsed:
            continue
        action, var, val = parsed
        if action == "set":
            effects[var] = val
        elif action == "give":
            effects[var] = effects.get(var, 0) + val


def get_badge_effects(badge: dict, stats: dict, roll_count: int = 0) -> dict:
    """Эффекты одной медали (effect + hard_effect)."""
    stats = {**stats, "badge_roll_count": roll_count}
    effects = {}
    if badge.get("effect"):
        apply_effects([badge["effect"]], effects)

    hard = badge.get("hard_effect", [])
    for block in hard:
        if "if" in block:
            if eval_condition(block["if"], stats):
                apply_effects(block.get("then", ""), effects)
                return effects
        elif "elif" in block:
            if eval_condition(block["elif"], stats):
                apply_effects(block.get("then", ""), effects)
                return effects
        elif "else" in block:
            apply_effects(block.get("else", ""), effects)
            return effects
    return effects


def get_total_effects(brain, user_id: int) -> dict:
    """Все эффекты от надетых медалей."""
    from cosmetics import BADGES

    stats = brain.db.get_extended_stats(user_id)
    effects = {}

    for slot, bid in brain.db.get_user_badges(user_id).items():
        if bid and bid in BADGES:
            roll_count = brain.db.get_badge_roll_count(user_id, slot)
            badge_eff = get_badge_effects(BADGES[bid], stats, roll_count)
            for k, v in badge_eff.items():
                if k == "win_mult":
                    effects[k] = effects.get(k, 1) * v
                else:
                    effects[k] = effects.get(k, 0) + v

    for effect_name in ("luck", "mult_bonus", "xp_bonus"):
        multiplier_name = f"{effect_name}_mult"
        if multiplier_name in effects:
            effects[effect_name] = effects.get(effect_name, 0) * effects.pop(
                multiplier_name
            )

    return effects


# ---------- ПОЛОМКА МЕДАЛЕЙ ----------

def should_break(badge: dict, trigger: str) -> bool:
    if badge.get("hp") == "inf":
        return False
    if trigger not in badge.get("break_on", []):
        return False
    return random.random() < badge.get("break_chance", 0)


def handle_break(brain, user_id: int, badge_id: str, slot: int):
    from cosmetics import BADGES, badge_slots_for_level
    badge = BADGES.get(badge_id)
    if not badge:
        return None
    brain.db.remove_user_badge(user_id, slot, preserve_state=False)
    if badge.get("shop_id"):
        brain.db.remove_item(user_id, badge["shop_id"], 1)
    brain.db.log_event(
        user_id, "", "break_badge", f"{badge_id}|{slot}"
    )
    after = badge.get("after_break", {"type": "NOTHING"})
    t = after.get("type", "NOTHING")
    if t == "NOTHING":
        return f"💔 <b>{badge['name']}</b> сломался и пропал."
    if t == "GET_SC":
        amt = after.get("amount", 0)
        brain.db.add_balance(user_id, "lc", amt)
        return f"💔 <b>{badge['name']}</b> сломался! Взамен +{amt} LC."
    if t == "GET_LC":
        amt = after.get("amount", 0)
        brain.db.add_balance(user_id, "lc", amt)
        return f"💔 <b>{badge['name']}</b> сломался! Взамен +{amt} LC."
    if t == "GET_ITEM":
        new_id = after.get("item_id")
        if new_id and new_id in BADGES:
            # Новая медаль занимает первый свободный слот.
            level = brain.db.get_user(user_id)["level"]
            max_slots = badge_slots_for_level(level)
            equipped = brain.db.get_user_badges(user_id)
            free_slot = None
            for i in range(max_slots):
                if not equipped.get(i):
                    free_slot = i
                    break
            if free_slot is not None:
                brain.db.set_user_badge(user_id, free_slot, new_id)
                return f"💔 <b>{badge['name']}</b> сломался! Взамен <b>{BADGES[new_id]['name']}</b>."
            else:
                # нет свободного слота — дадим LC вместо SC
                brain.db.add_balance(user_id, "lc", 5000)
                return f"💔 <b>{badge['name']}</b> сломался! Слотов нет, +5000 LC."
    return f"💔 <b>{badge['name']}</b> сломался."