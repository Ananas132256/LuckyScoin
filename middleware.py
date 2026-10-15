from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class MaintenanceMiddleware(BaseMiddleware):
    def __init__(self, brain, admin_ids):
        self.brain = brain
        self.admin_ids = admin_ids

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")

        # Пропускаем статичных админов
        if user and user.id in self.admin_ids:
            return await handler(event, data)

        # Пропускаем динамических админов из базы данных
        try:
            if user and self.brain.db.is_db_admin(user.id):
                return await handler(event, data)
        except Exception as error:
            # При ошибке базы данных не пропускаем пользователя и не прерываем middleware.
            print(f"⚠️ Middleware: ошибка проверки админа {error}")

        # /start остаётся доступен, чтобы пользователи могли получить сообщение о техперерыве.
        if isinstance(event, Message):
            text = event.text or ""
            if text.startswith("/start"):
                return await handler(event, data)

        # Проверяем техперерыв
        maint = self.brain.db.get_maintenance()
        if not maint["enabled"]:
            return await handler(event, data)

        # Блокируем
        reason = maint["reason"] or "ведутся работы"
        text = (
            f"🛠 <b>Технический перерыв</b>\n\n"
            f"Причина: <i>{reason}</i>\n\n"
            f"Скоро вернёмся! Спасибо за терпение."
        )
        if isinstance(event, Message):
            await event.answer(text, parse_mode="HTML")
        elif isinstance(event, CallbackQuery):
            await event.answer("🛠 Идут техработы", show_alert=True)
        return  # не вызываем handler


class ActivityMiddleware(BaseMiddleware):
    """Lightweight screen tracker for callbacks and bot entry commands."""

    SCREEN_BY_PREFIX = (
        ("menu", "menu"),
        ("play", "play"),
        ("choose_", "play_bet"),
        ("roulette", "play_roulette"),
        ("exchange", "play_exchange"),
        ("casino", "casino"),
        ("tycoon_", "casino_tycoon"),
        ("shop", "shop"),
        ("trade", "trade"),
        ("inv", "inv"),
        ("top", "top"),
        ("profile", "profile"),
        ("settings", "settings"),
        ("complaint", "complaint"),
        ("admin_", "admin"),
    )

    def __init__(self, brain):
        self.brain = brain

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        try:
            screen = self._detect_screen(event)
            if screen:
                self.brain.db.set_user_screen(user.id, screen)
        except Exception as error:
            try:
                print(f"⚠️ ActivityMiddleware: {error}")
            except Exception:
                pass
        return await handler(event, data)

    def _detect_screen(self, event) -> str | None:
        if isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            for prefix, screen in self.SCREEN_BY_PREFIX:
                if callback_data.startswith(prefix):
                    return screen
            return None
        if isinstance(event, Message):
            text = event.text or ""
            if text.startswith("/start") or text.startswith("/menu"):
                return "menu"
        return None