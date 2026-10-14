import sqlite3
import random
import time


class DB:
    ROOMS = {
        # Окупаемость указана как cost / доход зала, без бонуса сотрудников.
        1:  {"name": "🎰 Слот-зал",       "income": 30,     "cost": 0,        "req": 0,   "desc": "Классические автоматы"},  # Бесплатный старт
        2:  {"name": "🃏 Покерный зал",   "income": 75,     "cost": 1000,     "req": 3,   "desc": "Столы для покера"},  # Окупаемость: 13,3 ч
        3:  {"name": "🎡 Рулетка",        "income": 190,    "cost": 2500,     "req": 8,   "desc": "Колесо фортуны"},  # Окупаемость: 13,2 ч
        4:  {"name": "🍸 Бар",            "income": 450,    "cost": 6000,     "req": 15,  "desc": "Напитки и закуски"},  # Окупаемость: 13,3 ч
        5:  {"name": "🎲 VIP-зал",        "income": 1150,   "cost": 15000,    "req": 25,  "desc": "Для крупных игроков"},  # Окупаемость: 13,0 ч
        6:  {"name": "🏨 Отель",          "income": 3000,   "cost": 40000,    "req": 35,  "desc": "Гости казино"},  # Окупаемость: 13,3 ч
        7:  {"name": "🎭 Шоу-программа",  "income": 7500,   "cost": 100000,   "req": 50,  "desc": "Развлечения каждый вечер"},  # Окупаемость: 13,3 ч
        8:  {"name": "🌐 Онлайн-казино",  "income": 19000,  "cost": 250000,   "req": 65,  "desc": "Игроки со всего мира"},  # Окупаемость: 13,2 ч
        9:  {"name": "🚁 VIP-вертолётка", "income": 46000,  "cost": 600000,   "req": 80,  "desc": "Только для элиты"},  # Окупаемость: 13,0 ч
        10: {"name": "👑 Империя",        "income": 120000, "cost": 1500000,  "req": 100, "desc": "Легендарный бизнес"},  # Окупаемость: 12,5 ч
    }

    STAFF = {
        # Окупаемость бонусных сотрудников зависит от текущего дохода всех залов.
        1: {"name": "🎩 Крупье",   "bonus": 0.08, "cost": 500,    "desc": "+8% к доходу"},  # Около 63–104 ч при доходе 60–100 LC/ч
        2: {"name": "🍺 Бармен",   "bonus": 0.12, "cost": 3000,   "desc": "+12% к доходу"},  # Около 60–85 ч при доходе 300–400 LC/ч
        3: {"name": "💪 Охрана",   "bonus": 0.00, "cost": 15000,  "desc": "Защита от ограблений"},
        4: {"name": "📊 Менеджер", "bonus": 0.20, "cost": 60000,  "desc": "+20% к доходу"},  # Около 50–75 ч при доходе 4000–6000 LC/ч
        5: {"name": "📣 Пиарщик",  "bonus": 0.35, "cost": 250000, "desc": "+35% к доходу"},  # Около 35–70 ч при доходе 10000–20000 LC/ч
        6: {"name": "🔮 Гадалка",   "bonus": 0.00, "cost": 50000,  "desc": "На 25% уменьшает прирост перегрева за спин"},
        7: {"name": "💼 Бухгалтер", "bonus": 0.00, "cost": 150000, "desc": "Автоматически собирает доход раз в 9 часов (накопление ограничено 8 часами)"},
        8: {"name": "🎰 Механик",   "bonus": 0.00, "cost": 200000, "desc": "На 10% повышает вес выпадения 🎲 и 7️⃣ в слотах"},
    }

    CASINO_MAX_HOURS = 8
    CASINO_AUTO_COLLECT_SECONDS = 9 * 3600
    SHOP_REFRESH_SECONDS = 6 * 3600
    SHOP_TOTAL_ITEMS = 3   # значков в одной ротации магазина

    EVENT_COOLDOWN = 3600
    EVENT_CHANCE = 0.5
    EVENT_DURATION = 1800

    # Перегрев
    OVERHEAT_PER_STAGE = 10        # очков на 1 стадию
    OVERHEAT_MAX_STAGE = 5
    OVERHEAT_COOL_PER_2MIN = 5    # -1 стадия за 2 минуты простоя

    def __init__(self):
        import os
        os.makedirs("data", exist_ok=True)
        self.conn = sqlite3.connect("data/casino.db")

        # ============ USERS ============
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                sc INTEGER DEFAULT 0,
                lc INTEGER DEFAULT 15,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                games INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0,
                last_free_lc INTEGER DEFAULT 0,
                tickets INTEGER DEFAULT 0,
                layout TEXT DEFAULT 'classic',
                title TEXT DEFAULT '',
                streak INTEGER DEFAULT 0,
                max_streak INTEGER DEFAULT 0,
                total_bets INTEGER DEFAULT 0,
                total_won INTEGER DEFAULT 0,
                total_lost INTEGER DEFAULT 0,
                overheat_score INTEGER DEFAULT 0,
                last_spin_ts INTEGER DEFAULT 0
            )
        """)

        # ============ ITEMS ============
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                item_id INTEGER PRIMARY KEY,
                name TEXT,
                price_sc INTEGER,
                rarity TEXT,
                category TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER,
                item_id INTEGER,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, item_id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_luck_items (
                instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                uses_left INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_luck_item_per_user
            ON user_luck_items (user_id) WHERE active=1
        """)

        # ============ SHOP ============
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                next_refresh INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("INSERT OR IGNORE INTO shop_meta (id, next_refresh) VALUES (1, 0)")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_stock (
                item_id INTEGER PRIMARY KEY
            )
        """)

        # ============ CASINO ============
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS casinos (
                user_id INTEGER PRIMARY KEY,
                name TEXT DEFAULT 'Моё казино',
                last_collect INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                pending_event TEXT DEFAULT NULL,
                event_expires INTEGER DEFAULT 0,
                last_event INTEGER DEFAULT 0,
                last_storage_notify INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS casino_rooms (
                user_id INTEGER,
                room_id INTEGER,
                opened_at INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, room_id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS casino_staff (
                user_id INTEGER,
                staff_id INTEGER,
                hired_at INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, staff_id)
            )
        """)

        # ============ MAINTENANCE ============
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER DEFAULT 0,
                reason TEXT DEFAULT '',
                started_at INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("INSERT OR IGNORE INTO maintenance (id, enabled) VALUES (1, 0)")

        # ============ ЗНАЧКИ ============
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                user_id  INTEGER,
                slot     INTEGER,
                badge_id TEXT,
                hp       INTEGER DEFAULT -1,
                roll_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, slot)
            )
        """)

        # ============ АДМИНЫ ============
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id   INTEGER PRIMARY KEY,
                added_by  INTEGER DEFAULT 0,
                added_at  INTEGER DEFAULT 0
            )
        """)

        # ============ ЛОГ АДМИН-КОМАНД ============
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id  INTEGER,
                command   TEXT,
                args      TEXT,
                timestamp INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                username   TEXT,
                text       TEXT NOT NULL,
                status     TEXT DEFAULT 'new',
                admin_id   INTEGER DEFAULT 0,
                answer     TEXT DEFAULT '',
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
        """)

        self._migrate()
        self._init_items()
        self.conn.commit()

    # ================= MIGRATE =================

    def _migrate(self):
        cur = self.conn.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cur.fetchall()}
        needed_users = {
            "username":        "TEXT",
            "sc":              "INTEGER DEFAULT 0",
            "lc":              "INTEGER DEFAULT 15",
            "wins":            "INTEGER DEFAULT 0",
            "losses":          "INTEGER DEFAULT 0",
            "games":           "INTEGER DEFAULT 0",
            "level":           "INTEGER DEFAULT 0",
            "xp":              "INTEGER DEFAULT 0",
            "last_free_lc":    "INTEGER DEFAULT 0",
            "tickets":         "INTEGER DEFAULT 0",
            "layout":          "TEXT DEFAULT 'classic'",
            "title":           "TEXT DEFAULT ''",
            "streak":          "INTEGER DEFAULT 0",
            "max_streak":      "INTEGER DEFAULT 0",
            "total_bets":      "INTEGER DEFAULT 0",
            "total_won":       "INTEGER DEFAULT 0",
            "total_lost":      "INTEGER DEFAULT 0",
            "overheat_score":  "INTEGER DEFAULT 0",
            "last_spin_ts":    "INTEGER DEFAULT 0",
        }
        for col, definition in needed_users.items():
            if col not in existing_cols:
                self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")

        cur = self.conn.execute("PRAGMA table_info(casinos)")
        casino_cols = {row[1] for row in cur.fetchall()}
        needed_casino = {
            "pending_event":       "TEXT DEFAULT NULL",
            "event_expires":       "INTEGER DEFAULT 0",
            "last_event":          "INTEGER DEFAULT 0",
            "total_earned":        "INTEGER DEFAULT 0",
            "last_storage_notify": "INTEGER DEFAULT 0",
        }
        for col, definition in needed_casino.items():
            if col not in casino_cols:
                self.conn.execute(f"ALTER TABLE casinos ADD COLUMN {col} {definition}")

        cur = self.conn.execute("PRAGMA table_info(user_badges)")
        badge_cols = {row[1] for row in cur.fetchall()}
        if "hp" not in badge_cols:
            self.conn.execute("ALTER TABLE user_badges ADD COLUMN hp INTEGER DEFAULT -1")
        if "roll_count" not in badge_cols:
            self.conn.execute(
                "ALTER TABLE user_badges ADD COLUMN roll_count INTEGER DEFAULT 0"
            )

    # ================= INIT ITEMS =================

    def _init_items(self):
        test_items = [
            (1, "🍀 Клевер"),
            (2, "💎 Бриллиант"),
            (3, "🔥 Огненный"),
            (4, "👑 Королевский"),
            (5, "🐋 Кит"),
            (6, "🎩 Лорд"),
            (10, "⭐ Звёздочка"),
            (11, "🌟 Суперзвезда"),
            (12, "🌌 Галактика"),
            (13, "🎲 Кубик"),
            (14, "🃏 Джокер"),
            (15, "🏆 Трофей"),
        ]

        for item_id, name in test_items:
            self.conn.execute(
                "DELETE FROM shop_stock WHERE item_id=? "
                "AND EXISTS (SELECT 1 FROM items WHERE item_id=? AND name=?)",
                (item_id, item_id, name)
            )
            self.conn.execute(
                "DELETE FROM items WHERE item_id=? AND name=?",
                (item_id, name)
            )

        from cosmetics import ITEMS, BADGES, TITLES
        legacy_badge_destinations = {
            "☘️ Трёхлистный клевер": ITEMS["three_leaf_clover"]["shop_id"],
            "🍀 Четырёхлистный клевер": ITEMS["four_leaf_clover"]["shop_id"],
            "🎲 D6 (целый)": ITEMS["d6_full"]["shop_id"],
            "🔥 Огненный шар": ITEMS["fireball"]["shop_id"],
            "⛽ Канистра с бензином": ITEMS["fuel_canister"]["shop_id"],
        }
        old_badge_rows = self.conn.execute(
            "SELECT item_id, name FROM items WHERE category='badge'"
        ).fetchall()
        badge_id_migrations = {
            old_id: legacy_badge_destinations[name]
            for old_id, name in old_badge_rows
            if name in legacy_badge_destinations
            and old_id != legacy_badge_destinations[name]
        }
        if badge_id_migrations:
            old_ids = tuple(badge_id_migrations)
            placeholders = ",".join("?" for _ in old_ids)
            inventory_rows = self.conn.execute(
                f"SELECT user_id, item_id, quantity FROM inventory "
                f"WHERE item_id IN ({placeholders})",
                old_ids,
            ).fetchall()
            self.conn.execute(
                f"DELETE FROM inventory WHERE item_id IN ({placeholders})",
                old_ids,
            )
            for user_id, old_id, quantity in inventory_rows:
                new_id = badge_id_migrations[old_id]
                self.conn.execute(
                    "INSERT INTO inventory (user_id, item_id, quantity) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(user_id, item_id) DO UPDATE SET "
                    "quantity=inventory.quantity + excluded.quantity",
                    (user_id, new_id, quantity),
                )
            for instance_id, old_id in self.conn.execute(
                f"SELECT instance_id, item_id FROM user_luck_items "
                f"WHERE item_id IN ({placeholders})",
                old_ids,
            ).fetchall():
                self.conn.execute(
                    "UPDATE user_luck_items SET item_id=? WHERE instance_id=?",
                    (badge_id_migrations[old_id], instance_id),
                )

        self.conn.execute(
            "UPDATE user_badges SET badge_id='fuel_canister' "
            "WHERE badge_id='gasoline_canister'"
        )

        for item in ITEMS.values():
            self.conn.execute(
                "INSERT INTO items (item_id, name, price_sc, rarity, category) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(item_id) DO UPDATE SET "
                "name=excluded.name, price_sc=excluded.price_sc, "
                "rarity=excluded.rarity, category=excluded.category",
                (
                    item["shop_id"], item["name"], item.get("price_sc", 0),
                    item["rarity"], "badge"
                )
            )

        current_badge_ids = set(BADGES)
        current_cosmetic_item_ids = {
            item["shop_id"] for item in ITEMS.values()
        } | {
            cosmetic["shop_id"]
            for cosmetic in TITLES.values()
            if isinstance(cosmetic.get("shop_id"), int)
        }
        if not TITLES:
            self.conn.execute("UPDATE users SET title=''")
        old_cosmetic_rows = self.conn.execute(
            "SELECT item_id FROM items"
        ).fetchall()
        removed_cosmetic_ids = [
            row[0] for row in old_cosmetic_rows
            if row[0] not in current_cosmetic_item_ids
        ]
        if removed_cosmetic_ids:
            placeholders = ",".join("?" for _ in removed_cosmetic_ids)
            self.conn.execute(
                f"DELETE FROM inventory WHERE item_id IN ({placeholders})",
                removed_cosmetic_ids
            )
            self.conn.execute(
                f"DELETE FROM items WHERE item_id IN ({placeholders})",
                removed_cosmetic_ids
            )
        for (badge_id,) in self.conn.execute(
            "SELECT DISTINCT badge_id FROM user_badges"
        ).fetchall():
            if badge_id not in current_badge_ids:
                self.conn.execute(
                    "DELETE FROM user_badges WHERE badge_id=?", (badge_id,)
                )
        item_id_placeholders = ",".join("?" for _ in current_cosmetic_item_ids)
        self.conn.execute(
            f"""
            INSERT INTO inventory (user_id, item_id, quantity)
            SELECT user_id, item_id, 1
            FROM user_luck_items
            WHERE item_id IN ({item_id_placeholders})
            GROUP BY user_id, item_id
            ON CONFLICT(user_id, item_id) DO UPDATE SET quantity=MAX(quantity, 1)
            """,
            tuple(current_cosmetic_item_ids)
        )
        self.conn.execute("DELETE FROM user_luck_items")
        for category, cosmetics in (("title", TITLES),):
            for cosmetic in cosmetics.values():
                price = cosmetic.get("price_sc")
                item_id = cosmetic.get("shop_id")
                if not isinstance(price, int) or price <= 0 or not item_id:
                    continue
                self.conn.execute(
                    "INSERT INTO items (item_id, name, price_sc, rarity, category) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(item_id) DO UPDATE SET "
                    "name=excluded.name, price_sc=excluded.price_sc, "
                    "rarity=excluded.rarity, category=excluded.category",
                    (item_id, cosmetic["name"], price, cosmetic["rarity"], category)
                )
        self.conn.execute("DELETE FROM shop_stock")
        self.conn.execute("UPDATE shop_meta SET next_refresh=0 WHERE id=1")
        self.conn.commit()

    @staticmethod
    def _purchasable_cosmetic_ids():
        from cosmetics import BADGES, TITLES

        return {
            cosmetic["shop_id"]
            for cosmetic in (*BADGES.values(), *TITLES.values())
            if isinstance(cosmetic.get("shop_id"), int)
            and cosmetic["shop_id"] > 0
            and isinstance(cosmetic.get("price_sc"), int)
            and cosmetic["price_sc"] > 0
        }

    def _ensure(self, user_id):
        self.conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    # ================= ЮЗЕР =================

    def set_username(self, user_id, username):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        self.conn.commit()

    def get_user_by_username(self, username):
        username = username.lstrip("@").lower()
        cur = self.conn.execute("SELECT user_id FROM users WHERE LOWER(username)=?", (username,))
        row = cur.fetchone()
        return row[0] if row else None

    def get_balance(self, user_id, currency):
        self._ensure(user_id)
        cur = self.conn.execute(f"SELECT {currency} FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone()[0]

    def add_balance(self, user_id, currency, amount):
        self._ensure(user_id)
        self.conn.execute(
            f"UPDATE users SET {currency} = {currency} + ? WHERE user_id=?",
            (amount, user_id)
        )
        self.conn.commit()

    def set_balance(self, user_id, currency, amount):
        self._ensure(user_id)
        self.conn.execute(f"UPDATE users SET {currency} = ? WHERE user_id=?", (amount, user_id))
        self.conn.commit()

    def add_result(self, user_id, win):
        self._ensure(user_id)
        col = "wins" if win else "losses"
        self.conn.execute(
            f"UPDATE users SET {col} = {col} + 1, games = games + 1 WHERE user_id=?",
            (user_id,)
        )
        self.conn.commit()

    def get_user(self, user_id):
        self._ensure(user_id)
        cur = self.conn.execute(
            "SELECT username, sc, lc, wins, losses, games, level, xp, layout, title, "
            "streak, max_streak, total_bets, total_won, total_lost, "
            "overheat_score, last_spin_ts "
            "FROM users WHERE user_id=?",
            (user_id,)
        )
        (username, sc, lc, wins, losses, games, level, xp, layout, title,
         streak, max_streak, total_bets, total_won, total_lost,
         overheat_score, last_spin_ts) = cur.fetchone()
        return {
            "username": username, "sc": sc, "lc": lc,
            "wins": wins, "losses": losses, "games": games,
            "level": level, "xp": xp, "layout": layout, "title": title,
            "streak": streak or 0, "max_streak": max_streak or 0,
            "total_bets": total_bets or 0,
            "total_won": total_won or 0,
            "total_lost": total_lost or 0,
            "overheat_score": overheat_score or 0,
            "last_spin_ts": last_spin_ts or 0,
        }

    # ================= УРОВНИ / XP =================

    def get_last_free_lc(self, user_id):
        self._ensure(user_id)
        cur = self.conn.execute("SELECT last_free_lc FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone()[0]

    def set_last_free_lc(self, user_id, timestamp):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET last_free_lc = ? WHERE user_id=?", (timestamp, user_id))
        self.conn.commit()

    def get_tickets(self, user_id) -> int:
        self._ensure(user_id)
        cur = self.conn.execute("SELECT tickets FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone()[0]

    def add_tickets(self, user_id, amount: int):
        """Добавляет билетики, не позволяя превысить лимит хранения."""
        self._ensure(user_id)
        amount = max(0, int(amount))
        if amount == 0:
            return
        self.conn.execute(
            "UPDATE users SET tickets=MIN(10, tickets + ?) WHERE user_id=?",
            (amount, user_id)
        )
        self.conn.commit()

    def spend_ticket(self, user_id) -> bool:
        """Атомарно тратит один билет, если он есть."""
        self._ensure(user_id)
        cur = self.conn.execute(
            "UPDATE users SET tickets=tickets-1 WHERE user_id=? AND tickets>0",
            (user_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_level_xp(self, user_id):
        self._ensure(user_id)
        cur = self.conn.execute("SELECT level, xp FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone()

    def add_xp(self, user_id, amount):
        self._ensure(user_id)
        level, xp = self.get_level_xp(user_id)
        xp += amount
        leveled_up = False
        while xp >= 100 * (level + 1):
            xp -= 100 * (level + 1)
            level += 1
            leveled_up = True
        self.conn.execute("UPDATE users SET xp=?, level=? WHERE user_id=?", (xp, level, user_id))
        self.conn.commit()
        return level, xp, leveled_up

    def set_level(self, user_id, level):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET level=? WHERE user_id=?", (level, user_id))
        self.conn.commit()

    def set_xp(self, user_id, xp):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET xp=? WHERE user_id=?", (xp, user_id))
        self.conn.commit()

    # ================= НАСТРОЙКИ =================

    def get_layout(self, user_id):
        self._ensure(user_id)
        cur = self.conn.execute("SELECT layout FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone()[0] or "classic"

    def set_layout(self, user_id, layout):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET layout=? WHERE user_id=?", (layout, user_id))
        self.conn.commit()

    def get_title(self, user_id):
        self._ensure(user_id)
        cur = self.conn.execute("SELECT title FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone()[0] or ""

    def set_title(self, user_id, title):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET title=? WHERE user_id=?", (title, user_id))
        self.conn.commit()

    # ================= ЛИДЕРБОРД =================

    def top_by(self, field, limit=10):
        allowed = {"sc", "lc", "level", "wins", "games"}
        if field not in allowed:
            field = "sc"
        cur = self.conn.execute(
            f"SELECT username, user_id, {field}, title FROM users ORDER BY {field} DESC LIMIT ?",
            (limit,)
        )
        return cur.fetchall()

    def top_winrate(self, limit=10, min_games=10):
        cur = self.conn.execute(
            "SELECT username, user_id, wins, games, ROUND(wins*100.0/games, 1) AS wr, title "
            "FROM users WHERE games >= ? ORDER BY wr DESC LIMIT ?",
            (min_games, limit)
        )
        return cur.fetchall()

    def get_bot_stats(self):
        cur = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(sc),0), COALESCE(SUM(lc),0), COALESCE(SUM(games),0) "
            "FROM users"
        )
        users, sc, lc, games = cur.fetchone()
        return {"users": users, "sc": sc, "lc": lc, "games": games}

    # ================= МАГАЗИН =================

    def get_all_items(self, category=None):
        if category:
            cur = self.conn.execute(
                "SELECT item_id, name, price_sc, rarity FROM items WHERE category=? ORDER BY price_sc",
                (category,)
            )
        else:
            cur = self.conn.execute(
                "SELECT item_id, name, price_sc, rarity, category FROM items ORDER BY category, price_sc"
            )
        return cur.fetchall()

    def get_item(self, item_id):
        cur = self.conn.execute(
            "SELECT item_id, name, price_sc, rarity, category FROM items WHERE item_id=?",
            (item_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"item_id": row[0], "name": row[1], "price_sc": row[2], "rarity": row[3], "category": row[4]}

    def has_item(self, user_id, item_id):
        item = self.get_item(item_id)
        if item and item["category"] == "luck_item":
            cur = self.conn.execute(
                "SELECT COUNT(*) FROM user_luck_items WHERE user_id=? AND item_id=?",
                (user_id, item_id)
            )
            return cur.fetchone()[0]
        cur = self.conn.execute(
            "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?",
            (user_id, item_id)
        )
        row = cur.fetchone()
        return row[0] if row else 0

    def add_item(self, user_id, item_id, qty=1):
        self.conn.execute(
            "INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + ?",
            (user_id, item_id, qty, qty)
        )
        self.conn.commit()

    def remove_item(self, user_id, item_id, qty=1):
        cur = self.conn.execute(
            "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?",
            (user_id, item_id)
        )
        row = cur.fetchone()
        if not row or row[0] < qty:
            return False
        new_qty = row[0] - qty
        if new_qty <= 0:
            self.conn.execute("DELETE FROM inventory WHERE user_id=? AND item_id=?", (user_id, item_id))
        else:
            self.conn.execute(
                "UPDATE inventory SET quantity=? WHERE user_id=? AND item_id=?",
                (new_qty, user_id, item_id)
            )
        self.conn.commit()
        return True

    def get_inventory(self, user_id):
        cur = self.conn.execute(
            "SELECT items.item_id, inventory.quantity, items.name, items.rarity, items.category "
            "FROM inventory JOIN items ON inventory.item_id = items.item_id "
            "WHERE inventory.user_id=? ORDER BY items.category, items.price_sc DESC",
            (user_id,)
        )
        return cur.fetchall()

    def buy_item(self, user_id, item_id):
        cur = self.conn.execute(
            "SELECT 1 FROM shop_stock WHERE item_id=?", (item_id,)
        )
        if not cur.fetchone():
            return False, "❌ Этого товара сейчас нет в магазине"
        item = self.get_item(item_id)
        if not item:
            return False, "❌ Предмет не найден"
        sc = self.get_balance(user_id, "sc")
        if sc < item["price_sc"]:
            return False, f"❌ Нужно {item['price_sc']} SC, у тебя {sc}"

        if self.has_item(user_id, item_id) > 0:
            return False, "❌ У тебя уже есть этот предмет"
        self.add_balance(user_id, "sc", -item["price_sc"])
        self.add_item(user_id, item_id, 1)
        if item["category"] == "title":
            self.set_title(user_id, item["name"])
        return True, f"✅ Куплено: {item['name']} за {item['price_sc']} SC"

    def get_luck_items(self, user_id):
        cur = self.conn.execute("""
            SELECT user_luck_items.instance_id, user_luck_items.item_id,
                   items.name, items.rarity, user_luck_items.uses_left,
                   user_luck_items.active
            FROM user_luck_items
            JOIN items ON user_luck_items.item_id = items.item_id
            WHERE user_luck_items.user_id=?
            ORDER BY user_luck_items.instance_id
        """, (user_id,))
        return cur.fetchall()

    def activate_luck_item(self, user_id, instance_id):
        cur = self.conn.execute(
            "SELECT 1 FROM user_luck_items WHERE user_id=? AND instance_id=?",
            (user_id, instance_id)
        )
        if not cur.fetchone():
            return False
        self.conn.execute(
            "UPDATE user_luck_items SET active=0 WHERE user_id=? AND active=1",
            (user_id,)
        )
        self.conn.execute(
            "UPDATE user_luck_items SET active=1 WHERE user_id=? AND instance_id=?",
            (user_id, instance_id)
        )
        self.conn.commit()
        return True

    def deactivate_luck_item(self, user_id):
        self.conn.execute(
            "UPDATE user_luck_items SET active=0 WHERE user_id=? AND active=1",
            (user_id,)
        )
        self.conn.commit()

    def get_active_luck_item(self, user_id):
        cur = self.conn.execute(
            "SELECT item_id FROM user_luck_items WHERE user_id=? AND active=1",
            (user_id,)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def consume_active_luck_item(self, user_id):
        cur = self.conn.execute("""
            SELECT user_luck_items.instance_id, user_luck_items.item_id,
                   user_luck_items.uses_left, items.name
            FROM user_luck_items
            JOIN items ON user_luck_items.item_id = items.item_id
            WHERE user_luck_items.user_id=? AND user_luck_items.active=1
        """, (user_id,))
        row = cur.fetchone()
        if not row or row[2] == -1:
            return None

        instance_id, item_id, uses_left, name = row
        uses_left -= 1
        if uses_left > 0:
            self.conn.execute(
                "UPDATE user_luck_items SET uses_left=? WHERE instance_id=?",
                (uses_left, instance_id)
            )
            self.conn.commit()
            return None

        from item import ITEMS
        definition = next(
            (value for value in ITEMS.values() if value["shop_id"] == item_id),
            None
        )
        after = definition.get("after_break") or {}
        replacement_id = None
        replacement_def = None
        if after.get("type") == "GET_ITEM":
            replacement_key = after.get("item_id")
            replacement_def = ITEMS.get(replacement_key)
            if replacement_def:
                replacement_id = replacement_def["shop_id"]

        self.conn.execute(
            "DELETE FROM user_luck_items WHERE instance_id=?",
            (instance_id,)
        )
        if replacement_id is not None and replacement_def is not None:
            uses = replacement_def.get("hp", 1)
            if uses == "inf":
                uses = -1
            self.conn.execute(
                "INSERT INTO user_luck_items (user_id, item_id, uses_left) VALUES (?, ?, ?)",
                (user_id, replacement_id, uses)
            )
        self.conn.commit()

        if replacement_id is not None and replacement_def is not None:
            replacement_name = replacement_def["name"]
            return f"💔 <b>{name}</b> закончился! Получен <b>{replacement_name}</b>."
        return f"💔 <b>{name}</b> закончился."

    def get_shop_items(self):
        now = int(time.time())
        cur = self.conn.execute("SELECT next_refresh FROM shop_meta WHERE id=1")
        next_refresh = cur.fetchone()[0]
        purchasable_cosmetics = self._purchasable_cosmetic_ids()
        if now >= next_refresh:
            cur = self.conn.execute("SELECT DISTINCT category FROM items")
            categories = [r[0] for r in cur.fetchall()]
            selected = []
            for cat in categories:
                cur = self.conn.execute("SELECT item_id FROM items WHERE category=?", (cat,))
                ids = [r[0] for r in cur.fetchall()]
                if cat == "badge":
                    ids = [
                        item_id for item_id in ids
                        if item_id in purchasable_cosmetics
                    ]
                    selected.extend(random.sample(
                        ids, min(self.SHOP_TOTAL_ITEMS, len(ids))
                    ))
                elif cat == "title":
                    selected.extend(
                        item_id for item_id in ids
                        if item_id in purchasable_cosmetics
                    )
                else:
                    random.shuffle(ids)
                    selected.extend(ids[:self.SHOP_TOTAL_ITEMS])
            self.conn.execute("DELETE FROM shop_stock")
            for iid in selected:
                self.conn.execute("INSERT INTO shop_stock (item_id) VALUES (?)", (iid,))
            self.conn.execute(
                "UPDATE shop_meta SET next_refresh=? WHERE id=1",
                (now + self.SHOP_REFRESH_SECONDS,)
            )
            self.conn.commit()
        cur = self.conn.execute("""
            SELECT items.item_id, items.name, items.price_sc, items.rarity, items.category
            FROM shop_stock
            JOIN items ON shop_stock.item_id = items.item_id
            ORDER BY items.category, items.price_sc
        """)
        rows = [
            row for row in cur.fetchall()
            if row[4] not in ("badge", "title")
            or row[0] in purchasable_cosmetics
        ]
        badge_rows = [row for row in rows if row[4] == "badge"]
        random.shuffle(badge_rows)
        return badge_rows + [row for row in rows if row[4] != "badge"]

    def get_shop_next_refresh(self):
        cur = self.conn.execute("SELECT next_refresh FROM shop_meta WHERE id=1")
        return cur.fetchone()[0]

    # ================= КАЗИНО =================

    def get_casino(self, user_id):
        cur = self.conn.execute(
            "SELECT user_id, name, last_collect, total_earned, "
            "pending_event, event_expires, last_event FROM casinos WHERE user_id=?",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        rooms = self.get_rooms(user_id)
        level = max(rooms) if rooms else 1
        return {
            "user_id": row[0], "name": row[1], "last_collect": row[2],
            "total_earned": row[3],
            "pending_event": row[4], "event_expires": row[5], "last_event": row[6],
            "level": level,
            "rooms": rooms,
        }

    def create_casino(self, user_id):
        now = int(time.time())
        self.conn.execute(
            "INSERT OR IGNORE INTO casinos (user_id, name, last_collect, total_earned, last_event) "
            "VALUES (?, 'Моё казино', ?, 0, ?)",
            (user_id, now, now)
        )
        self.conn.commit()
        self.open_room(user_id, 1)

    def get_rooms(self, user_id):
        cur = self.conn.execute(
            "SELECT room_id FROM casino_rooms WHERE user_id=? ORDER BY room_id", (user_id,)
        )
        return [row[0] for row in cur.fetchall()]

    def open_room(self, user_id, room_id):
        if room_id not in self.ROOMS:
            return False, "❌ Неизвестное помещение"
        if room_id in self.get_rooms(user_id):
            return False, "❌ Помещение уже открыто"
        room = self.ROOMS[room_id]
        cost = room["cost"]
        req = room["req"]
        user_level, _ = self.get_level_xp(user_id)
        if user_level < req:
            return False, f"❌ Нужен юзер-уровень {req}, у тебя {user_level}"
        lc = self.get_balance(user_id, "lc")
        if lc < cost:
            return False, f"❌ Нужно {cost} LC, у тебя {lc}"
        if room_id > 1 and (room_id - 1) not in self.get_rooms(user_id):
            return False, f"❌ Сначала открой зал №{room_id - 1}"
        self.collect_casino(user_id)
        self.add_balance(user_id, "lc", -cost)
        self.conn.execute(
            "INSERT INTO casino_rooms (user_id, room_id, opened_at) VALUES (?, ?, ?)",
            (user_id, room_id, int(time.time()))
        )
        self.conn.commit()
        return True, f"🏗 Открыт {room['name']}!"

    def get_staff(self, user_id):
        cur = self.conn.execute(
            "SELECT staff_id FROM casino_staff WHERE user_id=?", (user_id,)
        )
        return [row[0] for row in cur.fetchall()]

    def hire_staff(self, user_id, staff_id):
        if staff_id not in self.STAFF:
            return False, "❌ Неизвестный сотрудник"
        if staff_id in self.get_staff(user_id):
            return False, "❌ Уже нанят"
        staff = self.STAFF[staff_id]
        lc = self.get_balance(user_id, "lc")
        if lc < staff["cost"]:
            return False, f"❌ Нужно {staff['cost']} LC, у тебя {lc}"
        self.collect_casino(user_id)
        self.add_balance(user_id, "lc", -staff["cost"])
        self.conn.execute(
            "INSERT INTO casino_staff (user_id, staff_id, hired_at) VALUES (?, ?, ?)",
            (user_id, staff_id, int(time.time()))
        )
        self.conn.commit()
        return True, f"👔 Нанят {staff['name']}!"

    def has_guard(self, user_id):
        return 3 in self.get_staff(user_id)

    def auto_collect_casino(self, user_id):
        """Собирает доход каждые 9 часов, если нанят бухгалтер."""
        if 7 not in self.get_staff(user_id):
            return None
        casino = self.get_casino(user_id)
        if not casino:
            return None
        if int(time.time()) - casino["last_collect"] < self.CASINO_AUTO_COLLECT_SECONDS:
            return 0
        return self.collect_casino(user_id)

    def get_income_per_hour(self, user_id):
        rooms = self.get_rooms(user_id)
        base = sum(self.ROOMS[r]["income"] for r in rooms if r in self.ROOMS)
        staff = self.get_staff(user_id)
        bonus = sum(self.STAFF[s]["bonus"] for s in staff if s in self.STAFF)
        return int(base * (1 + bonus))

    def get_income_breakdown(self, user_id):
        rooms = self.get_rooms(user_id)
        staff = self.get_staff(user_id)
        base = sum(self.ROOMS[r]["income"] for r in rooms if r in self.ROOMS)
        bonus_pct = sum(self.STAFF[s]["bonus"] for s in staff if s in self.STAFF)
        bonus_lc = int(base * bonus_pct)
        total = base + bonus_lc
        return {
            "base": base,
            "bonus_pct": bonus_pct,
            "bonus_lc": bonus_lc,
            "total": total,
            "rooms": [self.ROOMS[r] for r in rooms if r in self.ROOMS],
            "staff": [self.STAFF[s] for s in staff if s in self.STAFF],
        }

    def get_pending_income(self, user_id):
        casino = self.get_casino(user_id)
        if not casino:
            return 0, 0, 0
        now = int(time.time())
        elapsed = now - casino["last_collect"]
        capped = min(elapsed, self.CASINO_MAX_HOURS * 3600)
        income = self.get_income_per_hour(user_id)
        pending = int(income * capped / 3600)
        return pending, elapsed, income

    def collect_casino(self, user_id):
        pending, _, _ = self.get_pending_income(user_id)
        if pending <= 0:
            return 0
        self.add_balance(user_id, "lc", pending)
        self.conn.execute(
            "UPDATE casinos SET last_collect=?, total_earned = total_earned + ? WHERE user_id=?",
            (int(time.time()), pending, user_id)
        )
        self.conn.commit()
        return pending

    def rename_casino(self, user_id, name):
        self.conn.execute("UPDATE casinos SET name=? WHERE user_id=?", (name, user_id))
        self.conn.commit()

    # ================= СОБЫТИЯ =================

    def try_trigger_event(self, user_id):
        casino = self.get_casino(user_id)
        if not casino:
            return None
        now = int(time.time())
        if casino["pending_event"] and casino["event_expires"] > now:
            return casino["pending_event"]
        if casino["pending_event"] and casino["event_expires"] <= now:
            self.conn.execute(
                "UPDATE casinos SET pending_event=NULL, event_expires=0 WHERE user_id=?",
                (user_id,)
            )
            self.conn.commit()
        if now - casino["last_event"] < self.EVENT_COOLDOWN:
            return None
        if random.random() > self.EVENT_CHANCE:
            self.conn.execute("UPDATE casinos SET last_event=? WHERE user_id=?", (now, user_id))
            self.conn.commit()
            return None
        event_type = random.choices(
            ["celebrity", "robbery", "big_visitor"],
            weights=[50, 30, 20]
        )[0]
        self.conn.execute(
            "UPDATE casinos SET pending_event=?, event_expires=?, last_event=? WHERE user_id=?",
            (event_type, now + self.EVENT_DURATION, now, user_id)
        )
        self.conn.commit()
        return event_type

    def resolve_event(self, user_id, event_type, action):
        casino = self.get_casino(user_id)
        if not casino or casino["pending_event"] != event_type:
            return False, "❌ Событие уже неактивно"
        result = {"ok": True, "text": "", "amount": 0}
        if event_type == "celebrity":
            income = self.get_income_per_hour(user_id)
            bonus = income * 5
            self.add_balance(user_id, "lc", bonus)
            self.conn.execute(
                "UPDATE casinos SET total_earned = total_earned + ? WHERE user_id=?",
                (bonus, user_id)
            )
            result["text"] = f"🌟 Знаменитость оставила {bonus} LC чаевых!"
            result["amount"] = bonus
        elif event_type == "big_visitor":
            income = self.get_income_per_hour(user_id)
            bonus = income * 10
            self.add_balance(user_id, "lc", bonus)
            self.conn.execute(
                "UPDATE casinos SET total_earned = total_earned + ? WHERE user_id=?",
                (bonus, user_id)
            )
            result["text"] = f"🐋 Крупный игрок проиграл {bonus} LC!"
            result["amount"] = bonus
        elif event_type == "robbery":
            pending, _, _ = self.get_pending_income(user_id)
            steal_pct = 0.20
            if self.has_guard(user_id):
                if random.random() < 0.85:
                    result["text"] = "💪 Охрана отбила ограбление! Ничего не потеряно."
                    result["amount"] = 0
                else:
                    stolen = max(1, int(pending * steal_pct))
                    income = max(1, self.get_income_per_hour(user_id))
                    seconds_lost = int(stolen / income * 3600)
                    self.conn.execute(
                        "UPDATE casinos SET last_collect = last_collect + ? WHERE user_id=?",
                        (seconds_lost, user_id)
                    )
                    result["text"] = f"😨 Воры всё же прорвались! Потеряно ~{stolen} LC."
                    result["amount"] = -stolen
            else:
                if random.random() < 0.30:
                    result["text"] = "🍀 Каким-то чудом отбил ограбление!"
                    result["amount"] = 0
                else:
                    stolen = max(1, int(pending * steal_pct))
                    income = max(1, self.get_income_per_hour(user_id))
                    seconds_lost = int(stolen / income * 3600)
                    self.conn.execute(
                        "UPDATE casinos SET last_collect = last_collect + ? WHERE user_id=?",
                        (seconds_lost, user_id)
                    )
                    result["text"] = (
                        f"🚨 Ограбление! Потеряно ~{stolen} LC.\n"
                        f"_Совет: найми 💪 Охрану, чтобы защититься._"
                    )
                    result["amount"] = -stolen
        self.conn.execute(
            "UPDATE casinos SET pending_event=NULL, event_expires=0 WHERE user_id=?",
            (user_id,)
        )
        self.conn.commit()
        return True, result["text"]

    def clear_event(self, user_id):
        self.conn.execute(
            "UPDATE casinos SET pending_event=NULL, event_expires=0 WHERE user_id=?",
            (user_id,)
        )
        self.conn.commit()

    # ================= ТОП КАЗИНО =================

    def top_casinos(self, limit=10):
        cur = self.conn.execute("""
            SELECT c.user_id, u.username, u.title, c.name, c.total_earned,
                   COALESCE(MAX(r.room_id), 1) as level
            FROM casinos c
            JOIN users u ON c.user_id = u.user_id
            LEFT JOIN casino_rooms r ON c.user_id = r.user_id
            GROUP BY c.user_id
            ORDER BY level DESC, c.total_earned DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()

    def get_casino_rank(self, user_id):
        casino = self.get_casino(user_id)
        if not casino:
            return None
        if casino["level"] <= 1 and casino["total_earned"] <= 0:
            return None
        cur = self.conn.execute("""
            SELECT COUNT(*) + 1 FROM (
                SELECT c.user_id,
                       COALESCE(MAX(r.room_id), 1) as lvl,
                       c.total_earned as earned
                FROM casinos c
                LEFT JOIN casino_rooms r ON c.user_id = r.user_id
                GROUP BY c.user_id
            )
            WHERE lvl > ?
               OR (lvl = ? AND earned > ?)
        """, (casino["level"], casino["level"], casino["total_earned"]))
        return cur.fetchone()[0]

    def count_active_casinos(self):
        cur = self.conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT c.user_id,
                       COALESCE(MAX(r.room_id), 1) as lvl,
                       c.total_earned as earned
                FROM casinos c
                LEFT JOIN casino_rooms r ON c.user_id = r.user_id
                GROUP BY c.user_id
            )
            WHERE lvl > 1 OR earned > 0
        """)
        return cur.fetchone()[0]

    def count_all_casinos(self):
        cur = self.conn.execute("SELECT COUNT(*) FROM casinos")
        return cur.fetchone()[0]

    def get_user_casino_position(self, user_id, limit=10):
        rank = self.get_casino_rank(user_id)
        if rank is None:
            return None, False
        return rank, rank <= limit

    # ================= ТЕХПЕРЕРЫВ =================

    def get_maintenance(self):
        cur = self.conn.execute(
            "SELECT enabled, reason, started_at FROM maintenance WHERE id=1"
        )
        row = cur.fetchone()
        if not row:
            return {"enabled": False, "reason": "", "started_at": 0}
        return {
            "enabled": bool(row[0]),
            "reason": row[1] or "",
            "started_at": row[2] or 0,
        }

    def set_maintenance(self, enabled, reason=""):
        self.conn.execute(
            "UPDATE maintenance SET enabled=?, reason=?, started_at=? WHERE id=1",
            (1 if enabled else 0, reason, int(time.time()) if enabled else 0)
        )
        self.conn.commit()

    # ================= ПУШИ ХРАНИЛИЩА =================

    def get_users_with_casino(self):
        cur = self.conn.execute("SELECT user_id FROM casinos")
        return [row[0] for row in cur.fetchall()]

    def get_all_user_ids(self):
        cur = self.conn.execute("SELECT user_id FROM users")
        return [row[0] for row in cur.fetchall()]

    def get_last_storage_notify(self, user_id):
        cur = self.conn.execute(
            "SELECT last_storage_notify FROM casinos WHERE user_id=?", (user_id,)
        )
        row = cur.fetchone()
        return row[0] if row else 0

    def set_last_storage_notify(self, user_id, ts):
        self.conn.execute(
            "UPDATE casinos SET last_storage_notify=? WHERE user_id=?",
            (ts, user_id)
        )
        self.conn.commit()

    def is_storage_full(self, user_id):
        casino = self.get_casino(user_id)
        if not casino:
            return False
        _, elapsed, _ = self.get_pending_income(user_id)
        return elapsed >= self.CASINO_MAX_HOURS * 3600

    # ================= ЗНАЧКИ =================

    def get_all_owned_badges(self, user_id):
        """Возвращает медали игрока из слотов и инвентаря без повторов."""
        from cosmetics import BADGES

        equipped = self.get_user_badges_full(user_id)
        slot_by_badge = {}
        for slot, info in equipped.items():
            slot_by_badge.setdefault(info["badge_id"], []).append(slot)

        owned = []
        for badge_id, badge in BADGES.items():
            quantity = self.has_item(user_id, badge["shop_id"])
            slots = slot_by_badge.get(badge_id, [])
            if slots or quantity:
                owned.append({
                    "badge_id": badge_id,
                    "name": badge["name"],
                    "slots": slots,
                    "quantity": quantity,
                })
        return owned

    def transfer_badge(self, from_id, to_id, badge_id):
        """Передаёт одну медаль, сохраняя её прочность при переносе из слота."""
        from cosmetics import BADGES, badge_slots_for_level

        badge = BADGES.get(badge_id)
        if not badge:
            return False

        try:
            self.conn.execute("BEGIN IMMEDIATE")
            cur = self.conn.execute(
                "SELECT slot, hp, roll_count FROM user_badges "
                "WHERE user_id=? AND badge_id=? ORDER BY slot LIMIT 1",
                (from_id, badge_id)
            )
            equipped = cur.fetchone()
            if equipped:
                source_slot, hp, roll_count = equipped
                self.conn.execute(
                    "DELETE FROM user_badges WHERE user_id=? AND slot=?",
                    (from_id, source_slot)
                )
            else:
                cur = self.conn.execute(
                    "SELECT quantity FROM inventory WHERE user_id=? AND item_id=?",
                    (from_id, badge["shop_id"])
                )
                inventory_item = cur.fetchone()
                if not inventory_item or inventory_item[0] <= 0:
                    self.conn.rollback()
                    return False
                quantity = inventory_item[0] - 1
                if quantity:
                    self.conn.execute(
                        "UPDATE inventory SET quantity=? WHERE user_id=? AND item_id=?",
                        (quantity, from_id, badge["shop_id"])
                    )
                else:
                    self.conn.execute(
                        "DELETE FROM inventory WHERE user_id=? AND item_id=?",
                        (from_id, badge["shop_id"])
                    )
                hp = badge.get("hp", 1)
                if hp == "inf":
                    hp = -1
                roll_count = 0

            cur = self.conn.execute(
                "SELECT level FROM users WHERE user_id=?", (to_id,)
            )
            row = cur.fetchone()
            level = row[0] if row else 0
            max_slots = badge_slots_for_level(level)
            cur = self.conn.execute(
                "SELECT slot FROM user_badges WHERE user_id=?", (to_id,)
            )
            occupied = {row[0] for row in cur.fetchall()}
            free_slot = next(
                (slot for slot in range(max_slots) if slot not in occupied),
                None,
            )

            if free_slot is not None:
                self.conn.execute(
                    "INSERT INTO user_badges "
                    "(user_id, slot, badge_id, hp, roll_count) VALUES (?, ?, ?, ?, ?)",
                    (to_id, free_slot, badge_id, hp, roll_count)
                )
            else:
                self.conn.execute(
                    "INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, 1) "
                    "ON CONFLICT(user_id, item_id) "
                    "DO UPDATE SET quantity=quantity+1",
                    (to_id, badge["shop_id"])
                )
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def get_user_badges(self, user_id):
        result = {i: None for i in range(5)}
        cur = self.conn.execute(
            "SELECT slot, badge_id FROM user_badges WHERE user_id=?",
            (user_id,)
        )
        for slot, bid in cur.fetchall():
            if 0 <= slot <= 4:
                result[slot] = bid
        return result

    def get_user_badges_full(self, user_id):
        result = {}
        cur = self.conn.execute(
            "SELECT slot, badge_id, hp, roll_count FROM user_badges WHERE user_id=?",
            (user_id,)
        )
        for slot, bid, hp, roll_count in cur.fetchall():
            result[slot] = {
                "badge_id": bid,
                "hp": hp,
                "roll_count": roll_count,
            }
        return result

    def is_badge_equipped_elsewhere(self, user_id, slot, badge_id):
        """Проверяет, надета ли такая же медаль в другом слоте."""
        cur = self.conn.execute(
            "SELECT 1 FROM user_badges "
            "WHERE user_id=? AND badge_id=? AND slot<>? LIMIT 1",
            (user_id, badge_id, slot),
        )
        return cur.fetchone() is not None

    def set_user_badge(self, user_id, slot, badge_id):
        from cosmetics import BADGES
        badge = BADGES.get(badge_id)
        hp = badge.get("hp", 1) if badge else 1
        if hp == "inf":
            hp = -1
        self.conn.execute(
            "INSERT INTO user_badges (user_id, slot, badge_id, hp, roll_count) "
            "VALUES (?, ?, ?, ?, 0) "
            "ON CONFLICT(user_id, slot) DO UPDATE SET "
            "roll_count=CASE WHEN badge_id != excluded.badge_id "
            "THEN 0 ELSE roll_count END, "
            "badge_id=excluded.badge_id, hp=excluded.hp",
            (user_id, slot, badge_id, hp)
        )
        self.conn.commit()

    def increment_badge_rolls(self, user_id):
        self.conn.execute(
            "UPDATE user_badges SET roll_count=roll_count+1 WHERE user_id=?",
            (user_id,)
        )
        self.conn.commit()

    def get_badge_roll_count(self, user_id, slot):
        cur = self.conn.execute(
            "SELECT roll_count FROM user_badges WHERE user_id=? AND slot=?",
            (user_id, slot)
        )
        row = cur.fetchone()
        return row[0] if row else 0

    def reset_badge_roll_count(self, user_id, slot):
        self.conn.execute(
            "UPDATE user_badges SET roll_count=0 WHERE user_id=? AND slot=?",
            (user_id, slot)
        )
        self.conn.commit()

    def set_badge_hp(self, user_id, slot, hp):
        self.conn.execute(
            "UPDATE user_badges SET hp=? WHERE user_id=? AND slot=?",
            (hp, user_id, slot)
        )
        self.conn.commit()

    def remove_user_badge(self, user_id, slot):
        self.conn.execute(
            "DELETE FROM user_badges WHERE user_id=? AND slot=?",
            (user_id, slot)
        )
        self.conn.commit()

    def get_active_effects(self, user_id):
        try:
            from item_system import get_total_effects
            return get_total_effects(self, user_id)
        except Exception:
            return {}

    # ================= СТАТИСТИКА ДЛЯ УСЛОВИЙ =================

    def get_extended_stats(self, user_id):
        import time as _t
        u = self.get_user(user_id)
        rooms = self.get_rooms(user_id) or []
        staff = self.get_staff(user_id) or []
        equipped_badges = self.get_user_badges(user_id)

        winrate = (u["wins"] / u["games"]) if u["games"] > 0 else 0.0

        try:
            from cosmetics import BADGES
            legendary = sum(
                1 for bid in equipped_badges.values()
                if bid and bid in BADGES and BADGES[bid].get("rarity") == "legendary"
            )
        except Exception:
            legendary = 0

        now = _t.localtime()
        oh_score = u.get("overheat_score", 0)
        oh_stage = min(self.OVERHEAT_MAX_STAGE, oh_score // self.OVERHEAT_PER_STAGE)

        return {
            "user_level":         u["level"],
            "user_sc":            u["sc"],
            "user_lc":            u["lc"],
            "user_games":         u["games"],
            "user_wins":          u["wins"],
            "user_losses":        u["losses"],
            "user_xp":            u["xp"],
            "user_streak":        u.get("streak", 0),
            "user_max_streak":    u.get("max_streak", 0),
            "user_winrate":       winrate,
            "user_total_bets":    u.get("total_bets", 0),
            "user_total_won":     u.get("total_won", 0),
            "user_total_lost":    u.get("total_lost", 0),
            "casino_level":       max(rooms) if rooms else 0,
            "casino_rooms":       len(rooms),
            "casino_staff":       len(staff),
            "casino_income":      self.get_income_per_hour(user_id) if rooms else 0,
            "badges_count":       sum(1 for b in equipped_badges.values() if b),
            "badges_legendary":   legendary,
            "hour_of_day":        now.tm_hour,
            "day_of_week":        now.tm_wday,
            # перегрев
            "user_overheat":       oh_score,
            "user_overheat_stage": oh_stage,
        }

    def add_streak_win(self, user_id):
        self._ensure(user_id)
        cur = self.conn.execute("SELECT streak, max_streak FROM users WHERE user_id=?", (user_id,))
        streak, max_streak = cur.fetchone()
        streak = (streak or 0) + 1
        max_streak = max_streak or 0
        if streak > max_streak:
            max_streak = streak
        self.conn.execute("UPDATE users SET streak=?, max_streak=? WHERE user_id=?",
                          (streak, max_streak, user_id))
        self.conn.commit()

    def add_streak_loss(self, user_id):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET streak=0 WHERE user_id=?", (user_id,))
        self.conn.commit()

    def add_bet_stats(self, user_id, bet, win_amount):
        self._ensure(user_id)
        if win_amount > 0:
            self.conn.execute(
                "UPDATE users SET total_bets = total_bets + ?, total_won = total_won + ? WHERE user_id=?",
                (bet, win_amount, user_id)
            )
        else:
            self.conn.execute(
                "UPDATE users SET total_bets = total_bets + ?, total_lost = total_lost + ? WHERE user_id=?",
                (bet, bet, user_id)
            )
        self.conn.commit()

    # ================= ПЕРЕГРЕВ =================

    def get_overheat_stage(self, user_id):
        """Возвращает (stage, score). Остывание -20 за 2 минуты."""
        self._ensure(user_id)
        cur = self.conn.execute(
            "SELECT overheat_score, last_spin_ts FROM users WHERE user_id=?",
            (user_id,)
        )
        score, last = cur.fetchone()
        score = score or 0
        last = last or 0

        now = int(time.time())
        if last > 0 and score > 0:
            minutes_blocks = (now - last) // 120  # блоков по 2 минуты
            if minutes_blocks > 0:
                score = max(0, score - minutes_blocks * self.OVERHEAT_COOL_PER_2MIN)
                self.conn.execute(
                    "UPDATE users SET overheat_score=? WHERE user_id=?",
                    (score, user_id)
                )
                self.conn.commit()

        stage = min(self.OVERHEAT_MAX_STAGE, score // self.OVERHEAT_PER_STAGE)
        return stage, score

    def add_overheat(self, user_id, amount=1, reduction=0):
        """Добавляет очки перегрева за спин, не превышая максимум."""
        self._ensure(user_id)
        reduced_amount = max(0, amount * (1 - min(max(reduction, 0), 1)))
        amount = int(reduced_amount)
        if random.random() < reduced_amount - amount:
            amount += 1
        cur = self.conn.execute(
            "SELECT overheat_score FROM users WHERE user_id=?",
            (user_id,)
        )
        score = (cur.fetchone()[0] or 0) + amount
        cap = self.OVERHEAT_PER_STAGE * self.OVERHEAT_MAX_STAGE
        score = min(score, cap)
        self.conn.execute(
            "UPDATE users SET overheat_score=?, last_spin_ts=? WHERE user_id=?",
            (score, int(time.time()), user_id)
        )
        self.conn.commit()

    def reset_overheat(self, user_id):
        self.conn.execute(
            "UPDATE users SET overheat_score=0 WHERE user_id=?",
            (user_id,)
        )
        self.conn.commit()

    # ================= АДМИНЫ =================

    def add_admin(self, user_id, added_by=0):
        self.conn.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
            (user_id, added_by, int(time.time()))
        )
        self.conn.commit()

    def remove_admin(self, user_id):
        self.conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        self.conn.commit()

    def is_db_admin(self, user_id):
        cur = self.conn.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
        return cur.fetchone() is not None

    def get_db_admins(self):
        cur = self.conn.execute(
            "SELECT user_id, added_by, added_at FROM admins ORDER BY added_at"
        )
        return cur.fetchall()

    # ================= ЛОГ =================

    def log_admin(self, admin_id, command, args=""):
        try:
            self.conn.execute(
                "INSERT INTO admin_log (admin_id, command, args, timestamp) VALUES (?, ?, ?, ?)",
                (admin_id, command, args, int(time.time()))
            )
            self.conn.commit()
        except Exception:
            pass

    def get_admin_log(self, limit=20):
        cur = self.conn.execute(
            "SELECT admin_id, command, args, timestamp FROM admin_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return cur.fetchall()

    def clear_admin_log(self):
        self.conn.execute("DELETE FROM admin_log")
        self.conn.commit()

    # ================= УДАЛЕНИЕ ЮЗЕРА =================

    def delete_user(self, user_id):
        self.conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        self.conn.execute("DELETE FROM user_badges WHERE user_id=?", (user_id,))
        self.conn.execute("DELETE FROM casinos WHERE user_id=?", (user_id,))
        self.conn.execute("DELETE FROM casino_rooms WHERE user_id=?", (user_id,))
        self.conn.execute("DELETE FROM casino_staff WHERE user_id=?", (user_id,))
        self.conn.execute("DELETE FROM inventory WHERE user_id=?", (user_id,))
        self.conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        self.conn.commit()

    def user_exists(self, user_id):
        cur = self.conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone() is not None

    # ================= ЖАЛОБЫ =================

    def add_complaint(self, user_id, username, text):
        """Создаёт жалобу и возвращает её ID."""
        now = int(time.time())
        cur = self.conn.execute(
            "INSERT INTO complaints "
            "(user_id, username, text, status, admin_id, answer, created_at, updated_at) "
            "VALUES (?, ?, ?, 'new', 0, '', ?, ?)",
            (user_id, username, text, now, now)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_user_complaints(self, user_id, limit=3):
        """Возвращает последние жалобы пользователя, новые сверху."""
        limit = max(1, min(50, int(limit)))
        cur = self.conn.execute(
            "SELECT id, text, status, answer, created_at, updated_at "
            "FROM complaints WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        columns = ("id", "text", "status", "answer", "created_at", "updated_at")
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_all_complaints(self, status=None, limit=50):
        """Возвращает жалобы, при необходимости отфильтрованные по статусу."""
        limit = max(1, min(50, int(limit)))
        if status is None:
            cur = self.conn.execute(
                "SELECT id, user_id, username, text, status, admin_id, answer, "
                "created_at, updated_at FROM complaints ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        else:
            cur = self.conn.execute(
                "SELECT id, user_id, username, text, status, admin_id, answer, "
                "created_at, updated_at FROM complaints WHERE status=? "
                "ORDER BY id DESC LIMIT ?",
                (status, limit)
            )
        columns = (
            "id", "user_id", "username", "text", "status", "admin_id",
            "answer", "created_at", "updated_at",
        )
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_complaint(self, complaint_id):
        """Возвращает одну жалобу или None."""
        cur = self.conn.execute(
            "SELECT id, user_id, username, text, status, admin_id, answer, "
            "created_at, updated_at FROM complaints WHERE id=?",
            (complaint_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        columns = (
            "id", "user_id", "username", "text", "status", "admin_id",
            "answer", "created_at", "updated_at",
        )
        return dict(zip(columns, row))

    def update_complaint(self, complaint_id, admin_id, status, answer=None):
        """Обновляет жалобу, сохраняя ответ, если он не передан."""
        now = int(time.time())
        if answer is None:
            cur = self.conn.execute(
                "UPDATE complaints SET status=?, admin_id=?, updated_at=? WHERE id=?",
                (status, admin_id, now, complaint_id)
            )
        else:
            cur = self.conn.execute(
                "UPDATE complaints SET status=?, admin_id=?, answer=?, updated_at=? "
                "WHERE id=?",
                (status, admin_id, answer, now, complaint_id)
            )
        self.conn.commit()
        return cur.rowcount > 0

    def count_unseen_complaints(self):
        """Возвращает число новых, ещё не просмотренных жалоб."""
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE status='new'"
        )
        return cur.fetchone()[0]