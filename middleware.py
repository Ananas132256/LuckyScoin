from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class MaintenanceMiddleware(BaseMiddleware):
    def __init__(self, brain, admin_ids):
        self.brain = brain
        self.admin_ids = admin_ids

    async def __call__(self, handler, event, data):
        # Пропускаем админов
        user = data.get("event_from_user")
        if user and user.id in self.admin_ids:
            return await handler(event, data)

        # Пропускаем /start — чтобы юзер знал про техперерыв
        if isinstance(event, Message):
            text = event.text or ""
            if text.startswith("/start") or text.startswith("/admin"):
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