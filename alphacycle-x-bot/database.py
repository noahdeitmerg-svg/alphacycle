# database.py — SQLite reply tracking
import sqlite3
from config import DB_PATH


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id TEXT UNIQUE NOT NULL,
            author TEXT NOT NULL,
            reply_text TEXT NOT NULL,
            replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scanned (
            tweet_id TEXT PRIMARY KEY,
            author TEXT NOT NULL,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            skipped_reason TEXT
        )
    """)

    conn.commit()
    conn.close()


def already_replied(tweet_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM replies WHERE tweet_id = ?", (tweet_id,))
    result = c.fetchone()
    conn.close()
    return result is not None


def already_scanned(tweet_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM scanned WHERE tweet_id = ?", (tweet_id,))
    result = c.fetchone()
    conn.close()
    return result is not None


def log_reply(tweet_id: str, author: str, reply_text: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO replies (tweet_id, author, reply_text) VALUES (?, ?, ?)",
        (tweet_id, author, reply_text),
    )
    conn.commit()
    conn.close()


def log_scanned(tweet_id: str, author: str, skipped_reason: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO scanned (tweet_id, author, skipped_reason) VALUES (?, ?, ?)",
        (tweet_id, author, skipped_reason),
    )
    conn.commit()
    conn.close()


def replies_last_hour() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM replies WHERE replied_at > datetime('now', '-1 hour')"
    )
    count = c.fetchone()[0]
    conn.close()
    return count


def replies_today() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM replies WHERE replied_at > datetime('now', 'start of day')"
    )
    count = c.fetchone()[0]
    conn.close()
    return count
