import html
import random

from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from cosmetics import (
    BADGES, TITLES, LEVEL_TITLES, RARITY_EMOJI, CRAFT_CHANCES,
    SLOT_UNLOCK_LEVELS, badge_slots_for_level, get_next_rarity, is_unlocked,
    describe_effect_dict, level_titles_for,
)
from utils import nav_footer, safe_answer, with_hero

# Включает/выключает отображение кнопки "⚒ Крафт" в инвентаре.
# True — крафт доступен, False — кнопка скрыта.
CRAFT_ENABLED = False


class Inventory:
    def __init__(self, brain):
        self.brain = brain

    def register(self, dp: Dispatcher):
        dp.callback_query(F.data == "inv")(self.cb_inv)
        dp.callback_query(F.data == "inv_sell")(self.cb_sell)
        dp.callback_query(F.data.startswith("inv_sell_confirm_"))(self.cb_sell_confirm)
        dp.callback_query(F.data.startswith("inv_sell_"))(self.cb_sell_item)
        # dp.callback_query(F.data == "inv_craft")(self.cb_craft)
        # dp.callback_query(F.data.startswith("inv_craft_"))(self.cb_craft_item)
        # dp.callback_query(F.data.startswith("inv_craft_confirm_"))(self.cb_craft_confirm)
        dp.callback_query(F.data == "inv_badges")(self.cb_badges)
        dp.callback_query(F.data == "inv_titles")(self.cb_titles)
        dp.callback_query(F.data.startswith("inv_slot_"))(self.cb_slot)
        dp.callback_query(F.data.startswith("inv_badge_pick_"))(self.cb_badge_pick)
        dp.callback_query(F.data.startswith("inv_badge_remove_"))(self.cb_badge_remove)
        dp.callback_query(F.data.startswith("inv_title_pick_"))(self.cb_title_pick)

    # ---------- ХЕЛПЕРЫ ----------

    def _ctx(self, user_id):
        u = self.brain.db.get_user(user_id)
        u["user_id"] = user_id
        rooms = self.brain.db.get_rooms(user_id) or []
        room_level = max(rooms) if rooms else 0
        return u, room_level

    def _owned_badges(self, u: dict, room_level: int):
        user_id = u["user_id"]
        result = {
            bid
            for bid, badge in BADGES.items()
            if badge.get("shop_id")
            and self.brain.db.has_item(user_id, badge["shop_id"]) > 0
        }
        result.update(
            bid
            for bid, badge in BADGES.items()
            # Only non-hidden badges may be granted by the free-unlock rule.
            if not badge.get("hidden")
            and not badge.get("price_sc")
            and is_unlocked(badge, u, room_level)
        )
        equipped = self.brain.db.get_user_badges(user_id)
        result.update(
            bid for bid in equipped.values()
            if bid in BADGES
        )
        return result

    def _describe_badge_effect(self, badge: dict, user_id: int) -> str:
        """Показать эффект медали с учётом hard_effect."""
        try:
            from item_system import get_badge_effects
            stats = self.brain.db.get_extended_stats(user_id)
            eff = get_badge_effects(badge, stats)
            return describe_effect_dict(eff)
        except Exception:
            return "—"

    def _badge_by_shop_id(self, item_id):
        return next(
            (
                (badge_id, badge)
                for badge_id, badge in BADGES.items()
                if badge.get("shop_id") == item_id
            ),
            (None, None),
        )

    def _available_badge_quantity(self, user_id, item_id):
        """Количество экземпляров в инвентаре, не занятых ячейками."""
        badge_id, badge = self._badge_by_shop_id(item_id)
        if not badge_id:
            return 0
        equipped = self.brain.db.get_user_badges(user_id)
        equipped_count = sum(1 for owned_id in equipped.values() if owned_id == badge_id)
        return max(
            0,
            self.brain.db.has_item(user_id, item_id) - equipped_count,
        )

    def _get_craftable_items(self, user_id):
        """Список ID медалей, которых в инвентаре есть минимум две."""
        return [
            item_id
            for item_id, _, _, _, category, _ in self.brain.db.get_inventory(user_id)
            if category == "badge"
            and self._available_badge_quantity(user_id, item_id) >= 2
            and (badge := self._badge_by_shop_id(item_id)[1])
            and badge.get("price_sc", 0) > 0
        ]

    def _pick_craft_result(self, item_id):
        """Разыгрывает исход крафта и возвращает (ID, медаль) либо None."""
        badge_id, badge = self._badge_by_shop_id(item_id)
        rarity = badge.get("rarity") if badge else None
        if not badge_id or badge.get("price_sc", 0) <= 0:
            return None
        if rarity not in CRAFT_CHANCES:
            return None

        chances = dict(CRAFT_CHANCES[rarity])
        roll = random.random()
        if roll < chances["up"]:
            target_rarity = get_next_rarity(rarity)
            candidates = [
                (candidate_id, candidate)
                for candidate_id, candidate in BADGES.items()
                if candidate_id != badge_id
                and candidate.get("rarity") == target_rarity
                and candidate.get("price_sc", 0) > 0
            ]
            if not candidates:
                candidates = [
                    (candidate_id, candidate)
                    for candidate_id, candidate in BADGES.items()
                    if candidate_id != badge_id
                    and candidate.get("rarity") == rarity
                    and candidate.get("price_sc", 0) > 0
                ]
        elif roll < chances["up"] + chances["same"]:
            candidates = [
                (candidate_id, candidate)
                for candidate_id, candidate in BADGES.items()
                if candidate_id != badge_id
                and candidate.get("rarity") == rarity
                and candidate.get("price_sc", 0) > 0
            ]
        else:
            return None

        return random.choice(candidates) if candidates else None

    # ---------- ГЛАВНЫЙ ЭКРАН ----------

    async def cb_inv(self, query: CallbackQuery):
        user_id = query.from_user.id
        user = self.brain.db.get_user(user_id)

        try:
            from item_system import get_total_effects
            effects = get_total_effects(self.brain, user_id)
        except Exception:
            effects = {}
        effects_line = describe_effect_dict(effects)

        body = (
            "🎒 <b>Инвентарь</b>\n\n"
            f"✨ <b>Активные эффекты:</b>\n<i>{effects_line}</i>\n\n"
            "Выбери раздел:"
        )
        text = with_hero(body, user)
        sections = []
        if BADGES:
            sections.append(
                [InlineKeyboardButton(text="🎖 Медали", callback_data="inv_badges")]
            )
            sections.append(
                [InlineKeyboardButton(
                    text="💰 Продать значки", callback_data="inv_sell"
                )]
            )
            if CRAFT_ENABLED:
                sections.append(
                    [InlineKeyboardButton(text="⚒ Крафт", callback_data="inv_craft")]
                )
        if TITLES:
            sections.append(
                [InlineKeyboardButton(text="🏷 Титулы", callback_data="inv_titles")]
            )
        sections.extend(nav_footer("inv"))
        kb = InlineKeyboardMarkup(inline_keyboard=sections)
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await safe_answer(query)

    # ---------- ПРОДАЖА И КРАФТ МЕДАЛЕЙ ----------

    async def cb_sell(self, query: CallbackQuery, notice=None):
        try:
            user_id = query.from_user.id
            inventory = [
                row for row in self.brain.db.get_inventory(user_id)
                if row[4] == "badge"
            ]
            available_inventory = []
            for item_id, quantity, name, _, _, soulbound in inventory:
                if soulbound:
                    available_inventory.append(
                        (item_id, quantity, name, True)
                    )
                    continue
                quantity = self._available_badge_quantity(user_id, item_id)
                if quantity > 0:
                    available_inventory.append((item_id, quantity, name, False))
            prefix = f"{notice}\n\n" if notice else ""
            if not available_inventory:
                text = (
                    prefix
                    + "💰 <b>Продажа медалей</b>\n\n"
                    "У тебя нет значков для продажи. Сначала сними надетые."
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="inv")
                ]] + nav_footer())
            else:
                lines = [prefix + "💰 <b>Продажа медалей</b>\n"]
                buttons = []
                for item_id, quantity, name, soulbound in available_inventory:
                    _, badge = self._badge_by_shop_id(item_id)
                    price = badge.get("price_sc", 0) if badge else 0
                    if soulbound:
                        lines.append(
                            f"{html.escape(name)} ×{quantity} "
                            "🔒 не продаётся"
                        )
                    elif price > 0:
                        sale_price = max(1, price // 2)
                        lines.append(
                            f"{html.escape(name)} ×{quantity} "
                            f"({sale_price} SC за штуку)"
                        )
                        buttons.append([InlineKeyboardButton(
                            text=f"Продать {name} ({sale_price} SC)",
                            callback_data=f"inv_sell_{item_id}",
                        )])
                    else:
                        lines.append(
                            f"{html.escape(name)} ×{quantity} "
                            "🔒 не продаётся"
                        )
                buttons.append([InlineKeyboardButton(
                    text="⬅️ Назад", callback_data="inv"
                )])
                buttons.extend(nav_footer())
                text = "\n".join(lines)
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await query.message.edit_text(
                text, reply_markup=keyboard, parse_mode="HTML"
            )
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка экрана продажи медалей: {error}")
            await safe_answer(
                query, "Не удалось открыть продажу медалей.", show_alert=True
            )

    async def cb_sell_item(self, query: CallbackQuery):
        try:
            item_id = int(query.data.removeprefix("inv_sell_"))
            user_id = query.from_user.id
            inventory_item = next(
                (
                    row for row in self.brain.db.get_inventory(user_id)
                    if row[0] == item_id and row[4] == "badge"
                ),
                None,
            )
            if not inventory_item or inventory_item[5]:
                await safe_answer(
                    query, "🔒 Этот значок нельзя продать.", show_alert=True
                )
                return
            _, badge = self._badge_by_shop_id(item_id)
            if not badge or self._available_badge_quantity(user_id, item_id) < 1:
                await safe_answer(query, "Значка нет в инвентаре.", show_alert=True)
                return
            price = badge.get("price_sc", 0)
            if price <= 0:
                await safe_answer(query, "Этот значок нельзя продать.", show_alert=True)
                return

            sale_price = max(1, price // 2)
            text = (
                f"💰 Продать {html.escape(badge['name'])} "
                f"за <b>{sale_price} SC</b>?"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Продать",
                    callback_data=f"inv_sell_confirm_{item_id}",
                )],
                [InlineKeyboardButton(
                    text="❌ Отмена", callback_data="inv_sell"
                )],
            ] + nav_footer())
            await query.message.edit_text(
                text, reply_markup=keyboard, parse_mode="HTML"
            )
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка подтверждения продажи: {error}")
            await safe_answer(query, "Не удалось начать продажу.", show_alert=True)

    async def cb_sell_confirm(self, query: CallbackQuery):
        try:
            item_id = int(query.data.removeprefix("inv_sell_confirm_"))
            user_id = query.from_user.id
            inventory_item = next(
                (
                    row for row in self.brain.db.get_inventory(user_id)
                    if row[0] == item_id and row[4] == "badge"
                ),
                None,
            )
            if not inventory_item or inventory_item[5]:
                await safe_answer(
                    query, "🔒 Этот значок нельзя продать.", show_alert=True
                )
                return
            _, badge = self._badge_by_shop_id(item_id)
            if not badge or self._available_badge_quantity(user_id, item_id) < 1:
                await safe_answer(query, "Значка больше нет в инвентаре.", show_alert=True)
                return
            price = badge.get("price_sc", 0)
            if price <= 0:
                await safe_answer(query, "Этот значок нельзя продать.", show_alert=True)
                return
            sale_price = max(1, price // 2)
            if not self.brain.db.remove_item(user_id, item_id, 1):
                await safe_answer(query, "Не удалось списать значок.", show_alert=True)
                return

            self.brain.db.add_balance(user_id, "sc", sale_price)
            balance = self.brain.db.get_balance(user_id, "sc")
            notice = (
                f"✅ Продано: {html.escape(badge['name'])} "
                f"за {sale_price} SC. Баланс: {balance} SC"
            )
            await self.cb_sell(query, notice=notice)
        except Exception as error:
            print(f"⚠️ Ошибка продажи медали: {error}")
            await safe_answer(query, "Не удалось продать значок.", show_alert=True)

    async def cb_craft(self, query: CallbackQuery, notice=None):
        if not CRAFT_ENABLED:
            return await safe_answer(query, "⚒ Крафт временно отключён.", show_alert=True)

        try:
            craftable = self._get_craftable_items(query.from_user.id)
            prefix = f"{notice}\n\n" if notice else ""
            if not craftable:
                text = (
                    prefix
                    + "⚒ <b>Крафт медалей</b>\n\n"
                    "У тебя нет пар значков для крафта."
                )
                buttons = []
            else:
                lines = [prefix + "⚒ <b>Крафт медалей</b>\n"]
                buttons = []
                for item_id in craftable:
                    _, badge = self._badge_by_shop_id(item_id)
                    rarity = badge["rarity"]
                    chances = dict(CRAFT_CHANCES[rarity])
                    next_rarity = get_next_rarity(rarity)
                    up_icon = RARITY_EMOJI.get(next_rarity, "⚪")
                    same_icon = RARITY_EMOJI.get(rarity, "⚪")
                    lines.append(
                        f"{html.escape(badge['name'])} ×2 → "
                        f"{up_icon} случайный {next_rarity} "
                        f"({int(chances['up'] * 100)}%) / "
                        f"{same_icon} {rarity} "
                        f"({int(chances['same'] * 100)}%) / "
                        f"ничего ({int(chances['nothing'] * 100)}%)"
                    )
                    buttons.append([InlineKeyboardButton(
                        text=f"⚒ Крафтить {badge['name']}",
                        callback_data=f"inv_craft_{item_id}",
                    )])
            buttons.append([InlineKeyboardButton(
                text="⬅️ Назад", callback_data="inv"
            )])
            buttons.extend(nav_footer())
            await query.message.edit_text(
                text if not craftable else "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML",
            )
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка списка крафта: {error}")
            await safe_answer(query, "Не удалось открыть крафт.", show_alert=True)

    async def cb_craft_item(self, query: CallbackQuery):
        try:
            item_id = int(query.data.removeprefix("inv_craft_"))
            user_id = query.from_user.id
            _, badge = self._badge_by_shop_id(item_id)
            if not badge or self._available_badge_quantity(user_id, item_id) < 2:
                await safe_answer(query, "Для крафта нужны две одинаковые медали.", show_alert=True)
                return
            if badge.get("price_sc", 0) <= 0:
                await safe_answer(query, "Эту медаль нельзя использовать для крафта.", show_alert=True)
                return
            if badge.get("rarity") not in CRAFT_CHANCES:
                await safe_answer(query, "Эта редкость пока не участвует в крафте.", show_alert=True)
                return

            chances = dict(CRAFT_CHANCES[badge["rarity"]])
            text = (
                f"⚒ Скрафтить 2 × {html.escape(badge['name'])}?\n\n"
                f"Шансы: {int(chances['up'] * 100)}% "
                f"{RARITY_EMOJI.get(get_next_rarity(badge['rarity']), '⚪')} "
                f"{get_next_rarity(badge['rarity'])} / "
                f"{int(chances['same'] * 100)}% "
                f"{RARITY_EMOJI.get(badge['rarity'], '⚪')} "
                f"{badge['rarity']} / "
                f"{int(chances['nothing'] * 100)}% ничего"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="⚒ Крафтить",
                    callback_data=f"inv_craft_confirm_{item_id}",
                )],
                [InlineKeyboardButton(
                    text="❌ Отмена", callback_data="inv_craft"
                )],
            ] + nav_footer())
            await query.message.edit_text(
                text, reply_markup=keyboard, parse_mode="HTML"
            )
            await safe_answer(query)
        except Exception as error:
            print(f"⚠️ Ошибка подтверждения крафта: {error}")
            await safe_answer(query, "Не удалось начать крафт.", show_alert=True)

    async def cb_craft_confirm(self, query: CallbackQuery):
        try:
            item_id = int(query.data.removeprefix("inv_craft_confirm_"))
            user_id = query.from_user.id
            badge_id, badge = self._badge_by_shop_id(item_id)
            if not badge_id or self._available_badge_quantity(user_id, item_id) < 2:
                await safe_answer(query, "Для крафта нужны две одинаковые медали.", show_alert=True)
                return
            if badge.get("price_sc", 0) <= 0:
                await safe_answer(query, "Эту медаль нельзя использовать для крафта.", show_alert=True)
                return
            if badge.get("rarity") not in CRAFT_CHANCES:
                await safe_answer(query, "Эта редкость пока не участвует в крафте.", show_alert=True)
                return
            if not self.brain.db.remove_item(user_id, item_id, 2):
                await safe_answer(query, "Не удалось списать две медали.", show_alert=True)
                return

            result = self._pick_craft_result(item_id)
            if result:
                _, result_badge = result
                self.brain.db.add_item(user_id, result_badge["shop_id"], 1)
                notice = (
                    f"✨ Крафт удался! Получен "
                    f"{html.escape(result_badge['name'])}"
                )
            else:
                notice = "💨 Крафт не удался. Значки сгорели."
            await self.cb_craft(query, notice=notice)
        except Exception as error:
            print(f"⚠️ Ошибка крафта медалей: {error}")
            await safe_answer(query, "Не удалось выполнить крафт.", show_alert=True)

    # ---------- МЕДАЛИ ----------

    async def cb_badges(self, query: CallbackQuery):
        user_id = query.from_user.id
        u, room_level = self._ctx(user_id)
        level = u["level"]

        if level < 5:
            text = (
                "🎖 <b>Медали</b>\n\n"
                "🔒 Доступно с <b>5 уровня</b>.\n"
                f"Твой уровень: <b>{level}</b>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="inv")],
            ] + nav_footer())
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
            return await query.answer()

        total = badge_slots_for_level(level)
        equipped = self.brain.db.get_user_badges_full(user_id)
        owned = self._owned_badges(u, room_level)

        lines = [
            "🎖 <b>Медали</b>\n",
            f"⭐ Уровень: <b>{level}</b>  •  Ячеек: <b>{total}/5</b>",
            f"🎖 Открыто: <b>{len(owned)}/{len(BADGES)}</b>\n",
        ]
        for slot in range(total):
            info = equipped.get(slot)
            if info:
                bid = info["badge_id"]
                hp = info["hp"]
                badge = BADGES.get(bid)
                if badge:
                    hp_str = "∞" if hp == -1 else str(hp)
                    eff = self._describe_badge_effect(badge, user_id)
                    lines.append(f"{slot + 1}. {badge['name']} (HP: {hp_str})")
                    lines.append(f"     └ <i>{eff}</i>")
                else:
                    lines.append(f"{slot + 1}. <i>неизвестная медаль</i>")
            else:
                lines.append(f"{slot + 1}. <i>пусто</i>")

        unlock_lvl = SLOT_UNLOCK_LEVELS
        buttons = []
        for slot in range(5):
            if slot >= total:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 Ячейка {slot + 1} (с {unlock_lvl[slot]} ур.)",
                    callback_data="locked"
                )])
                continue
            info = equipped.get(slot)
            if info:
                badge = BADGES.get(info["badge_id"])
                label = f"{slot + 1}. {badge['name']}" if badge else f"Ячейка {slot + 1}"
            else:
                label = f"➕ Ячейка {slot + 1}"
            buttons.append([InlineKeyboardButton(
                text=label, callback_data=f"inv_slot_{slot}"
            )])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="inv")])
        buttons.extend(nav_footer())

        try:
            await query.message.edit_text(
                "\n".join(lines) + "\n\nВыбери ячейку:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except Exception:
            pass
        await query.answer()

    async def cb_slot(self, query: CallbackQuery):
        try:
            slot = int(query.data.replace("inv_slot_", ""))
            user_id = query.from_user.id
            u, room_level = self._ctx(user_id)
            if slot < 0 or slot >= badge_slots_for_level(u["level"]):
                await safe_answer(query, "Ячейка заблокирована", show_alert=True)
                return

            owned = self._owned_badges(u, room_level)
            equipped = self.brain.db.get_user_badges_full(user_id)
            if not owned:
                await safe_answer(query, "Нет доступных медалей", show_alert=True)
                return

            buttons = []
            current_bid = equipped.get(slot, {}).get("badge_id")
            for bid in owned:
                badge = BADGES[bid]
                rarity = RARITY_EMOJI.get(badge["rarity"], "⚪")
                hp = badge.get("hp", "inf")
                hp_str = "∞" if hp == "inf" else str(hp)
                other_slots = [
                    other_slot
                    for other_slot, info in equipped.items()
                    if other_slot != slot and info["badge_id"] == bid
                ]
                if other_slots:
                    other_slot = min(other_slots)
                    label = f"🔒 {badge['name']} [слот {other_slot + 1}]"
                elif current_bid == bid:
                    label = f"✅ {badge['name']} [слот {slot + 1}]"
                else:
                    label = f"{rarity} {badge['name']} [{hp_str}]"
                buttons.append([InlineKeyboardButton(
                    text=label,
                    callback_data=f"inv_badge_pick_{slot}_{bid}"
                )])

            if current_bid:
                buttons.append([InlineKeyboardButton(
                    text="❌ Снять медаль",
                    callback_data=f"inv_badge_remove_{slot}"
                )])
            buttons.append([InlineKeyboardButton(
                text="⬅️ Назад", callback_data="inv_badges"
            )])
            buttons.extend(nav_footer())

            info_text = f"🏅 <b>Ячейка {slot + 1}</b>\n\n"
            if current_bid and current_bid in BADGES:
                badge = BADGES[current_bid]
                effect = self._describe_badge_effect(badge, user_id)
                info_text += (
                    f"Сейчас: <b>{badge['name']}</b>\n"
                    f"<i>{badge.get('desc', '')}</i>\n"
                    f"Эффект: <i>{effect}</i>\n\n"
                )
            info_text += f"Доступно значков: <b>{len(owned)}</b>\n"
            info_text += "<i>Нажми, чтобы надеть. HP = сколько спинов проживёт.</i>"
            await query.message.edit_text(
                info_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML",
            )
            await safe_answer(query)
        except ValueError:
            await safe_answer(query, "Ошибка", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка открытия ячейки медали: {error}")
            await safe_answer(query, "Не удалось открыть ячейку.", show_alert=True)

    async def cb_badge_pick(self, query: CallbackQuery):
        try:
            # inv_badge_pick_{slot}_{badge_id}
            parts = query.data.split("_", 4)
            if len(parts) != 5:
                await safe_answer(query, "Ошибка", show_alert=True)
                return
            slot = int(parts[3])
            bid = parts[4]
            user_id = query.from_user.id
            if slot < 0 or slot >= 5:
                await safe_answer(query, "Ячейка не найдена.", show_alert=True)
                return
            if bid not in BADGES:
                await safe_answer(query, "Значок не найден", show_alert=True)
                return
            u, room_level = self._ctx(user_id)
            if bid not in self._owned_badges(u, room_level):
                await safe_answer(query, "Значок ещё не открыт", show_alert=True)
                return

            if self.brain.db.is_badge_equipped_elsewhere(user_id, slot, bid):
                equipped = self.brain.db.get_user_badges_full(user_id)
                other_slot = next(
                    current_slot
                    for current_slot, info in equipped.items()
                    if current_slot != slot and info["badge_id"] == bid
                )
                await safe_answer(
                    query,
                    f"❌ Уже надето в слоте {other_slot + 1}",
                    show_alert=True,
                )
                return

            self.brain.db.set_user_badge(user_id, slot, bid)
            self.brain.db.log_event(
                user_id, u["username"] or "", "equip_badge", f"{bid}|{slot}"
            )
            await safe_answer(query, f"✅ Надето: {BADGES[bid]['name']}")
            query.data = f"inv_slot_{slot}"
            await self.cb_slot(query)
        except ValueError:
            await safe_answer(query, "Ошибка", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка надевания медали: {error}")
            await safe_answer(query, "Не удалось надеть значок.", show_alert=True)

    async def cb_badge_remove(self, query: CallbackQuery):
        try:
            slot = int(query.data.replace("inv_badge_remove_", ""))
            if slot < 0 or slot >= 5:
                return await safe_answer(query, "Ячейка не найдена.", show_alert=True)

            user_id = query.from_user.id
            equipped = self.brain.db.get_user_badges_full(user_id)
            info = equipped.get(slot)
            if not info:
                return await safe_answer(query, "Слот пуст.", show_alert=True)

            badge_id = info["badge_id"]
            badge = BADGES.get(badge_id)
            if badge and badge.get("shop_id"):
                shop_id = badge["shop_id"]
                if self.brain.db.has_item(user_id, shop_id) < 1:
                    self.brain.db.add_item(user_id, shop_id, 1)
                self.brain.db.remove_user_badge(user_id, slot)
                await safe_answer(query, f"Снято: {badge['name']}")
            else:
                self.brain.db.remove_user_badge(user_id, slot)
                await safe_answer(query, "Снято.")

            query.data = f"inv_slot_{slot}"
            await self.cb_slot(query)
        except ValueError:
            await safe_answer(query, "Ошибка", show_alert=True)
        except Exception as error:
            print(f"⚠️ Ошибка снятия медали: {error}")
            await safe_answer(query, "Не удалось снять медаль.", show_alert=True)

    # ---------- ТИТУЛЫ ----------

    async def cb_titles(self, query: CallbackQuery):
        user_id = query.from_user.id
        u = self.brain.db.get_user(user_id)
        level = u["level"]
        current = self.brain.db.get_title(user_id)

        lines = [
            "🏷 <b>Титулы — просто для красоты</b>\n",
            f"Сейчас: <b>{current}</b>\n",
            "<i>Титулы не дают бонусов. Они украшают профиль.</i>\n",
            "🏆 <b>За уровень</b>",
        ]
        buttons = []
        unlocked_level_titles = {
            title[0] for title in level_titles_for(level)
        }
        for key, name, required_level, rarity in LEVEL_TITLES:
            rarity_icon = RARITY_EMOJI.get(rarity, "⚪")
            if key in unlocked_level_titles:
                mark = " ✅" if name == current else ""
                buttons.append([InlineKeyboardButton(
                    text=f"{rarity_icon} {name}{mark}",
                    callback_data=f"inv_title_pick_{name}",
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 {name} (с {required_level} ур.)",
                    callback_data="locked",
                )])

        lines.extend(["", "🛒 <b>Купленные</b>"])
        for title in TITLES.values():
            owned = self.brain.db.has_item(user_id, title["shop_id"]) > 0
            rarity_icon = RARITY_EMOJI.get(title["rarity"], "⚪")
            if owned:
                mark = " ✅" if title["name"] == current else ""
                buttons.append([InlineKeyboardButton(
                    text=f"{rarity_icon} {title['name']}{mark}",
                    callback_data=f"inv_title_pick_{title['name']}",
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 {title['name']}",
                    callback_data="locked",
                )])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="inv")])
        buttons.extend(nav_footer())

        try:
            await query.message.edit_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except Exception:
            pass
        await query.answer()

    async def cb_title_pick(self, query: CallbackQuery):
        name = query.data.removeprefix("inv_title_pick_")
        user_id = query.from_user.id
        level_title = next(
            (title for title in LEVEL_TITLES if title[1] == name),
            None,
        )
        if level_title:
            level = self.brain.db.get_user(user_id)["level"]
            if level < level_title[2]:
                return await safe_answer(
                    query,
                    f"🔒 Нужен уровень {level_title[2]}",
                    show_alert=True,
                )
        else:
            purchased_title = next(
                (title for title in TITLES.values() if title["name"] == name),
                None,
            )
            if purchased_title is None:
                return await safe_answer(
                    query, "Титул не найден", show_alert=True
                )
            if self.brain.db.has_item(
                user_id, purchased_title["shop_id"]
            ) <= 0:
                return await safe_answer(
                    query,
                    "🔒 Титул ещё не куплен",
                    show_alert=True,
                )

        self.brain.db.set_title(user_id, name)
        await safe_answer(query, f"✅ Титул: {name}")
        await self.cb_titles(query)