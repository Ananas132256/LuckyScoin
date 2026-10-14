import asyncio
import time


CHECK_INTERVAL = 1800          # 30 минут
NOTIFY_COOLDOWN = 8 * 3600     # не чаще раза в 8 часов одному юзеру


async def notifier_loop(brain):
    """Бесконечный цикл: проверяет казино и шлёт пуши."""
    # Первый запуск — через 5 минут после старта, чтоб бот оклемался
    await asyncio.sleep(300)
    while True:
        try:
            await _tick(brain)
        except Exception as e:
            print(f"⚠️ notifier error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)


async def _tick(brain):
    # Если идёт техперерыв — не спамим
    if brain.db.get_maintenance()["enabled"]:
        return

    now = int(time.time())
    user_ids = brain.db.get_users_with_casino()

    for uid in user_ids:
        try:
            casino = brain.db.get_casino(uid)
            if not casino:
                continue

            auto_collected = brain.db.auto_collect_casino(uid)
            if auto_collected is not None:
                if auto_collected > 0:
                    await brain.bot.send_message(
                        uid,
                        f"💼 <b>Бухгалтер собрал доход казино!</b>\n\n"
                        f"🏢 {casino['name']}\n"
                        f"💰 Начислено: <b>{auto_collected} LC</b>",
                        parse_mode="HTML"
                    )
                continue

            # Хранилище не заполнено — пропускаем
            pending, elapsed, income = brain.db.get_pending_income(uid)
            if elapsed < brain.db.CASINO_MAX_HOURS * 3600:
                continue

            # Кулдаун: не чаще раза в 8 часов
            last = brain.db.get_last_storage_notify(uid)
            if now - last < NOTIFY_COOLDOWN:
                continue

            # Отправляем
            try:
                await brain.bot.send_message(
                    uid,
                    f"📦 <b>Хранилище казино заполнено!</b>\n\n"
                    f"🏢 {casino['name']}\n"
                    f"💰 Накоплено: <b>{pending} LC</b>\n\n"
                    f"<i>Собери доход — иначе не копится дальше.</i>",
                    parse_mode="HTML"
                )
                brain.db.set_last_storage_notify(uid, now)
            except Exception:
                # Юзер мог заблокировать бота — не страшно
                pass
        except Exception:
            continue