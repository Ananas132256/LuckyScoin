import sqlite3


class DB:
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
<<<<<<< HEAD
                last_free_lc INTEGER DEFAULT 0
=======
                last_free_lc INTEGER DEFAULT 0,
                layout TEXT DEFAULT 'classic',
                title TEXT DEFAULT '🎲 Новичок'
>>>>>>> 76f277e (<f>)
            )
        """)
        self._migrate()
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
<<<<<<< HEAD
=======
            "layout":       "TEXT DEFAULT 'classic'",
            "title":        "TEXT DEFAULT '🎲 Новичок'",
>>>>>>> 76f277e (<f>)
        }
        for col, definition in needed.items():
            if col not in existing_cols:
                self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")

    def _ensure(self, user_id):
        self.conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    def set_username(self, user_id, username):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        self.conn.commit()

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
        self.conn.execute(
            f"UPDATE users SET {currency} = ? WHERE user_id=?",
            (amount, user_id)
        )
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
<<<<<<< HEAD
            "SELECT username, sc, lc, wins, losses, games, level, xp FROM users WHERE user_id=?",
            (user_id,)
        )
        username, sc, lc, wins, losses, games, level, xp = cur.fetchone()
        return {
            "username": username, "sc": sc, "lc": lc,
            "wins": wins, "losses": losses, "games": games,
            "level": level, "xp": xp
=======
            "SELECT username, sc, lc, wins, losses, games, level, xp, layout, title "
            "FROM users WHERE user_id=?",
            (user_id,)
        )
        username, sc, lc, wins, losses, games, level, xp, layout, title = cur.fetchone()
        return {
            "username": username, "sc": sc, "lc": lc,
            "wins": wins, "losses": losses, "games": games,
            "level": level, "xp": xp,
            "layout": layout, "title": title
>>>>>>> 76f277e (<f>)
        }

    def top_balances(self, limit=10):
        cur = self.conn.execute(
            "SELECT username, user_id, sc FROM users ORDER BY sc DESC LIMIT ?",
            (limit,)
        )
        return cur.fetchall()

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
        self.conn.execute(
            "UPDATE users SET xp = ?, level = ? WHERE user_id=?",
            (xp, level, user_id)
        )
        self.conn.commit()
        return level, xp, leveled_up

    def set_level(self, user_id, level):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET level = ? WHERE user_id=?", (level, user_id))
        self.conn.commit()

    def set_xp(self, user_id, xp):
        self._ensure(user_id)
        self.conn.execute("UPDATE users SET xp = ? WHERE user_id=?", (xp, user_id))
<<<<<<< HEAD
        self.conn.commit()
=======
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

    # ---------- АДМИН СТАТИСТИКА ----------

    def get_bot_stats(self):
        cur = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(sc),0), COALESCE(SUM(lc),0), COALESCE(SUM(games),0) "
            "FROM users"
        )
        users, sc, lc, games = cur.fetchone()
        return {"users": users, "sc": sc, "lc": lc, "games": games}
>>>>>>> 76f277e (<f>)
