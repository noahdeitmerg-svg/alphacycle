"""
Send Telegram inline-keyboard approval requests for reply candidates.
"""
import os

import requests

import config


def _api_base() -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def send_plain_message(text: str) -> bool:
    """Second message: reply text only (long-press copy). No keyboard."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": (text or "")[:4096],
    }
    url = f"{_api_base()}/sendMessage"
    try:
        r = requests.post(url, json=payload, timeout=45)
        if not r.ok:
            print(f"[TELEGRAM] send_plain_message failed: {r.status_code} {r.text[:400]}")
            return False
        return bool((r.json() or {}).get("ok"))
    except Exception as e:
        print(f"[TELEGRAM] send_plain_message error: {e}")
        return False


def send_approval(
    tweet_url: str,
    reply_text: str,
    tweet_id: str,
    username: str,
    post_mode: str = "auto",
    reply_settings: str = "",
    qa_pass: bool | None = None,
) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID — cannot send approval")
        return False

    u = (username or "").strip().lstrip("@")
    rs = (reply_settings or "").strip() or "(unknown)"
    mode = (post_mode or "auto").strip() or "auto"
    qa_line = "\n\n✅ QA: PASS" if qa_pass is True else ""
    body = (
        f"Reply ready — {mode}{qa_line}\n\n"
        f"Tweet: {tweet_url}\n"
        f"Author: @{u}\n"
        f"Reply setting: {rs}\n\n"
        "Tap POST to send (API or copy-paste if blocked). Reply text follows in the next message."
    )
    max_len = 4096
    if len(body) > max_len:
        body = body[: max_len - 40] + "\n...(truncated)"

    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": body,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "POST", "callback_data": f"post:{tweet_id}"},
                    {"text": "SKIP", "callback_data": f"skip:{tweet_id}"},
                ]
            ]
        },
    }

    url = f"{_api_base()}/sendMessage"
    try:
        r = requests.post(url, json=payload, timeout=45)
        if not r.ok:
            print(f"[TELEGRAM] sendMessage failed: {r.status_code} {r.text[:500]}")
            return False
        data = r.json()
        if not data.get("ok"):
            print(f"[TELEGRAM] sendMessage not ok: {data}")
            return False
        print(f"[LOG] telegram approval sent tweet_id={tweet_id}")
    except Exception as e:
        print(f"[TELEGRAM] sendMessage error: {e}")
        return False

    if not send_plain_message((reply_text or "").strip()):
        print("[TELEGRAM] approval info sent but plain reply message failed")
        return False
    return True


def send_post_outcome_two_part(
    author: str,
    tweet_id: str,
    reply_text: str,
    reply_settings: str,
    post_mode: str,
    result_line: str,
) -> bool:
    """
    After POST: info message + plain reply only (copy-paste path / result notice).
    result_line: e.g. Auto-posted, API blocked, or Restricted.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    a = (author or "").strip().lstrip("@")
    rs = (reply_settings or "").strip() or "(unknown)"
    url = f"https://x.com/{a}/status/{tweet_id}"
    body = (
        f"Reply ready — {post_mode}\n\n"
        f"Tweet: {url}\n"
        f"Author: @{a}\n"
        f"Reply setting: {rs}\n\n"
        f"{result_line}\n\n"
        f"[MANUAL_REPLY] tweet_id={tweet_id} author={a}"
    )[:4096]
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": body}
    req_url = f"{_api_base()}/sendMessage"
    try:
        r = requests.post(req_url, json=payload, timeout=45)
        if not r.ok:
            print(f"[TELEGRAM] send_post_outcome info failed: {r.status_code}")
            return False
        if not (r.json() or {}).get("ok"):
            return False
    except Exception as e:
        print(f"[TELEGRAM] send_post_outcome error: {e}")
        return False
    return send_plain_message((reply_text or "").strip())


