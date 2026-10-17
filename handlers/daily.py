import asyncio
import random
import time
from html import escape

from aiogram import Dispatcher, F
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils import nav_footer, safe_answer


class Daily:
    def __init__(self, brain):
        self.brain = brain
        self._edit_lock = asyncio.Lock()
        self._last_edit = 0

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "daily")(self.cb_open)
        dp.callback_query(F.data == "daily_claim")(self.cb_claim)
        dp.callback_query(F.data == "daily_wheel")(self.cb_wheel_spin)

    def _wheel_until(self, user_id) -> int:
        value = self.brain.db.get_flag(f"daily_wheel_until:{user_id}")
        return int(value or 0)

    def _keyboard(self, can_claim, wheel_available):
        rows = []
        if can_claim:
            rows.append([
                InlineKeyboardButton(
                    text="🎁 Забрать награду",
                    callback_data="daily_claim",
                )
            ])
        if wheel_available:
            rows.append([
                InlineKeyboardButton(
                    text="🎡 Крутить колесо",
                    callback_data="daily_wheel",
                )
            ])
        rows.extend(nav_footer())
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _render(self, user_id, state, now):
        from config import DAILY_REWARDS

        streak = state["streak"]
        effective_streak = 0 if state["streak_lost"] else streak
        if state["can_claim"]:
            highlighted_day = min(effective_streak + 1, len(DAILY_REWARDS))
        else:
            highlighted_day = max(1, min(effective_streak, len(DAILY_REWARDS)))
        displayed_streak = 0 if state["streak_lost"] else streak

        lines = [
            "🎁 <b>Ежедневные награды</b>",
            f"Текущая серия: <b>{displayed_streak}</b>",
            "",
        ]
        for day, amount in DAILY_REWARDS:
            if day < highlighted_day:
                marker = "✅"
            elif day == highlighted_day:
                marker = "🎯" if state["can_claim"] else "✅ ⭐"
            else:
                marker = "🔒"
            reward = f"{amount:,} LC".replace(",", " ")
            lines.append(f"{marker} День {day} — <b>{reward}</b>")

        if state["streak_lost"]:
            lines.extend(["", "⚠️ Серия сброшена — ты пропустил день."])
        if not state["can_claim"]:
            remaining = max(0, state["next_claim_at"] - now)
            hours, remainder = divmod(remaining, 3600)
            minutes, seconds = divmod(remainder, 60)
            lines.extend([
                "",
                f"Следующая награда через: <b>{hours:02}:{minutes:02}:{seconds:02}</b>",
            ])

        wheel_available = self._wheel_until(user_id) > now
        return (
            "\n".join(lines),
            self._keyboard(state["can_claim"], wheel_available),
        )

    async def _safe_edit(self, message, text, **kwargs):
        async with self._edit_lock:
            for attempt in range(3):
                elapsed = time.time() - self._last_edit
                if elapsed < 1.1:
                    await asyncio.sleep(1.1 - elapsed)
                self._last_edit = time.time()
                try:
                    await message.edit_text(text, **kwargs)
                    return
                except TelegramRetryAfter as error:
                    if attempt == 2:
                        print(
                            "⚠️ Не удалось обновить экран ежедневной награды "
                            "после трёх попыток."
                        )
                        return
                    elapsed = time.time() - self._last_edit
                    await asyncio.sleep(max(error.retry_after + 1, 1.1 - elapsed))
                except TelegramBadRequest:
                    return

    async def _show_state(self, query, user_id):
        now = int(time.time())
        state = self.brain.db.get_daily_state(user_id)
        text, keyboard = self._render(user_id, state, now)
        await self._safe_edit(
            query.message,
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def cb_open(self, query: CallbackQuery):
        await safe_answer(query)
        await self._show_state(query, query.from_user.id)

    async def cb_claim(self, query: CallbackQuery):
        from config import (
            DAILY_REWARDS,
            DAILY_WHEEL_CHANCE,
            DAILY_WHEEL_COOLDOWN_SECONDS,
        )

        user_id = query.from_user.id
        state = self.brain.db.get_daily_state(user_id)
        if not state["can_claim"]:
            return await safe_answer(
                query,
                "⏳ Уже получено. Возвращайся позже.",
                show_alert=True,
            )

        streak = state["streak"]
        new_streak = 1 if state["streak_lost"] or streak >= 7 else streak + 1
        lc_amount = DAILY_REWARDS[new_streak - 1][1]
        now = int(time.time())
        wheel_granted = (
            new_streak == 7
            or (
                random.random() < DAILY_WHEEL_CHANCE
                and now - state["wheel_ts"] >= DAILY_WHEEL_COOLDOWN_SECONDS
            )
        )

        if not self.brain.db.claim_daily(user_id, new_streak):
            return await safe_answer(
                query,
                "⏳ Уже получено. Возвращайся позже.",
                show_alert=True,
            )

        self.brain.db.add_balance(user_id, "lc", lc_amount)
        self.brain.db.log_event(
            user_id, "", "daily_claim", f"{new_streak}|{lc_amount}"
        )
        wheel_until = now + 300 if wheel_granted else 0
        self.brain.db.set_flag(f"daily_wheel_until:{user_id}", wheel_until)

        await safe_answer(query, f"🎁 Получено: {lc_amount:,} LC".replace(",", " "))
        await self._show_state(query, user_id)

    async def cb_wheel_spin(self, query: CallbackQuery):
        from config import DAILY_WHEEL_PRIZES

        user_id = query.from_user.id
        now = int(time.time())
        flag_key = f"daily_wheel_until:{user_id}"
        if self._wheel_until(user_id) <= now:
            return await safe_answer(
                query, "Колесо недоступно.", show_alert=True
            )

        self.brain.db.set_flag(flag_key, 0)
        prize = random.choices(
            DAILY_WHEEL_PRIZES,
            weights=[item["chance"] for item in DAILY_WHEEL_PRIZES],
            k=1,
        )[0]
        self.brain.db.record_wheel_spin(user_id)
        self.brain.db.add_balance(user_id, "lc", prize["lc_amount"])
        self.brain.db.log_event(
            user_id,
            "",
            "daily_wheel",
            f"{prize['name']}|{prize['lc_amount']}",
        )

        await safe_answer(query)
        symbols = [item["symbol"] for item in DAILY_WHEEL_PRIZES]
        for frame in range(3):
            await self._safe_edit(
                query.message,
                "🎡 <b>Колесо вращается...</b>\n\n"
                + "　".join(
                    symbols[(frame + offset) % len(symbols)]
                    for offset in range(3)
                ),
                parse_mode="HTML",
            )

        localized_name = {
            "Bronze": "Бронза",
            "Silver": "Серебро",
            "Gold": "Золото",
            "Diamond": "Бриллиант",
            "Crown": "Корона",
        }.get(prize["name"], prize["name"])
        result = (
            f"🎡 <b>Колесо остановилось!</b>\n\n"
            f"{escape(prize['symbol'])} {escape(localized_name)}\n"
            f"Награда: <b>{prize['lc_amount']:,} LC</b>"
        ).replace(",", " ")
        buttons = []
        buttons.extend(nav_footer())
        await self._safe_edit(
            query.message,
            result,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML",
        )
