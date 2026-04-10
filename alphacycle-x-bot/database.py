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

    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_replies (
            tweet_id TEXT PRIMARY KEY,
            tweet_url TEXT NOT NULL,
            username TEXT NOT NULL,
            reply_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


def insert_pending_reply(
    tweet_id: str,
    tweet_url: str,
    username: str,
    reply_text: str,
) -> bool:
    """Insert a new pending row. Returns True if inserted, False if tweet_id already exists."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO pending_replies (tweet_id, tweet_url, username, reply_text, status)
        VALUES (?, ?, ?, ?, 'pending')
        """,
        (tweet_id, tweet_url, username, reply_text),
    )
    inserted = c.rowcount > 0
    conn.commit()
    conn.close()
    return inserted


def get_pending_by_tweet_id(tweet_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT tweet_id, tweet_url, username, reply_text, status FROM pending_replies WHERE tweet_id = ?",
        (tweet_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def set_pending_status(tweet_id: str, status: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE pending_replies
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE tweet_id = ?
        """,
        (status, tweet_id),
    )
    conn.commit()
    conn.close()


def try_transition_pending_status(tweet_id: str, from_status: str, to_status: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE pending_replies
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE tweet_id = ? AND status = ?
        """,
        (to_status, tweet_id, from_status),
    )
    ok = c.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def delete_pending_reply(tweet_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM pending_replies WHERE tweet_id = ?", (tweet_id,))
    conn.commit()
    conn.close()


def mark_pending_skipped(tweet_id: str) -> bool:
    """Set status to skipped if currently pending. Returns True if updated."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE pending_replies
        SET status = 'skipped', updated_at = CURRENT_TIMESTAMP
        WHERE tweet_id = ? AND status = 'pending'
        """,
        (tweet_id,),
    )
    ok = c.rowcount > 0
    conn.commit()
    conn.close()
    return ok
