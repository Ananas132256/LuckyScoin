import sqlite3
import random
import time


class DB:
    ROOMS = {
        1:  {"name": "🎰 Слот-зал",       "income": 30,     "cost": 0,        "req": 0,  "desc": "Классические автоматы"},
        2:  {"name": "🃏 Покерный зал",   "income": 80,     "cost": 1000,     "req": 1,  "desc": "Столы для покера"},
        3:  {"name": "🎡 Рулетка",        "income": 200,    "cost": 2500,     "req": 3,  "desc": "Колесо фортуны"},
        4:  {"name": "🍸 Бар",            "income": 500,    "cost": 6000,     "req": 5,  "desc": "Напитки и закуски"},
        5:  {"name": "🎲 VIP-зал",        "income": 1200,   "cost": 15000,    "req": 8,  "desc": "Для крупных игроков"},
        6:  {"name": "🏨 Отель",          "income": 3000,   "cost": 40000,    "req": 12, "desc": "Гости казино"},
        7:  {"name": "🎭 Шоу-программа",  "income": 8000,   "cost": 100000,   "req": 16, "desc": "Развлечения каждый вечер"},
        8:  {"name": "🌐 Онлайн-казино",  "income": 20000,  "cost": 250000,   "req": 22, "desc": "Игроки со всего мира"},
        9:  {"name": "🚁 VIP-вертолётка", "income": 50000,  "cost": 600000,   "req": 30, "desc": "Только для элиты"},
        10: {"name": "👑 Империя",        "income": 130000, "cost": 1500000,  "req": 40, "desc": "Легендарный бизнес"},
    }

    STAFF = {
        1: {"name": "🎩 Крупье",   "bonus": 0.10, "cost": 2000,   "desc": "+10% к доходу"},
        2: {"name": "🍺 Бармен",   "bonus": 0.15, "cost": 8000,   "desc": "+15% к доходу"},
        3: {"name": "💪 Охрана",   "bonus": 0.00, "cost": 25000,  "desc": "Защита от ограблений"},
        4: {"name": "📊 Менеджер", "bonus": 0.25, "cost": 100000, "desc": "+25% к доходу"},
        5: {"name": "📣 Пиарщик",  "bonus": 0.50, "cost": 500000, "desc": "+50% к доходу"},
    }

    CASINO_MAX_HOURS = 8
    SHOP_REFRESH_SECONDS = 6 * 3600
    SHOP_PER_CATEGORY = 3

    EVENT_COOLDOWN = 3600
    EVENT_CHANCE = 0.5
    EVENT_DURATION = 1800

    def __init__(self):
        import os
        os.makedirs("data", exist_ok=True)
        self.conn = sqlite3.connect("data/casino.db")
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
                layout TEXT DEFAULT 'classic',
                title TEXT DEFAULT '🎲 Новичок'
            )
        """)
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
            CREATE TABLE IF NOT EXISTS shop_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                next_refresh INTEGER DEFAULT 0
            )
        """)
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
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER DEFAULT 0,
                reason TEXT DEFAULT '',
                started_at INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("INSERT OR IGNORE INTO maintenance (id, enabled) VALUES (1, 0)")
        # ---- ЗНАЧКИ ----
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                user_id  INTEGER,
                slot     INTEGER,
                badge_id TEXT,
                PRIMARY KEY (user_id, slot)
            )
        """)
        self._migrate()
        self._init_items()
        self.conn.commit()

    def _migrate(self):
        cur = self.conn.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cur.fetchall()}
        needed_users = {
            "username":     "TEXT",
            "sc":           "INTEGER DEFAULT 0",
            "lc":           "INTEGER DEFAULT 15",
            "wins":         "INTEGER DEFAULT 0",
            "losses":       "INTEGER DEFAULT 0",
            "games":        "INTEGER DEFAULT 0",
            "level":        "INTEGER DEFAULT 0",
            "xp":           "INTEGER DEFAULT 0",
            "last_free_lc": "INTEGER DEFAULT 0",
            "layout":       "TEXT DEFAULT 'classic'",
            "title":        "TEXT DEFAULT '🎲 Новичок'",
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

    def _init_items(self):
        default_items = [
            (1,  "🍀 Клевер",         50,   "common",    "title"),
            (2,  "💎 Бриллиант",      300,  "rare",      "title"),
            (3,  "🔥 Огненный",       800,  "rare",      "title"),
            (4,  "👑 Королевский",    2000, "epic",      "title"),
            (5,  "🐋 Кит",            5000, "legendary", "title"),
            (6,  "🎩 Лорд",           4000, "legendary", "title"),
            (10, "⭐ Звёздочка",       100,  "common",    "badge"),
            (11, "🌟 Суперзвезда",     500,  "rare",      "badge"),
            (12, "🌌 Галактика",      3000, "epic",      "badge"),
            (13, "🎲 Кубик",           150,  "common",    "badge"),
            (14, "🃏 Джокер",          700,  "rare",      "badge"),
            (15, "🏆 Трофей",          1200, "epic",      "badge"),
        ]
        for item in default_items:
            self.conn.execute(
                "INSERT OR IGNORE INTO items (item_id, name, price_sc, rarity, category) "
                "VALUES (?, ?, ?, ?, ?)",
                item
            )
        self.conn.commit()

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
            "SELECT username, sc, lc, wins, losses, games, level, xp, layout, title "
            "FROM users WHERE user_id=?",
            (user_id,)
        )
        username, sc, lc, wins, losses, games, level, xp, layout, title = cur.fetchone()
        return {
            "username": username, "sc": sc, "lc": lc,
            "wins": wins, "losses": losses, "games": games,
            "level": level, "xp": xp, "layout": layout, "title": title
        }

    # ================= УРОВНИ/XP =================

    def get_last_free_lc(self, user_id):
        self._ensure(user_id)
        cur = self.conn.execute("SELECT last_free_lc FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone()[0]

    def set_last_free_lc(self, user_id, timestamp):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET last_free_lc = ? WHERE user_id=?", (timestamp, user_id))
        self.conn.commit()

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
        return cur.fetchone()[0] or "🎲 Новичок"

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

    def get_shop_items(self):
        now = int(time.time())
        cur = self.conn.execute("SELECT next_refresh FROM shop_meta WHERE id=1")
        next_refresh = cur.fetchone()[0]
        if now >= next_refresh:
            cur = self.conn.execute("SELECT DISTINCT category FROM items")
            categories = [r[0] for r in cur.fetchall()]
            selected = []
            for cat in categories:
                cur = self.conn.execute("SELECT item_id FROM items WHERE category=?", (cat,))
                ids = [r[0] for r in cur.fetchall()]
                random.shuffle(ids)
                selected.extend(ids[:self.SHOP_PER_CATEGORY])
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
        return cur.fetchall()

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

    def set_user_badge(self, user_id, slot, badge_id):
        self.conn.execute(
            "INSERT INTO user_badges (user_id, slot, badge_id) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, slot) DO UPDATE SET badge_id=excluded.badge_id",
            (user_id, slot, badge_id)
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
            from cosmetics import BADGES
        except Exception:
            return {}
        effects = {}
        for bid in self.get_user_badges(user_id).values():
            if not bid or bid not in BADGES:
                continue
            for k, v in BADGES[bid].get("effect", {}).items():
                effects[k] = effects.get(k, 0) + v
        return effects