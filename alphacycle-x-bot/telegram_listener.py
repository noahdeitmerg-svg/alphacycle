"""
Telegram long-polling: POST/SKIP (replies + daily), sichtbare Chat-Bestätigungen,
Inline-Menue (menu:*), Slash-Befehle, Daily Summary 23:00 UTC.
Run alongside: python3 bot.py
"""
import asyncio
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import config
import database
import poster
import telegram_bot

# UTC calendar day (YYYY-MM-DD) for which we already sent the 23:00 summary.
_summary_sent_for_utc_date: str | None = None


def _api_base() -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def _callback_chat_and_message_id(cq: dict) -> tuple[int | str | None, int | None]:
    msg = cq.get("message") or {}
    chat = msg.get("chat") or {}
    cid = chat.get("id")
    mid = msg.get("message_id")
    return cid, mid


def _parse_manual_meta(text: str) -> tuple[str, str] | tuple[None, None]:
    """
    Extract (tweet_id, author) from poster's manual fallback marker line:
    [MANUAL_REPLY] tweet_id=... author=...
    """
    raw = str(text or "")
    for line in raw.splitlines():
        s = line.strip()
        if not s.startswith("[MANUAL_REPLY]"):
            continue
        parts = s.replace("[MANUAL_REPLY]", "").strip().split()
        tweet_id = ""
        author = ""
        for p in parts:
            if p.startswith("tweet_id="):
                tweet_id = p.split("=", 1)[1].strip()
            elif p.startswith("author="):
                author = p.split("=", 1)[1].strip().lstrip("@")
        if tweet_id and author:
            return tweet_id, author
    return None, None


def _sql_candidates_found_today() -> int:
    """Rows logged as candidate path (scanned, no skip reason) since UTC midnight."""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT COUNT(*) FROM scanned
            WHERE scanned_at >= datetime('now', 'start of day')
            AND (skipped_reason IS NULL OR skipped_reason = '')
            """
        )
        return int(c.fetchone()[0])
    finally:
        conn.close()


def _sql_daily_posts_today() -> int:
    """Original daily posts recorded in posted_topics since UTC midnight."""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT COUNT(*) FROM posted_topics
            WHERE timestamp >= datetime('now', 'start of day')
            """
        )
        return int(c.fetchone()[0])
    finally:
        conn.close()


def _next_daily_post_time_str() -> str:
    """Next calendar run of DAILY_POST_TIME in UTC (bot.py uses TZ=UTC on Linux)."""
    raw = (config.DAILY_POST_TIME or "13:00").strip()
    parts = raw.split(":")
    try:
        h = max(0, min(23, int(parts[0])))
    except (ValueError, IndexError):
        h = 13
    try:
        m = max(0, min(59, int(parts[1]))) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        m = 0
    now = datetime.now(timezone.utc)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%d %H:%M UTC")


def _build_status_body() -> str:
    rt: dict = {}
    try:
        rt = database.get_bot_runtime_status()
        uptime = rt.get("uptime_h", "n/a")
        scans_today = rt.get("scans_today", "n/a")
        last_scan = rt.get("last_scan", "n/a")
    except Exception:
        rt = {}
        uptime = scans_today = last_scan = "n/a"
    up_line = f"Uptime: {uptime}h" if uptime != "n/a" else "Uptime: n/a"
    lines = [
        "AlphaCycle Bot Status:",
        up_line,
        f"Scans today: {scans_today}",
    ]
    try:
        rtd = database.replies_today()
        rlh = database.replies_last_hour()
        lines.append(f"Replies today: {rtd}/{config.MAX_REPLIES_PER_DAY}")
        lines.append(f"Replies this hour: {rlh}/{config.MAX_REPLIES_PER_HOUR}")
    except Exception:
        lines.append("Replies today: n/a")
        lines.append("Replies this hour: n/a")
    lines.append(f"Auto-posted: {rt.get('reply_stat_auto', '0')}")
    lines.append(f"Copy-paste sent: {rt.get('reply_stat_paste', '0')}")
    lines.append(f"Skipped (restricted): {rt.get('reply_stat_restricted', '0')}")
    lines.append(f"Next daily post: {_next_daily_post_time_str()}")
    lines.append(f"Last scan: {last_scan}")
    try:
        lines.append(f"Candidates found today: {_sql_candidates_found_today()}")
    except Exception:
        lines.append("Candidates found today: n/a")
    return "\n".join(lines)


