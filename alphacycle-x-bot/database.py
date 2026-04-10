# database.py — SQLite reply tracking
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH, TOPIC_LOOKBACK_DAYS


def _ensure_column(conn, table: str, column: str, coldef: str) -> None:
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table})")
    names = [row[1] for row in c.fetchall()]
    if column not in names:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")


def _reply_history_order_by_clause(conn) -> str:
    c = conn.cursor()
    c.execute("PRAGMA table_info(reply_history)")
    cols = {row[1] for row in c.fetchall()}
    if not cols:
        return "id DESC"
    if "timestamp" in cols and "created_at" in cols:
        return "COALESCE(timestamp, created_at) DESC"
    if "timestamp" in cols:
        return "timestamp DESC"
    return "created_at DESC"


def _upgrade_reply_history_schema(conn) -> None:
    """
    Legacy reply_history had reply_text, tweet_author, approach, created_at.
    New shape adds tweet_text, had_hook, timestamp. Additive only.
    """
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reply_history'")
    if not c.fetchone():
        return
    c.execute("PRAGMA table_info(reply_history)")
    cols = {row[1] for row in c.fetchall()}
    if "tweet_text" not in cols:
        c.execute(
            "ALTER TABLE reply_history ADD COLUMN tweet_text TEXT NOT NULL DEFAULT ''"
        )
    if "had_hook" not in cols:
        c.execute(
            "ALTER TABLE reply_history ADD COLUMN had_hook INTEGER NOT NULL DEFAULT 0"
        )
    if "timestamp" not in cols:
        c.execute("ALTER TABLE reply_history ADD COLUMN timestamp DATETIME")
        if "created_at" in cols:
            c.execute(
                "UPDATE reply_history SET timestamp = created_at WHERE timestamp IS NULL"
            )


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
            approach TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_column(conn, "pending_replies", "approach", "TEXT DEFAULT ''")

    c.execute("""
        CREATE TABLE IF NOT EXISTS reply_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_author TEXT NOT NULL,
            tweet_text TEXT NOT NULL,
            reply_text TEXT NOT NULL,
            approach TEXT NOT NULL,
            had_hook BOOLEAN NOT NULL DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _upgrade_reply_history_schema(conn)

    c.execute("""
        CREATE TABLE IF NOT EXISTS posted_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_text TEXT NOT NULL,
            post_type TEXT NOT NULL,
            arc_score INTEGER,
            topic_summary TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_post_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_snippet TEXT NOT NULL,
            post_preview TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_daily_posts (
            id TEXT PRIMARY KEY,
            post_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_column(conn, "pending_daily_posts", "post_type", "TEXT DEFAULT ''")
    _ensure_column(conn, "pending_daily_posts", "arc_score", "REAL")

    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_runtime (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            booted_at TEXT,
            last_scan_at TEXT,
            scans_date TEXT,
            scans_count INTEGER NOT NULL DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS api_blocked_accounts (
            username TEXT PRIMARY KEY,
            blocked_since DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_attempt DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def set_bot_booted_now() -> None:
    """Call once when bot.py main process starts (uptime baseline)."""
    now = datetime.now(timezone.utc)
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM bot_runtime WHERE id = 1")
    if c.fetchone():
        c.execute("UPDATE bot_runtime SET booted_at = ? WHERE id = 1", (iso,))
    else:
        c.execute(
            """
            INSERT INTO bot_runtime (id, booted_at, last_scan_at, scans_date, scans_count)
            VALUES (1, ?, NULL, NULL, 0)
            """,
            (iso,),
        )
    conn.commit()
    conn.close()


def record_scan_cycle_finished() -> None:
    """Increment scan cycles for current UTC day; set last_scan_at (every finished cycle)."""
    now = datetime.now(timezone.utc)
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    day = now.strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT scans_date, scans_count FROM bot_runtime WHERE id = 1")
    row = c.fetchone()
    if not row:
        c.execute(
            """
            INSERT INTO bot_runtime (id, booted_at, last_scan_at, scans_date, scans_count)
            VALUES (1, ?, ?, ?, 1)
            """,
            (iso, iso, day),
        )
    else:
        sd, sc = row[0], int(row[1] or 0)
        if sd == day:
            new_c = sc + 1
        else:
            new_c = 1
        c.execute(
            """
            UPDATE bot_runtime
            SET last_scan_at = ?, scans_date = ?, scans_count = ?
            WHERE id = 1
            """,
            (iso, day, new_c),
        )
    conn.commit()
    conn.close()


def _parse_stored_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    s = str(ts).strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def get_bot_runtime_status() -> dict[str, str]:
    """
    For Telegram /status. Values are display strings; use 'n/a' if unknown.
    Keys: uptime_h, scans_today, last_scan
    """
    out = {"uptime_h": "n/a", "scans_today": "n/a", "last_scan": "n/a"}
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "SELECT booted_at, last_scan_at, scans_date, scans_count FROM bot_runtime WHERE id = 1"
        )
        row = c.fetchone()
        if not row:
            return out
        booted_at, last_scan_at, scans_date, scans_count = row[0], row[1], row[2], row[3]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        bt = _parse_stored_utc(booted_at)
        if bt is not None:
            hours = (datetime.now(timezone.utc) - bt).total_seconds() / 3600.0
            out["uptime_h"] = str(round(max(0.0, hours), 1))
        if scans_date == today and scans_count is not None:
            out["scans_today"] = str(int(scans_count))
        else:
            out["scans_today"] = "0"
        st = _parse_stored_utc(last_scan_at)
        if st is not None:
            out["last_scan"] = st.strftime("%Y-%m-%d %H:%M UTC")
    finally:
        conn.close()
    return out


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


def get_recent_reply_texts(limit: int = 10) -> list[str]:
    """Latest reply bodies for duplicate-avoidance in growth_engine prompts."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT reply_text FROM replies ORDER BY replied_at DESC LIMIT ?",
        (limit,),
    )
    rows = [str(r[0]) for r in c.fetchall()]
    conn.close()
    return rows


def get_reply_history_texts_for_prompt(limit: int = 10) -> list[str]:
    """
    Last N reply bodies from reply_history (newest first), then fill from replies
    if needed so prompts stay useful on fresh DBs.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ob = _reply_history_order_by_clause(conn)
    c.execute(
        f"SELECT reply_text FROM reply_history ORDER BY {ob} LIMIT ?",
        (limit,),
    )
    hist = [str(r[0]) for r in c.fetchall()]
    conn.close()
    if len(hist) >= limit:
        return hist[:limit]
    seen = set(hist)
    for t in get_recent_reply_texts(max(limit * 2, 20)):
        if t in seen:
            continue
        seen.add(t)
        hist.append(t)
        if len(hist) >= limit:
            break
    return hist[:limit]


def insert_reply_history(reply_text: str, tweet_author: str, approach: str) -> None:
    """Log a posted reply for prompt duplicate-avoidance (after successful X post)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO reply_history (tweet_author, tweet_text, reply_text, approach, had_hook)
        VALUES (?, ?, ?, ?, 0)
        """,
        (tweet_author, "", reply_text, approach or ""),
    )
    conn.commit()
    conn.close()


def get_recent_replies(limit: int = 10) -> list[dict]:
    """Latest rows from reply_history for analytics / richer prompts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    ob = _reply_history_order_by_clause(conn)
    c.execute(
        f"""
        SELECT reply_text, approach, tweet_author
        FROM reply_history
        ORDER BY {ob}
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def save_reply(
    tweet_author: str,
    tweet_text: str,
    reply_text: str,
    approach: str,
    had_hook: bool = False,
) -> None:
    """Full reply_history row (e.g. after post with original tweet + hook flag)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    hook_int = 1 if had_hook else 0
    c.execute(
        """
        INSERT INTO reply_history (tweet_author, tweet_text, reply_text, approach, had_hook)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            tweet_author,
            tweet_text or "",
            reply_text,
            approach or "",
            hook_int,
        ),
    )
    conn.commit()
    conn.close()


