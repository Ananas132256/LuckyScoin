import sqlite3
import random
import time


class DB:
    # ---------- КОНСТАНТЫ КАЗИНО ----------
    CASINO_INCOME = {
        1: 30, 2: 80, 3: 200, 4: 500, 5: 1200,
        6: 3000, 7: 8000, 8: 20000, 9: 50000, 10: 130000,
    }
    CASINO_UPGRADE_COST = {
        1: 1000, 2: 2500, 3: 6000, 4: 15000, 5: 40000,
        6: 100000, 7: 250000, 8: 600000, 9: 1500000,
    }
    CASINO_USER_REQ = {
        1: 0, 2: 1, 3: 3, 4: 5, 5: 8,
        6: 12, 7: 16, 8: 22, 9: 30, 10: 40,
    }
    CASINO_MAX_HOURS = 8
    CASINO_MAX_LEVEL = 10

    SHOP_REFRESH_SECONDS = 6 * 3600
    SHOP_PER_CATEGORY = 4

    def __init__(self):
        self.conn = sqlite3.connect("casino.db")
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
        self.conn.execute("INSERT OR IGNORE INTO shop_meta (id, next_refresh) VALUES (1, 0)")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_stock (
                item_id INTEGER PRIMARY KEY
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS casinos (
                user_id INTEGER PRIMARY KEY,
                name TEXT DEFAULT 'Моё казино',
                level INTEGER DEFAULT 1,
                last_collect INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0
            )
        """)
        self._migrate()
        self._init_items()
        self.conn.commit()

    def _migrate(self):
        cur = self.conn.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cur.fetchall()}
        needed = {
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
        for col, definition in needed.items():
            if col not in existing_cols:
                self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")

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

    # ---------- ЮЗЕР ----------

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

    # ---------- УРОВНИ / XP ----------

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

    # ---------- НАСТРОЙКИ ----------

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

    # ---------- ЛИДЕРБОРД ----------

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

    # ---------- СТАТИСТИКА ДЛЯ АДМИНА ----------

    def get_bot_stats(self):
        cur = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(sc),0), COALESCE(SUM(lc),0), COALESCE(SUM(games),0) "
            "FROM users"
        )
        users, sc, lc, games = cur.fetchone()
        return {"users": users, "sc": sc, "lc": lc, "games": games}

    # ---------- МАГАЗИН ----------

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

    # ---------- РОТАЦИЯ МАГАЗИНА ----------

    def get_shop_items(self):
        now = int(time.time())
        cur = self.conn.execute("SELECT next_refresh FROM shop_meta WHERE id=1")
        next_refresh = cur.fetchone()[0]

        if now >= next_refresh:
            cur = self.conn.execute("SELECT DISTINCT category FROM items")
            categories = [r[0] for r in cur.fetchall()]

            selected = []
            for cat in categories:
                cur = self.conn.execute(
                    "SELECT item_id FROM items WHERE category=?",
                    (cat,)
                )
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

    # ---------- СВОЁ КАЗИНО (TYCOON) ----------

    def get_casino(self, user_id):
        cur = self.conn.execute(
            "SELECT user_id, name, level, last_collect, total_earned FROM casinos WHERE user_id=?",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0], "name": row[1], "level": row[2],
            "last_collect": row[3], "total_earned": row[4],
        }

    def create_casino(self, user_id):
        now = int(time.time())
        self.conn.execute(
            "INSERT OR IGNORE INTO casinos (user_id, name, level, last_collect, total_earned) "
            "VALUES (?, 'Моё казино', 1, ?, 0)",
            (user_id, now)
        )
        self.conn.commit()

    def get_pending_income(self, user_id):
        casino = self.get_casino(user_id)
        if not casino:
            return 0, 0, 0
        now = int(time.time())
        elapsed = now - casino["last_collect"]
        capped = min(elapsed, self.CASINO_MAX_HOURS * 3600)
        income_per_hour = self.CASINO_INCOME.get(casino["level"], 0)
        pending = int(income_per_hour * capped / 3600)
        return pending, elapsed, income_per_hour

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

    def upgrade_casino(self, user_id):
        casino = self.get_casino(user_id)
        if not casino:
            return False, "❌ Сначала открой своё казино"

        level = casino["level"]
        if level >= self.CASINO_MAX_LEVEL:
            return False, "👑 У тебя уже максимальный уровень!"

        self.collect_casino(user_id)

        cost = self.CASINO_UPGRADE_COST.get(level, 0)
        next_level = level + 1
        req_user_level = self.CASINO_USER_REQ.get(next_level, 999)

        lc = self.get_balance(user_id, "lc")
        if lc < cost:
            return False, f"❌ Нужно {cost} LC, у тебя {lc}"

        user_level, _ = self.get_level_xp(user_id)
        if user_level < req_user_level:
            return False, f"❌ Нужен юзер-уровень {req_user_level}, у тебя {user_level}"

        self.add_balance(user_id, "lc", -cost)
        self.conn.execute("UPDATE casinos SET level=? WHERE user_id=?", (next_level, user_id))
        self.conn.commit()
        return True, f"📈 Казино прокачано до уровня {next_level}!"

    def rename_casino(self, user_id, name):
        self.conn.execute("UPDATE casinos SET name=? WHERE user_id=?", (name, user_id))
        self.conn.commit()

    def top_casinos(self, limit=10):
        cur = self.conn.execute(
            "SELECT casinos.user_id, users.username, users.title, "
            "casinos.name, casinos.level, casinos.total_earned "
            "FROM casinos JOIN users ON casinos.user_id = users.user_id "
            "ORDER BY casinos.level DESC, casinos.total_earned DESC LIMIT ?",
            (limit,)
        )
        return cur.fetchall()

    def get_casino_rank(self, user_id):
        """Возвращает место юзера в рейтинге казино."""
        cur = self.conn.execute("""
            SELECT COUNT(*) + 1 FROM casinos
            WHERE level > (SELECT level FROM casinos WHERE user_id=?)
               OR (level = (SELECT level FROM casinos WHERE user_id=?)
                   AND total_earned > (SELECT total_earned FROM casinos WHERE user_id=?))
        """, (user_id, user_id, user_id))
        return cur.fetchone()[0]

    def count_active_casinos(self):
        """Сколько казино реально прокачано (не пустышки)."""
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM casinos WHERE level > 1 OR total_earned > 0"
        )
        return cur.fetchone()[0]

    def count_all_casinos(self):
        """Сколько всего казино создано."""
        cur = self.conn.execute("SELECT COUNT(*) FROM casinos")
        return cur.fetchone()[0]

    def get_user_casino_position(self, user_id, limit=10):
        """Возвращает (место_в_рейтинге, входит_ли_в_топ). None если нет казино или пустышка."""
        rank = self.get_casino_rank(user_id)
        if rank is None:
            return None, False
        return rank, rank <= limit