def _authorized_chat(chat_id) -> bool:
    """Only chats listed in TELEGRAM_ALLOWED_CHAT_IDS may use commands and callbacks (when any id is set)."""
    if chat_id is None:
        return False
    allowed = getattr(config, "TELEGRAM_ALLOWED_CHAT_IDS", ()) or ()
    if not allowed:
        return True
    sid = str(chat_id).strip()
    return sid in allowed


def _send_chunks(
    chat_id: int | str,
    text: str,
    reply_to_message_id: int | None = None,
    prefix: str = "",
) -> None:
    """Telegram sendMessage max 4096; send_feedback_message truncates internally."""
    body = (prefix + (text or "")).strip() or "(empty)"
    limit = 4000
    first = True
    for i in range(0, len(body), limit):
        chunk = body[i : i + limit]
        telegram_bot.send_feedback_message(
            chunk,
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id if first else None,
        )
        first = False


def _run_bot_cli(extra_args: list[str]) -> tuple[int, str]:
    """Run bot.py as subprocess (same venv/cwd as listener)."""
    root = Path(__file__).resolve().parent
    bot_py = root / "bot.py"
    timeout_s = 7200 if "--queue-daily" in extra_args else 3600
    cmd = [sys.executable, "-u", str(bot_py)] + extra_args
    try:
        r = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as e:
        tail_out = (e.stdout or "")[-2500:]
        tail_err = (e.stderr or "")[-2500:]
        return -1, f"Timeout after {timeout_s}s.\n{tail_out}\n{tail_err}"
    except OSError as e:
        return -1, f"Subprocess error: {e}"
    out = (r.stdout or "").rstrip()
    err = (r.stderr or "").rstrip()
    combined = out
    if err:
        combined = (out + "\n" + err).strip() if out else err
    return r.returncode, combined or "(no output)"