def get_recent_topics(days: int = 7) -> list[str]:
    """Lines like 'topic_summary (post_type)' from posted_topics in the last N days."""
    d = max(1, min(int(days), 366))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        f"""
        SELECT topic_summary, post_type FROM posted_topics
        WHERE timestamp > datetime('now', '-{d} days')
        ORDER BY timestamp DESC
        """
    )
    out: list[str] = []
    for row in c.fetchall():
        summary, ptype = row[0], row[1]
        s = (summary or "").strip()
        p = (ptype or "").strip()
        if s and p:
            out.append(f"{s} ({p})")
        elif s:
            out.append(s)
        elif p:
            out.append(p)
    conn.close()
    return out


def save_topic(
    post_text: str,
    post_type: str,
    arc_score: int | None = None,
    topic_summary: str | None = None,
) -> None:
    """Insert into posted_topics (e.g. after Claude summary of a published daily post)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO posted_topics (post_text, post_type, arc_score, topic_summary)
        VALUES (?, ?, ?, ?)
        """,
        (
            post_text or "",
            post_type or "",
            arc_score,
            topic_summary,
        ),
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
    approach: str = "",
) -> bool:
    """Insert a new pending row. Returns True if inserted, False if tweet_id already exists."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO pending_replies (tweet_id, tweet_url, username, reply_text, status, approach)
        VALUES (?, ?, ?, ?, 'pending', ?)
        """,
        (tweet_id, tweet_url, username, reply_text, approach or ""),
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
        """
        SELECT tweet_id, tweet_url, username, reply_text, status,
               COALESCE(approach, '') AS approach
        FROM pending_replies WHERE tweet_id = ?
        """,
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


