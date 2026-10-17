import asyncio
import time

from handlers.admin import is_admin


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


async def season_loop(brain):
    """Check hourly whether the active season should roll over."""
    await asyncio.sleep(120)
    while True:
        try:
            await _check_season(brain)
        except Exception as error:
            print(f"⚠️ season_loop error: {error}")
        await asyncio.sleep(3600)


async def _check_season(brain):
    from config import SEASON_DURATION_DAYS, SEASON_REWARD_TICKETS

    elapsed = brain.db.get_season_elapsed()
    if elapsed <= 0:
        return

    threshold = SEASON_DURATION_DAYS * 86400
    if elapsed < threshold:
        return

    top = brain.db.get_all_user_ids_sorted_by_lc(limit=3)
    brain.db.start_new_season()
    brain.db.reset_season_data()
    new_num = brain.db.get_current_season()
    brain.db.set_flag("season_current", str(new_num))

    medals = ["🥇", "🥈", "🥉"]
    reward_lines = []
    for place, (user_id, username, lc) in enumerate(top, 1):
        reward = SEASON_REWARD_TICKETS.get(place, 0)
        if reward:
            brain.db.grant_tickets_uncapped(user_id, reward)
        name = f"@{username}" if username else f"id{user_id}"
        reward_lines.append(
            f"{medals[place - 1]} {name} — "
            f"{lc:,} LC → 🎟 {reward}".replace(",", " ")
        )

    text_lines = [
        "🏁 <b>Сезон завершён!</b>\n",
        "Награды топ-3:",
    ]
    if reward_lines:
        text_lines.extend(reward_lines)
    else:
        text_lines.append("<i>Никто не набрал LC.</i>")
    text_lines.append(
        "\n🎉 <b>Начинается новый сезон!</b>\n"
        "LC, казино, статистика и серии сброшены. "
        "Успей забраться на вершину первым!\n\n"
        "<i>Уровень, SC, значки и инвентарь — навсегда "
        "с тобой.</i>"
    )
    broadcast = "\n".join(text_lines)

    for user_id in brain.db.get_all_user_ids():
        try:
            await brain.bot.send_message(
                user_id, broadcast, parse_mode="HTML"
            )
            await asyncio.sleep(0.05)
        except Exception:
            pass

    brain.db.log_admin(0, "auto_end_season", f"new={new_num}")


async def _tick(brain):
    from config import TYCOON_ENABLED

    # Если идёт техперерыв — не спамим
    if brain.db.get_maintenance()["enabled"]:
        return

    now = int(time.time())
    if TYCOON_ENABLED:
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

    # Ежедневные награды доступны также игрокам без казино.
    if brain.db.get_maintenance()["enabled"]:
        return

    for uid in brain.db.get_all_user_ids():
        if is_admin(uid, brain.db):
            continue
        if brain.db.get_flag(f"notif:{uid}", "1") != "1":
            continue

        state = brain.db.get_daily_state(uid)
        if not state["can_claim"]:
            continue

        flag_key = f"daily_nudge_ts:{uid}"
        last_nudge = int(brain.db.get_flag(flag_key, 0))
        if now - last_nudge < 20 * 3600:
            continue

        try:
            await brain.bot.send_message(
                uid,
                "🎁 Твоя ежедневная награда готова!\n"
                "Заходи и забери LC — серия растёт каждый день."
            )
        except Exception:
            continue
        brain.db.set_flag(flag_key, str(now))