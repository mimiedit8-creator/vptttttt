import os
import aiosqlite
from pathlib import Path

class Database:
    def __init__(self, path: str):
        self.path = path

    async def connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(self.path)
        db.row_factory = aiosqlite.Row
        return db

    async def init(self):
        async with await self.connect() as db:
            await db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL DEFAULT '',
                allow_messages INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS blocks(
                blocker_id INTEGER NOT NULL,
                blocked_id INTEGER NOT NULL,
                PRIMARY KEY(blocker_id, blocked_id)
            );
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tracks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tracking_number TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, tracking_number)
            );
            CREATE TABLE IF NOT EXISTS schedule_cache(
                day_key TEXT PRIMARY KEY,
                body TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            ''')
            await db.commit()

    async def upsert_user(self, user):
        async with await self.connect() as db:
            await db.execute(
                "INSERT INTO users(user_id, username, first_name) VALUES(?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
                (user.id, (user.username or "").lower(), user.first_name or ""),
            )
            await db.commit()

    async def get_user_by_username(self, username):
        async with await self.connect() as db:
            cur = await db.execute("SELECT * FROM users WHERE username=?", (username.lower().lstrip("@"),))
            return await cur.fetchone()

    async def set_allow_messages(self, user_id, enabled):
        async with await self.connect() as db:
            await db.execute("UPDATE users SET allow_messages=? WHERE user_id=?", (int(enabled), user_id))
            await db.commit()

    async def is_allowed(self, sender_id, recipient_id):
        async with await self.connect() as db:
            cur = await db.execute("SELECT allow_messages FROM users WHERE user_id=?", (recipient_id,))
            row = await cur.fetchone()
            if not row or not row["allow_messages"]:
                return False
            cur = await db.execute("SELECT 1 FROM blocks WHERE blocker_id=? AND blocked_id=?", (recipient_id, sender_id))
            return await cur.fetchone() is None

    async def block(self, blocker_id, blocked_id):
        async with await self.connect() as db:
            await db.execute("INSERT OR IGNORE INTO blocks VALUES(?,?)", (blocker_id, blocked_id))
            await db.commit()

    async def save_message(self, sender_id, recipient_id, body):
        async with await self.connect() as db:
            await db.execute("INSERT INTO messages(sender_id, recipient_id, body) VALUES(?,?,?)",
                             (sender_id, recipient_id, body))
            await db.commit()

    async def save_track(self, user_id, number):
        async with await self.connect() as db:
            await db.execute("INSERT OR IGNORE INTO tracks(user_id, tracking_number) VALUES(?,?)",
                             (user_id, number))
            await db.commit()

    async def get_tracks(self, user_id):
        async with await self.connect() as db:
            cur = await db.execute("SELECT tracking_number FROM tracks WHERE user_id=? ORDER BY id DESC", (user_id,))
            return [r["tracking_number"] for r in await cur.fetchall()]

    async def set_schedule(self, day_key, body):
        async with await self.connect() as db:
            await db.execute(
                "INSERT INTO schedule_cache(day_key, body, updated_at) VALUES(?,?,CURRENT_TIMESTAMP) "
                "ON CONFLICT(day_key) DO UPDATE SET body=excluded.body, updated_at=CURRENT_TIMESTAMP",
                (day_key, body),
            )
            await db.commit()

    async def get_schedule(self, day_key):
        async with await self.connect() as db:
            cur = await db.execute("SELECT body, updated_at FROM schedule_cache WHERE day_key=?", (day_key,))
            return await cur.fetchone()