def get_daily_post_topics_last_7_days(conn: sqlite3.Connection | None = None) -> list[str]:
    """Topic snippets from daily posts recorded in the last TOPIC_LOOKBACK_DAYS (newest first)."""
    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH)
    try:
        d = max(1, min(int(TOPIC_LOOKBACK_DAYS), 366))
        c = conn.cursor()
        c.execute(
            f"""
            SELECT topic_snippet FROM daily_post_topics
            WHERE created_at >= datetime('now', '-{d} days')
            ORDER BY created_at DESC
            """
        )
        return [str(r[0]) for r in c.fetchall()]
    finally:
        if own:
            conn.close()


def insert_pending_daily_post(
    pending_id: str,
    post_text: str,
    post_type: str = "",
    arc_score: float | int | None = None,
) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO pending_daily_posts (id, post_text, status, post_type, arc_score)
        VALUES (?, ?, 'pending', ?, ?)
        """,
        (pending_id, post_text, post_type or "", arc_score),
    )
    ok = c.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def get_pending_daily_post(pending_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT id, post_text, status, post_type, arc_score
        FROM pending_daily_posts WHERE id = ?
        """,
        (pending_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def set_pending_daily_status(pending_id: str, status: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE pending_daily_posts
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, pending_id),
    )
    conn.commit()
    conn.close()


def try_transition_daily_status(pending_id: str, from_status: str, to_status: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE pending_daily_posts
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = ?
        """,
        (to_status, pending_id, from_status),
    )
    ok = c.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def mark_daily_post_skipped(pending_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE pending_daily_posts
        SET status = 'skipped', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status IN ('pending', 'approved')
        """,
        (pending_id,),
    )
    ok = c.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def delete_pending_daily_post(pending_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM pending_daily_posts WHERE id = ?", (pending_id,))
    conn.commit()
    conn.close()


def record_daily_post_topic(
    topic_snippet: str,
    post_preview: str = "",
    conn: sqlite3.Connection | None = None,
) -> None:
    """
    Persist a topic line after a daily post was approved and published (e.g. via Telegram).
    Keeps growth_engine posted_topics history accurate.
    """
    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO daily_post_topics (topic_snippet, post_preview) VALUES (?, ?)",
            ((topic_snippet or "")[:500], (post_preview or "")[:2000]),
        )
        conn.commit()
    finally:
        if own:
            conn.close()


def mark_pending_skipped(tweet_id: str) -> bool:
    """Set status to skipped if pending or approved. Returns True if updated."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE pending_replies
        SET status = 'skipped', updated_at = CURRENT_TIMESTAMP
        WHERE tweet_id = ? AND status IN ('pending', 'approved')
        """,
        (tweet_id,),
    )
    ok = c.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def mark_api_blocked_account(username: str) -> None:
    """Remember account where API posting was blocked; refresh last_attempt."""
    u = (username or "").strip().lstrip("@")
    if not u:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO api_blocked_accounts (username, blocked_since, last_attempt)
        VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(username) DO UPDATE SET
            last_attempt = CURRENT_TIMESTAMP
        """,
        (u,),
    )
    conn.commit()
    conn.close()


def touch_api_blocked_attempt(username: str) -> None:
    u = (username or "").strip().lstrip("@")
    if not u:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        UPDATE api_blocked_accounts
        SET last_attempt = CURRENT_TIMESTAMP
        WHERE username = ?
        """,
        (u,),
    )
    conn.commit()
    conn.close()


def remove_api_blocked_account(username: str) -> None:
    u = (username or "").strip().lstrip("@")
    if not u:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM api_blocked_accounts WHERE username = ?", (u,))
    conn.commit()
    conn.close()


def is_api_blocked_recent(username: str, days: int = 7) -> bool:
    """True if account is in blocklist and blocked_since is within N days."""
    u = (username or "").strip().lstrip("@")
    if not u:
        return False
    d = max(1, min(int(days), 365))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT 1
        FROM api_blocked_accounts
        WHERE username = ?
          AND blocked_since >= datetime('now', ?)
        LIMIT 1
        """,
        (u, f"-{d} days"),
    )
    row = c.fetchone()
    conn.close()
    return row is not None