def _screen_log_tail(session: str, max_lines: int = 150) -> str:
    """
    GNU screen scrollback via hardcopy -h (needs screen session name, e.g. screen -S xbot).
    """
    if not session:
        return "(empty screen session name)"
    fd, path = tempfile.mkstemp(prefix="ac_scr_", suffix=".txt")
    os.close(fd)
    tmp = Path(path)
    try:
        r = subprocess.run(
            ["screen", "-S", session, "-X", "hardcopy", "-h", str(tmp)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            return (
                f"screen hardcopy failed for session {session!r} (code {r.returncode}). "
                f"{err or 'Is screen installed and the session name correct? Set SCREEN_SESSION_BOT / SCREEN_SESSION_TG in .env.'}"
            )
        raw = tmp.read_text(encoding="utf-8", errors="replace")
        raw = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", raw)
        lines = raw.splitlines()
        tail = lines[-max_lines:] if len(lines) > max_lines else lines
        text = "\n".join(tail).strip()
        if not text:
            return f"(no scrollback captured for session {session!r})"
        return f"--- screen -S {session} (last {len(tail)} lines) ---\n{text}"
    except FileNotFoundError:
        return "(screen binary not found on this host)"
    except OSError as e:
        return f"(screen log error: {e})"
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _build_daily_summary_body() -> str:
    try:
        posts = _sql_daily_posts_today()
    except Exception:
        posts = "n/a"
    try:
        replies = database.replies_today()
    except Exception:
        replies = "n/a"
    try:
        cand = _sql_candidates_found_today()
    except Exception:
        cand = "n/a"
    return (
        "Daily Summary:\n"
        f"Posts: {posts}\n"
        f"Replies: {replies}\n"
        "Impressions: n/a (manual check)\n"
        f"Candidates scanned: {cand}"
    )


# Plain text (authorized): show button menu without slash.
_MENU_TRIGGERS = frozenset(
    {
        "menu",
        "menü",
        "hilfe",
        "befehle",
        "hallo",
        "hi",
        "hey",
        "hello",
        "start",
        "help",
        "?",
    }
)


def _build_help_body() -> str:
    return (
        "AlphaCycle X-Bot — Befehle (Slash)\n\n"
        "Freigaben: Auf Kandidaten-Nachrichten POST / SKIP; Daily: POST / SKIP.\n\n"
        "/start /menu — Menue mit Buttons\n"
        "/status — Metriken\n"
        "/ping — Listener lebt\n"
        "/scan — ein Scan-Zyklus (bot.py --once)\n"
        "/queuedaily — Daily jetzt + Freigabe\n"
        "/banner — Dashboard-Hero Screenshot 1500x500 + optional X-Header\n"
        f"/logbot — Screen-Log ({config.SCREEN_SESSION_BOT})\n"
        f"/logtg — Screen-Log ({config.SCREEN_SESSION_TG})\n\n"
        "Hinweis: /scan kann parallel zum laufenden bot.py laufen.\n"
        "Schreib auch menu, hilfe oder banner (ohne Slash)."
    )


def _handle_banner_generate(chat_id, reply_to_message_id: int | None = None) -> None:
    """Run Playwright screenshot + optional X upload; send PNG to Telegram."""
    try:
        from generate_banner import generate_and_upload_banner
    except ImportError as e:
        telegram_bot.send_feedback_message(
            f"[BANNER] Modul fehlt: {e}\n"
            "pip install playwright Pillow && playwright install chromium",
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id,
        )
        return
    telegram_bot.send_feedback_message(
        "[BANNER] Erzeuge Screenshot (1–2 Min) …",
        chat_id=chat_id,
        reply_to_message_id=reply_to_message_id,
    )
    try:
        filepath, success = asyncio.run(generate_and_upload_banner())
    except Exception as e:
        telegram_bot.send_feedback_message(
            f"[BANNER] Fehler: {e}",
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id,
        )
        return
    upload_line = "X Upload: Success" if success else "X Upload: Failed (upload manually on X)"
    caption = f"Banner generated\n{upload_line}"
    if filepath and os.path.isfile(filepath):
        ok = telegram_bot.send_photo_path(
            filepath,
            caption=caption,
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id,
        )
        if not ok:
            telegram_bot.send_feedback_message(
                f"{caption}\n(Telegram photo send failed; file: {filepath})",
                chat_id=chat_id,
                reply_to_message_id=reply_to_message_id,
            )
    else:
        telegram_bot.send_feedback_message(
            f"{caption}\n(No PNG — see server logs.)",
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id,
        )


def _handle_menu_callback(
    cq_id: str,
    raw: str,
    chat_id,
    reply_mid: int | None,
) -> None:
    """Inline keyboard actions (callback_data menu:...)."""
    if not raw.startswith("menu:"):
        return

    def toast(msg: str) -> None:
        telegram_bot.answer_callback_query(cq_id, text=msg[:200])

    key = raw[5:].strip().lower()
    if key in ("menu", "start", ""):
        toast("Menue")
        telegram_bot.send_main_menu(chat_id)
        return
    if key == "help":
        toast("Hilfe")
        telegram_bot.send_feedback_message(
            _build_help_body(),
            chat_id=chat_id,
            reply_to_message_id=reply_mid,
        )
        return
    if key == "status":
        toast("Status")
        telegram_bot.send_feedback_message(
            _build_status_body(),
            chat_id=chat_id,
            reply_to_message_id=reply_mid,
        )
        return
    if key == "ping":
        toast("Pong")
        telegram_bot.send_feedback_message(
            "pong — Listener antwortet.",
            chat_id=chat_id,
            reply_to_message_id=reply_mid,
        )
        return
    if key == "scan":
        toast("Scan … Ergebnis folgt.")
        code, out = _run_bot_cli(["--once"])
        _send_chunks(
            chat_id,
            out,
            reply_to_message_id=reply_mid,
            prefix=f"Scan (bot.py --once)\nExit {code}\n",
        )
        return
    if key == "queuedaily":
        toast("Daily … Ergebnis folgt.")
        code, out = _run_bot_cli(["--queue-daily"])
        _send_chunks(
            chat_id,
            out,
            reply_to_message_id=reply_mid,
            prefix=f"Daily (--queue-daily)\nExit {code}\n",
        )
        return
    if key == "logbot":
        toast(f"Log {config.SCREEN_SESSION_BOT}")
        _send_chunks(
            chat_id,
            _screen_log_tail(config.SCREEN_SESSION_BOT),
            reply_to_message_id=reply_mid,
        )
        return
    if key == "logtg":
        toast(f"Log {config.SCREEN_SESSION_TG}")
        _send_chunks(
            chat_id,
            _screen_log_tail(config.SCREEN_SESSION_TG),
            reply_to_message_id=reply_mid,
        )
        return
    if key == "banner":
        toast("Banner …")
        _handle_banner_generate(chat_id, reply_mid)
        return

    toast("Unbekannt")
    telegram_bot.send_feedback_message(
        f"Unbekannter Menue-Button: {key!r}",
        chat_id=chat_id,
        reply_to_message_id=reply_mid,
    )


def _maybe_send_daily_summary_utc() -> None:
    global _summary_sent_for_utc_date
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    if now.hour != 23:
        return
    if _summary_sent_for_utc_date == today:
        return
    body = _build_daily_summary_body()
    if telegram_bot.send_feedback_message(body):
        _summary_sent_for_utc_date = today
        print(f"[LISTENER] Daily summary sent for UTC date {today}")


def _handle_text_command(msg: dict) -> None:
    """Slash-commands, manual 'done', and remote bot control (authorized chat only)."""
    text = (msg.get("text") or "").strip()
    chat_id = msg.get("chat", {}).get("id")
    if chat_id is None:
        return

    if not text.startswith("/"):
        low = text.lower().strip()
        if _authorized_chat(chat_id) and low == "banner":
            _handle_banner_generate(chat_id, msg.get("message_id"))
            return
        if low != "done" and _authorized_chat(chat_id) and low in _MENU_TRIGGERS:
            telegram_bot.send_main_menu(chat_id)
            return
        if text.lower() != "done":
            return
        if not _authorized_chat(chat_id):
            return
        reply_msg = msg.get("reply_to_message") or {}
        src_text = reply_msg.get("text") or ""
        tweet_id, author = _parse_manual_meta(src_text)
        if not tweet_id or not author:
            return
        row = database.get_pending_by_tweet_id(tweet_id)
        if row:
            database.insert_reply_history(
                row.get("reply_text") or "",
                author,
                (row.get("approach") or "") or "manual_copy_paste",
                row.get("pattern") or "",
            )
            database.set_pending_status(tweet_id, "posted")
        telegram_bot.send_feedback_message(
            f"OK: manual reply logged for @{author} (tweet_id={tweet_id}).",
            chat_id=chat_id,
            reply_to_message_id=msg.get("message_id"),
        )
        return

    if not _authorized_chat(chat_id):
        if text.startswith("/"):
            print(
                "[LISTENER] Rejected slash command (unauthorized chat_id=%r). "
                "Set TELEGRAM_CHAT_ID in .env to this id or a comma-separated list "
                "(e.g. private id + supergroup -100...). Allowed now: %s"
                % (chat_id, ",".join(config.TELEGRAM_ALLOWED_CHAT_IDS) or "(none)"),
            )
        return

    cmd = text.split()[0].split("@", 1)[0].lower()

    if cmd in ("/start", "/menu"):
        telegram_bot.send_main_menu(chat_id)
        return

    if cmd == "/help":
        telegram_bot.send_main_menu(chat_id)
        telegram_bot.send_feedback_message(_build_help_body(), chat_id=chat_id)
        return

    if cmd == "/status":
        telegram_bot.send_feedback_message(_build_status_body(), chat_id=chat_id)
        return
    if cmd == "/ping":
        telegram_bot.send_feedback_message("pong — Listener antwortet.", chat_id=chat_id)
        return

    if cmd == "/scan":
        telegram_bot.send_feedback_message(
            "Starte einen Scan-Zyklus (bot.py --once) ...",
            chat_id=chat_id,
        )
        code, out = _run_bot_cli(["--once"])
        head = f"Exit {code}\n"
        _send_chunks(chat_id, out, prefix=head)
        return

    if cmd in ("/queuedaily", "/queue_daily", "/dailyqueue"):
        telegram_bot.send_feedback_message(
            "Daily-Post wird erzeugt und zur Freigabe gesendet (bot.py --queue-daily) ...",
            chat_id=chat_id,
        )
        code, out = _run_bot_cli(["--queue-daily"])
        head = f"Exit {code}\n"
        _send_chunks(chat_id, out, prefix=head)
        return

    if cmd in ("/logbot", "/log_xbot", "/screenbot"):
        log_text = _screen_log_tail(config.SCREEN_SESSION_BOT)
        _send_chunks(chat_id, log_text)
        return

    if cmd in ("/logtg", "/log_tg", "/screentg", "/screen_tg"):
        log_text = _screen_log_tail(config.SCREEN_SESSION_TG)
        _send_chunks(chat_id, log_text)
        return

    if cmd == "/banner":
        _handle_banner_generate(chat_id, msg.get("message_id"))
        return


def preflight() -> bool:
    if not config.TELEGRAM_BOT_TOKEN:
        print("[LISTENER] MISSING: TELEGRAM_BOT_TOKEN")
        return False
    return True


def ensure_polling_mode() -> None:
    """
    Webhook and getUpdates cannot be used together. If a webhook is set,
    button callbacks never reach this listener.
    """
    base = _api_base()
    try:
        info = requests.get(f"{base}/getWebhookInfo", timeout=15).json()
        wh_url = (info.get("result") or {}).get("url") or ""
        if wh_url:
            print(f"[LISTENER] Active webhook blocks getUpdates: {wh_url!r} — removing...")
        else:
            print("[LISTENER] No webhook set (OK for long polling).")
        dr = requests.post(
            f"{base}/deleteWebhook",
            json={"drop_pending_updates": False},
            timeout=15,
        ).json()
        if not dr.get("ok"):
            print(f"[LISTENER] deleteWebhook warning: {dr}")
        else:
            print("[LISTENER] deleteWebhook OK — polling enabled.")
    except Exception as e:
        print(f"[LISTENER] ensure_polling_mode error: {e}")


def poll_loop() -> None:
    offset = 0
    print("[LISTENER] Telegram callback listener started (getUpdates long polling).")
    while True:
        try:
            _maybe_send_daily_summary_utc()
            url = f"{_api_base()}/getUpdates"
            r = requests.get(
                url,
                params={
                    "offset": offset,
                    "timeout": 50,
                },
                timeout=55,
            )
            if not r.ok:
                print(f"[LISTENER] getUpdates HTTP {r.status_code}: {r.text[:300]}")
                time.sleep(5)
                continue
            data = r.json()
            if not data.get("ok"):
                print(f"[LISTENER] getUpdates not ok: {data}")
                time.sleep(5)
                continue

            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                cq = upd.get("callback_query")
                if not cq:
                    plain = upd.get("message")
                    if plain:
                        _handle_text_command(plain)
                    continue

                cq_id = cq["id"]
                raw = (cq.get("data") or "").strip()
                chat_id, reply_mid = _callback_chat_and_message_id(cq)
                from_user = (cq.get("from") or {}).get("username") or cq.get("from", {}).get(
                    "id", "?"
                )
                print(f"[LISTENER] callback_query data={raw!r} from={from_user}")

                def _toast(t: str) -> None:
                    telegram_bot.answer_callback_query(cq_id, t)

                def _chat(detail: str) -> None:
                    telegram_bot.send_feedback_message(
                        detail,
                        chat_id=chat_id,
                        reply_to_message_id=reply_mid,
                    )

                if not _authorized_chat(chat_id):
                    _toast("Nicht autorisiert.")
                    print(
                        "[LISTENER] Rejected callback chat_id=%r (allowed: %s)"
                        % (chat_id, ",".join(config.TELEGRAM_ALLOWED_CHAT_IDS) or "(none)"),
                    )
                    continue

                if raw.startswith("menu:"):
                    _handle_menu_callback(cq_id, raw, chat_id, reply_mid)
                    continue

                if raw.startswith("post:"):
                    tweet_id = raw[5:].strip()
                    if not tweet_id:
                        _toast("Fehler: leere tweet_id")
                        _chat("Fehler: POST ohne Tweet-ID (Button ungültig).")
                        continue
                    print(
                        f"[LOG] telegram approval received: POST tweet_id={tweet_id} (from={from_user})"
                    )
                    result = poster.complete_approved_reply(tweet_id)
                    if result == "telegram":
                        _toast("Anleitung gesendet.")
                        _chat(
                            f"Du hast POST gedrückt (Reply).\n"
                            f"Tweet-ID: {tweet_id}\n"
                            f"Ergebnis: Zwei Telegram-Nachrichten (Link + Text) wurden gesendet; "
                            f"kein X-API-Versuch."
                        )
                    else:
                        _toast("Telegram-Versand fehlgeschlagen (Log auf Server).")
                        _chat(
                            f"Du hast POST gedrückt (Reply).\n"
                            f"Tweet-ID: {tweet_id}\n"
                            f"Ergebnis: fehlgeschlagen — Server-Log prüfen (Telegram sendMessage)."
                        )
                elif raw.startswith("skip:"):
                    tweet_id = raw[5:].strip()
                    if not tweet_id:
                        _toast("Fehler: leere tweet_id")
                        _chat("Fehler: SKIP ohne Tweet-ID.")
                        continue
                    print(
                        f"[LOG] telegram approval received: SKIP tweet_id={tweet_id} (from={from_user})"
                    )
                    if database.mark_pending_skipped(tweet_id):
                        print(f"[LOG] reply skipped tweet_id={tweet_id}")
                        _toast("Skip gespeichert.")
                        _chat(
                            f"Du hast SKIP gedrückt (Reply).\n"
                            f"Tweet-ID: {tweet_id}\n"
                            f"Ergebnis: verworfen, kein Post auf X."
                        )
                    else:
                        print(
                            f"[LISTENER] Skip ignored (no pending row or already finalized) tweet_id={tweet_id}"
                        )
                        _toast("Kein offener Eintrag (schon erledigt oder alter Button).")
                        _chat(
                            f"Du hast SKIP gedrückt (Reply).\n"
                            f"Tweet-ID: {tweet_id}\n"
                            f"Hinweis: kein offener Pending-Eintrag mehr "
                            f"(bereits erledigt oder alter Button)."
                        )
                elif raw.startswith("dpost:"):
                    pending_id = raw[6:].strip()
                    if not pending_id:
                        _toast("Fehler: leere pending_id")
                        _chat("Fehler: POST ohne Daily-Pending-ID.")
                        continue
                    print(
                        f"[LOG] telegram daily: POST pending_id={pending_id} (from={from_user})"
                    )
                    ok = poster.post_daily_post(pending_id)
                    _toast(
                        "Daily post gesendet." if ok else "Daily post fehlgeschlagen (Log)."
                    )
                    if ok:
                        _chat(
                            f"Du hast POST gedrückt (Daily Post).\n"
                            f"Pending-ID: {pending_id}\n"
                            f"Ergebnis: Post wurde auf X veröffentlicht."
                        )
                    else:
                        _chat(
                            f"Du hast POST gedrückt (Daily Post).\n"
                            f"Pending-ID: {pending_id}\n"
                            f"Ergebnis: fehlgeschlagen — Server-Log prüfen."
                        )
                elif raw.startswith("dskip:"):
                    pending_id = raw[6:].strip()
                    if not pending_id:
                        _toast("Fehler: leere pending_id")
                        _chat("Fehler: SKIP ohne Daily-Pending-ID.")
                        continue
                    print(
                        f"[LOG] telegram daily: SKIP pending_id={pending_id} (from={from_user})"
                    )
                    if database.mark_daily_post_skipped(pending_id):
                        _toast("Daily skip gespeichert.")
                        _chat(
                            f"Du hast SKIP gedrückt (Daily Post).\n"
                            f"Pending-ID: {pending_id}\n"
                            f"Ergebnis: Daily verworfen, kein Post auf X."
                        )
                    else:
                        _toast("Kein offener Daily-Eintrag.")
                        _chat(
                            f"Du hast SKIP gedrückt (Daily Post).\n"
                            f"Pending-ID: {pending_id}\n"
                            f"Hinweis: kein offener Daily-Eintrag mehr."
                        )
                else:
                    _toast("Unbekannter Button.")
                    _chat(f"Unbekannter Callback: {raw!r}")

        except KeyboardInterrupt:
            print("\n[LISTENER] Stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"[LISTENER] Loop error: {e}")
            time.sleep(5)


def main() -> None:
    database.init_db()
    if not preflight():
        sys.exit(1)
    ensure_polling_mode()
    poll_loop()


if __name__ == "__main__":
    main()
