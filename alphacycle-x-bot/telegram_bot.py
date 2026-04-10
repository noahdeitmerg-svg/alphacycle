"""
Send Telegram inline-keyboard approval requests for reply candidates.
"""
import requests

import config


def _api_base() -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def send_approval(
    tweet_url: str,
    reply_text: str,
    tweet_id: str,
    username: str,
) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID — cannot send approval")
        return False

    body = (
        "New AlphaCycle Reply Candidate\n\n"
        f"Account: @{username}\n\n"
        f"Tweet:\n{tweet_url}\n\n"
        f"Reply:\n{reply_text}\n\n"
        "Approve?"
    )
    max_len = 4096
    if len(body) > max_len:
        body = body[: max_len - 20] + "\n...(truncated)"

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
        return True
    except Exception as e:
        print(f"[TELEGRAM] sendMessage error: {e}")
        return False


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


def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        return
    url = f"{_api_base()}/answerCallbackQuery"
    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
        payload["show_alert"] = False
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"[TELEGRAM] answerCallbackQuery error: {e}")
