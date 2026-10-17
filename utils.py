from collections.abc import Iterable, Sequence
from datetime import date, datetime
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


def in_date_range(start: tuple, end: tuple, now=None) -> bool:
    """Check whether a date falls within inclusive (year, month, day) bounds."""
    start_date = date(*start)
    end_date = date(*end)
    if now is None:
        current_date = datetime.now().date()
    elif isinstance(now, datetime):
        current_date = now.date()
    elif isinstance(now, date):
        current_date = now
    else:
        current_date = date(*now)
    return start_date <= current_date <= end_date


def hero_card(user: dict, extra: str = "") -> str:
    """Render a compact HTML profile card from a database user dict."""
    username = escape(str(user.get("username") or "player"))
    display_name = str(user.get("display_name") or "").strip()
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
    name_line = escape(display_name) if display_name else f"@{username}"
    return (
        f"👤 {name_line}{title_line}\n"
        f"⭐ Ур. {level}  {xp_bar} {percent}%\n"
        f"💰 SC {sc}  ·  🍀 LC {lc}{extra_line}"
    )


def with_hero(body: str, user: dict, extra: str = "") -> str:
    return f"{hero_card(user, extra)}\n\n{'─' * 16}\n\n{body}"


def nav_footer(
    current: str | None = None,
    destinations: Iterable[str] | None = None,
) -> list[list[InlineKeyboardButton]]:
    """Return footer rows; callers adding them to a keyboard must use .extend()."""
    all_destinations = (
        ("play", "🎰 Играть"),
        ("casino", "🏢 Казино"),
        ("top", "🏆 Топ"),
        ("profile", "👤 Профиль"),
    )
    requested = set(destinations) if destinations is not None else None
    destination_row = [
        InlineKeyboardButton(
            text=label,
            callback_data=key,
        )
        for key, label in all_destinations
        if key != current and (requested is None or key in requested)
    ]
    menu_row = [
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="menu",
        )
    ]
    return ([destination_row] if destination_row else []) + [menu_row]


def paginate(items: Sequence, page: int, per_page: int) -> tuple[Sequence, int]:
    """Return a 1-based page chunk and the total number of pages."""
    if page < 1:
        raise ValueError("page must be at least 1")
    if per_page < 1:
        raise ValueError("per_page must be at least 1")
    total_pages = (len(items) + per_page - 1) // per_page
    start = (page - 1) * per_page
    return items[start:start + per_page], total_pages


def is_current_screen(query: CallbackQuery, screen: str) -> bool:
    """Identify a root screen before a footer callback repeats its edit."""
    message = query.message
    markup = getattr(message, "reply_markup", None)
    if query.data != screen:
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
