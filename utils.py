from html import escape

from aiogram.types import CallbackQuery, InlineKeyboardButton


async def safe_answer(query, *args, **kwargs):
    try:
        await query.answer(*args, **kwargs)
    except Exception:
        pass


def format_number(n: int) -> str:
    """Format an integer with spaces as thousands separators."""
    return f"{n:,}".replace(",", " ")


def format_sc(value) -> str:
    """Форматирует SC с разделителями тысяч и не более чем двумя знаками."""
    value = round(float(value), 2)
    if value == int(value):
        return format_number(int(value))
    return f"{value:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


def hero_card(user: dict, extra: str = "") -> str:
    """Render a compact HTML profile card from a database user dict."""
    username = escape(str(user.get("username") or "player"))
    title = escape(str(user.get("title") or ""))
    title_line = f"  •  🏷 {title}" if title else ""

    level = int(user.get("level") or 0)
    xp = max(0, int(user.get("xp") or 0))
    xp_required = 100 * (level + 1)
    progress = min(xp / xp_required, 1.0) if xp_required > 0 else 0.0
    percent = int(progress * 100)
    filled = int(progress * 10)
    xp_bar = "▰" * filled + "▱" * (10 - filled)

    sc = format_sc(user.get("sc") or 0)
    lc = format_number(int(user.get("lc") or 0))
    extra_line = f"\n{escape(extra)}" if extra else ""
    return (
        f"👤 @{username}{title_line}\n"
        f"⭐ Ур. {level}  {xp_bar} {percent}%\n"
        f"💰 SC {sc}  ·  🍀 LC {lc}{extra_line}"
    )


def with_hero(body: str, user: dict, extra: str = "") -> str:
    return f"{hero_card(user, extra)}\n\n{'─' * 16}\n\n{body}"


def nav_footer(current: str | None = None) -> list[list[InlineKeyboardButton]]:
    """Return footer rows; callers adding them to a keyboard must use .extend()."""
    destinations = (
        ("play", "🎰 Играть"),
        ("casino", "🏢 Казино"),
        ("top", "🏆 Топ"),
        ("profile", "👤 Профиль"),
    )
    destination_row = [
        InlineKeyboardButton(
            text=f"{label} ✓" if current == key else label,
            callback_data=key,
        )
        for key, label in destinations
    ]
    menu_row = [
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="menu",
        )
    ]
    return [destination_row, menu_row]


def is_current_screen(query: CallbackQuery, screen: str) -> bool:
    """Identify a root screen before a footer callback repeats its edit."""
    message = query.message
    markup = getattr(message, "reply_markup", None)
    rows = markup.inline_keyboard if markup else []
    if not rows or query.data != screen:
        return False
    active = any(
        button.callback_data == screen and button.text.endswith("✓")
        for button in rows[-1]
    )
    if not active:
        return False

    text = getattr(message, "text", None) or ""
    markers = {
        "play": "Игровой зал LuckyScoin",
        "casino": "Место в рейтинге:",
        "top": "🏆 <b>Топ по ",
        "profile": "📊 Винрейт:",
    }
    marker = markers.get(screen)
    return bool(marker and marker in text)