def send_daily_post_approval(post_text: str, pending_id: str) -> bool:
    """Telegram approval for original daily post (callbacks dpost: / dskip:)."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID — cannot send daily approval")
        return False

    body = (
        "Daily AlphaCycle Post Candidate\n\n"
        f"{post_text}\n\n"
        "Approve?"
    )
    max_len = 4096
    if len(body) > max_len:
        body = body[: max_len - 20] + "\n...(truncated)"

    cb_post = f"dpost:{pending_id}"
    cb_skip = f"dskip:{pending_id}"
    if len(cb_post.encode("utf-8")) > 64 or len(cb_skip.encode("utf-8")) > 64:
        print("[TELEGRAM] daily post callback_data exceeds 64 bytes — shorten pending_id")
        return False

    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": body,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "POST", "callback_data": cb_post},
                    {"text": "SKIP", "callback_data": cb_skip},
                ]
            ]
        },
    }

    url = f"{_api_base()}/sendMessage"
    try:
        r = requests.post(url, json=payload, timeout=45)
        if not r.ok:
            print(f"[TELEGRAM] sendMessage (daily) failed: {r.status_code} {r.text[:500]}")
            return False
        data = r.json()
        if not data.get("ok"):
            print(f"[TELEGRAM] sendMessage (daily) not ok: {data}")
            return False
        print(f"[LOG] telegram daily post approval sent pending_id={pending_id}")
        return True
    except Exception as e:
        print(f"[TELEGRAM] sendMessage (daily) error: {e}")
        return False


def answer_callback_query(
    callback_query_id: str,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        return
    url = f"{_api_base()}/answerCallbackQuery"
    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
        payload["show_alert"] = show_alert
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"[TELEGRAM] answerCallbackQuery error: {e}")


def send_main_menu(chat_id: int | str | None = None) -> bool:
    """
    Inline keyboard: same actions as /status, /ping, /scan, /queuedaily, /logbot, /logtg, /help.
    """
    cid = chat_id if chat_id is not None else config.TELEGRAM_CHAT_ID
    if not config.TELEGRAM_BOT_TOKEN or not cid:
        return False
    sb = config.SCREEN_SESSION_BOT
    st = config.SCREEN_SESSION_TG
    text = (
        "AlphaCycle X-Bot\n\n"
        "Was die Buttons tun:\n\n"
        "Status — Uptime, Scans heute, Replies, naechster Daily.\n"
        "Ping — Listener erreichbar?\n"
        "Scan jetzt — ein Scan-Zyklus (wie bot.py --once).\n"
        "Daily in Queue — Daily-Post erzeugen + Freigabe in Telegram.\n"
        "Banner — Screenshot alphacycle.app Hero (1500x500), optional X-Header.\n"
        f"Log {sb} — letzte Zeilen Screen-Scrollback (bot.py).\n"
        f"Log {st} — letzte Zeilen Scrollback (dieser Listener).\n"
        "Menue erneut — diese Karte nochmal.\n"
        "Hilfe — Befehlsliste als Text (/scan …).\n\n"
        "Tippe unten oder schreib /start oder menu."
    )
    rows = [
        [
            {"text": "Status", "callback_data": "menu:status"},
            {"text": "Ping", "callback_data": "menu:ping"},
        ],
        [
            {"text": "Scan jetzt", "callback_data": "menu:scan"},
            {"text": "Daily in Queue", "callback_data": "menu:queuedaily"},
        ],
        [
            {"text": "Banner", "callback_data": "menu:banner"},
        ],
        [
            {"text": f"Log {sb}", "callback_data": "menu:logbot"},
            {"text": f"Log {st}", "callback_data": "menu:logtg"},
        ],
        [
            {"text": "Menue erneut", "callback_data": "menu:menu"},
            {"text": "Hilfe (Text)", "callback_data": "menu:help"},
        ],
    ]
    payload = {
        "chat_id": cid,
        "text": text[:4096],
        "reply_markup": {"inline_keyboard": rows},
    }
    url = f"{_api_base()}/sendMessage"
    try:
        r = requests.post(url, json=payload, timeout=45)
        if not r.ok:
            print(f"[TELEGRAM] send_main_menu failed: {r.status_code} {r.text[:500]}")
            return False
        return bool(r.json().get("ok"))
    except Exception as e:
        print(f"[TELEGRAM] send_main_menu error: {e}")
        return False


def send_photo_path(
    photo_path: str,
    caption: str = "",
    chat_id: int | str | None = None,
    reply_to_message_id: int | None = None,
) -> bool:
    """sendPhoto with local file (e.g. X banner PNG)."""
    cid = chat_id if chat_id is not None else config.TELEGRAM_CHAT_ID
    if not config.TELEGRAM_BOT_TOKEN or not cid:
        return False
    path = (photo_path or "").strip()
    if not path or not os.path.isfile(path):
        print(f"[TELEGRAM] send_photo_path: file missing: {path!r}")
        return False
    url = f"{_api_base()}/sendPhoto"
    cap = (caption or "")[:1024]
    try:
        with open(path, "rb") as photo:
            files = {"photo": photo}
            data: dict = {"chat_id": str(cid), "caption": cap}
            if reply_to_message_id is not None:
                data["reply_to_message_id"] = str(reply_to_message_id)
            r = requests.post(url, data=data, files=files, timeout=120)
        if not r.ok:
            print(f"[TELEGRAM] sendPhoto failed: {r.status_code} {r.text[:500]}")
            return False
        return bool((r.json() or {}).get("ok"))
    except Exception as e:
        print(f"[TELEGRAM] send_photo_path error: {e}")
        return False


def send_feedback_message(
    text: str,
    chat_id: int | str | None = None,
    reply_to_message_id: int | None = None,
) -> bool:
    """
    Visible chat message (stays in history). Use after button presses so the user
    sees what happened beyond the short callback toast.
    """
    cid = chat_id if chat_id is not None else config.TELEGRAM_CHAT_ID
    if not config.TELEGRAM_BOT_TOKEN or not cid:
        return False
    payload: dict = {
        "chat_id": cid,
        "text": (text or "")[:4096],
    }
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
    url = f"{_api_base()}/sendMessage"
    try:
        r = requests.post(url, json=payload, timeout=30)
        if not r.ok:
            print(f"[TELEGRAM] send_feedback_message failed: {r.status_code} {r.text[:400]}")
            return False
        data = r.json()
        return bool(data.get("ok"))
    except Exception as e:
        print(f"[TELEGRAM] send_feedback_message error: {e}")
        return False
