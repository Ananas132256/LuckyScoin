import html
import time

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

from admin import is_admin
from utils import nav_footer, safe_answer


STATUSES = {
    "new": ("🆕", "Не просмотрена"),
    "seen": ("👀", "Просмотрена"),
    "progress": ("🔧", "На этапе решения"),
    "resolved": ("✅", "Решена"),
}


class ComplaintStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_answer = State()


def _status_emoji(status: str) -> str:
    return STATUSES.get(status, ("❓", "Неизвестно"))[0]


def _status_name(status: str) -> str:
    return STATUSES.get(status, ("❓", "Неизвестно"))[1]


def _fmt_time(timestamp: int) -> str:
    if not timestamp:
        return "—"
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(timestamp))


def _truncate(text: str, max_len: int = 50) -> str:
    text = text or ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


class Complaints:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "complaint")(self.cb_complaint)
        dp.callback_query(F.data == "complaint_new")(self.cb_new)
        dp.callback_query(F.data.startswith("complaint_view_"))(self.cb_view)

        dp.callback_query(F.data == "admin_complaints")(self.cb_admin_list)
        dp.callback_query(F.data.startswith("admin_complaints_filter_"))(self.cb_admin_list)
        dp.callback_query(F.data.startswith("admin_complaint_"))(self.cb_admin_view)
        dp.callback_query(F.data.startswith("admin_cstatus_"))(self.cb_admin_status)
        dp.callback_query(F.data.startswith("admin_canswer_"))(self.cb_admin_answer_start)

        dp.message(ComplaintStates.waiting_for_text)(self.on_text)
        dp.message(ComplaintStates.waiting_for_answer)(self.on_answer)

    async def _edit(self, query, text, reply_markup):
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def _notify_user(self, user_id, text):
        try:
            await self.brain.bot.send_message(user_id, text, parse_mode="HTML")
            return True
        except Exception as error:
            print(f"⚠️ Не удалось отправить уведомление о жалобе пользователю {user_id}: {error}")
            return False

    def _user_keyboard(self, complaints):
        rows = [
            [InlineKeyboardButton(text="📝 Пожаловаться", callback_data="complaint_new")]
        ]
        for complaint in complaints:
            rows.append([
                InlineKeyboardButton(
                    text=(
                        f"{_status_emoji(complaint['status'])} "
                        f"#{complaint['id']} — {_fmt_time(complaint['created_at'])[:10]}"
                    ),
                    callback_data=f"complaint_view_{complaint['id']}",
                )
            ])
        rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])
        rows.extend(nav_footer())
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def cb_complaint(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            await safe_answer(query)
            complaints = self.brain.db.get_user_complaints(query.from_user.id, limit=3)
            lines = ["📮 <b>Жалобы</b>\n"]
            if not complaints:
                lines.append("У тебя пока нет жалоб.")
            else:
                for complaint in complaints:
                    summary = html.escape(_truncate(complaint["text"], 50))
                    lines.append(
                        f"{_status_emoji(complaint['status'])} "
                        f"#{complaint['id']} от {_fmt_time(complaint['created_at'])[:10]} "
                        f"— {summary}"
                    )
                    if complaint["answer"]:
                        answer = html.escape(_truncate(complaint["answer"], 120))
                        lines.append(f"💬 Ответ: {answer}")
            await self._edit(query, "\n".join(lines), self._user_keyboard(complaints))
        except Exception as error:
            print(f"⚠️ Ошибка экрана жалоб: {error}")
            await safe_answer(query, "Не удалось загрузить жалобы.", show_alert=True)

    async def cb_new(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            await state.set_state(ComplaintStates.waiting_for_text)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="complaint")
            ]] + nav_footer())
            await safe_answer(query)
            await self._edit(
                query,
                "✏️ Напиши текст жалобы (от 5 до 500 символов). /cancel — отмена",
                keyboard,
            )
        except Exception as error:
            print(f"⚠️ Ошибка создания жалобы: {error}")
            await state.clear()
            await safe_answer(query, "Не удалось начать создание жалобы.", show_alert=True)

    async def on_text(self, message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if text.lower() == "/cancel":
            await state.clear()
            return await message.answer("Создание жалобы отменено.")
        if not 5 <= len(text) <= 500:
            return await message.answer("Текст жалобы должен содержать от 5 до 500 символов.")

        try:
            username = message.from_user.username or message.from_user.first_name or "anon"
            complaint_id = self.brain.db.add_complaint(
                message.from_user.id, username, text
            )
            await state.clear()
            await message.answer(
                f"✅ Жалоба #{complaint_id} отправлена. Админы ответят в ближайшее время."
            )
        except Exception as error:
            print(f"⚠️ Ошибка сохранения жалобы: {error}")
            await message.answer("Не удалось сохранить жалобу. Попробуй ещё раз позже.")

    async def cb_view(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            complaint_id = int(query.data.rsplit("_", 1)[1])
            complaint = self.brain.db.get_complaint(complaint_id)
            if not complaint or complaint["user_id"] != query.from_user.id:
                return await safe_answer(query, "Жалоба не найдена.", show_alert=True)
            await safe_answer(query)

            text = (
                f"📮 <b>Жалоба #{complaint['id']}</b>\n\n"
                f"📅 Создана: <b>{_fmt_time(complaint['created_at'])}</b>\n"
                f"📌 Статус: {_status_emoji(complaint['status'])} "
                f"<b>{html.escape(_status_name(complaint['status']))}</b>\n\n"
                f"<b>Текст:</b>\n{html.escape(complaint['text'])}"
            )
            if complaint["answer"]:
                text += f"\n\n💬 <b>Ответ:</b>\n{html.escape(complaint['answer'])}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад", callback_data="complaint")
            ]] + nav_footer())
            await self._edit(query, text, keyboard)
        except (TypeError, ValueError):
            await safe_answer(query, "Некорректный номер жалобы.", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка просмотра жалобы: {error}")
            await safe_answer(query, "Не удалось открыть жалобу.", show_alert=True)

    async def cb_admin_list(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            if not is_admin(query.from_user.id, self.brain.db):
                return await safe_answer(query, "⛔ Нет доступа", show_alert=True)
            await safe_answer(query)
            status = None
            if query.data.startswith("admin_complaints_filter_"):
                status = query.data.rsplit("_", 1)[1]
                if status not in STATUSES:
                    status = None
            complaints = self.brain.db.get_all_complaints(status=status, limit=50)
            filters = [
                ("Все", None),
                ("🆕 Новые", "new"),
                ("👀 Просмотренные", "seen"),
                ("🔧 В работе", "progress"),
                ("✅ Решённые", "resolved"),
            ]
            rows = [[
                InlineKeyboardButton(
                    text=label,
                    callback_data=(
                        "admin_complaints" if filter_status is None
                        else f"admin_complaints_filter_{filter_status}"
                    ),
                )
                for label, filter_status in filters
            ]]
            for complaint in complaints:
                username = complaint["username"] or str(complaint["user_id"])
                label = (
                    f"{_status_emoji(complaint['status'])} #{complaint['id']} "
                    f"от @{_truncate(username, 18)} — "
                    f"{_fmt_time(complaint['created_at'])[:10]}"
                )
                rows.append([InlineKeyboardButton(
                    text=_truncate(label, 64),
                    callback_data=f"admin_complaint_{complaint['id']}",
                )])
            if not complaints:
                text = "📮 <b>Жалобы</b>\n\nВ этой категории жалоб нет."
            else:
                text = f"📮 <b>Жалобы</b> — показано: {len(complaints)}"
            rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_refresh")])
            rows.extend(nav_footer())
            await self._edit(query, text, InlineKeyboardMarkup(inline_keyboard=rows))
        except Exception as error:
            print(f"⚠️ Ошибка списка жалоб для админа: {error}")
            await safe_answer(query, "Не удалось загрузить список жалоб.", show_alert=True)

    async def cb_admin_view(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            if not is_admin(query.from_user.id, self.brain.db):
                return await safe_answer(query, "⛔ Нет доступа", show_alert=True)
            complaint_id = int(query.data.rsplit("_", 1)[1])
            complaint = self.brain.db.get_complaint(complaint_id)
            if not complaint:
                return await safe_answer(query, "Жалоба не найдена.", show_alert=True)
            await safe_answer(query)
            await self._render_admin_complaint(query, complaint)
        except (TypeError, ValueError):
            await safe_answer(query, "Некорректный номер жалобы.", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка просмотра жалобы админом: {error}")
            await safe_answer(query, "Не удалось открыть жалобу.", show_alert=True)

    async def cb_admin_status(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            if not is_admin(query.from_user.id, self.brain.db):
                return await safe_answer(query, "⛔ Нет доступа", show_alert=True)
            _, _, complaint_id_text, status = query.data.split("_", 3)
            if status not in STATUSES:
                return await safe_answer(query, "Некорректный статус.", show_alert=True)
            complaint_id = int(complaint_id_text)
            complaint = self.brain.db.get_complaint(complaint_id)
            if not complaint:
                return await safe_answer(query, "Жалоба не найдена.", show_alert=True)
            if not self.brain.db.update_complaint(
                complaint_id, query.from_user.id, status, answer=None
            ):
                return await safe_answer(query, "Не удалось обновить жалобу.", show_alert=True)
            self.brain.db.log_admin(
                query.from_user.id, f"complaint_status_{status}", str(complaint_id)
            )
            await safe_answer(query, "Статус обновлён.")
            await self._notify_user(
                complaint["user_id"],
                f"📮 Статус твоей жалобы #{complaint_id} изменён на "
                f"<b>{html.escape(_status_name(status))}</b>.",
            )
            await self._render_admin_complaint(
                query, self.brain.db.get_complaint(complaint_id)
            )
        except (TypeError, ValueError):
            await safe_answer(query, "Некорректные данные жалобы.", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка обновления статуса жалобы: {error}")
            await safe_answer(query, "Не удалось изменить статус.", show_alert=True)

    async def _render_admin_complaint(self, query, complaint):
        complaint_id = complaint["id"]
        username = complaint["username"] or "не указан"
        text = (
            f"📮 <b>Жалоба #{complaint_id}</b>\n\n"
            f"👤 Игрок: <b>@{html.escape(username)}</b> "
            f"(<code>{complaint['user_id']}</code>)\n"
            f"📅 Создана: <b>{_fmt_time(complaint['created_at'])}</b>\n"
            f"📌 Статус: {_status_emoji(complaint['status'])} "
            f"<b>{html.escape(_status_name(complaint['status']))}</b>\n"
            f"🛠 Последний админ: <code>{complaint['admin_id'] or '—'}</code>\n\n"
            f"<b>Текст:</b>\n{html.escape(complaint['text'])}"
        )
        if complaint["answer"]:
            text += f"\n\n💬 <b>Ответ:</b>\n{html.escape(complaint['answer'])}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👀 Просмотрена",
                    callback_data=f"admin_cstatus_{complaint_id}_seen",
                ),
                InlineKeyboardButton(
                    text="🔧 В работе",
                    callback_data=f"admin_cstatus_{complaint_id}_progress",
                ),
            ],
            [InlineKeyboardButton(
                text="✅ Решена",
                callback_data=f"admin_cstatus_{complaint_id}_resolved",
            )],
            [InlineKeyboardButton(
                text="💬 Ответить",
                callback_data=f"admin_canswer_{complaint_id}",
            )],
            [InlineKeyboardButton(
                text="⬅️ Назад", callback_data="admin_complaints"
            )],
        ] + nav_footer())
        await self._edit(query, text, keyboard)

    async def cb_admin_answer_start(self, query: CallbackQuery, state: FSMContext):
        try:
            await state.clear()
            if not is_admin(query.from_user.id, self.brain.db):
                return await safe_answer(query, "⛔ Нет доступа", show_alert=True)
            complaint_id = int(query.data.rsplit("_", 1)[1])
            if not self.brain.db.get_complaint(complaint_id):
                return await safe_answer(query, "Жалоба не найдена.", show_alert=True)
            await state.update_data(complaint_id=complaint_id)
            await state.set_state(ComplaintStates.waiting_for_answer)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data=f"admin_complaint_{complaint_id}"
                )
            ]] + nav_footer())
            await safe_answer(query)
            await self._edit(
                query,
                "✏️ Напиши ответ игроку (от 3 до 500 символов). /cancel — отмена",
                keyboard,
            )
        except (TypeError, ValueError):
            await state.clear()
            await safe_answer(query, "Некорректный номер жалобы.", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка начала ответа на жалобу: {error}")
            await state.clear()
            await safe_answer(query, "Не удалось начать ответ.", show_alert=True)

    async def on_answer(self, message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if text.lower() == "/cancel":
            await state.clear()
            return await message.answer("Ответ отменён.")
        if not 3 <= len(text) <= 500:
            return await message.answer("Ответ должен содержать от 3 до 500 символов.")
        if not is_admin(message.from_user.id, self.brain.db):
            await state.clear()
            return await message.answer("⛔ Нет доступа.")

        try:
            data = await state.get_data()
            complaint_id = data.get("complaint_id")
            complaint = self.brain.db.get_complaint(complaint_id)
            if not complaint:
                await state.clear()
                return await message.answer("Жалоба не найдена.")
            if not self.brain.db.update_complaint(
                complaint_id, message.from_user.id, "resolved", answer=text
            ):
                await state.clear()
                return await message.answer("Не удалось сохранить ответ.")
            self.brain.db.log_admin(
                message.from_user.id, "complaint_answer", str(complaint_id)
            )
            await state.clear()
            delivered = await self._notify_user(
                complaint["user_id"],
                f"📮 <b>Ответ на твою жалобу #{complaint_id}:</b>\n\n"
                f"{html.escape(text)}",
            )
            if delivered:
                await message.answer("✅ Ответ отправлен игроку, жалоба отмечена решённой.")
            else:
                await message.answer(
                    "✅ Ответ сохранён, жалоба отмечена решённой, "
                    "но отправить его игроку не удалось."
                )
        except Exception as error:
            print(f"⚠️ Ошибка сохранения ответа на жалобу: {error}")
            await state.clear()
            await message.answer("Не удалось сохранить ответ. Попробуй ещё раз позже.")
