"""
Telegram long-polling: POST/SKIP (replies + daily), sichtbare Chat-Bestätigungen,
Commands /status /ping /help /start.
Run alongside: python3 bot.py
"""
import sys
import time

import requests

import config
import database
import poster
import telegram_bot


def _api_base() -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def _callback_chat_and_message_id(cq: dict) -> tuple[int | str | None, int | None]:
    msg = cq.get("message") or {}
    chat = msg.get("chat") or {}
    cid = chat.get("id")
    mid = msg.get("message_id")
    return cid, mid


def _handle_text_command(msg: dict) -> None:
    """Reply to /status, /ping, /help, /start so the user sees the bot is alive."""
    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return
    chat_id = msg.get("chat", {}).get("id")
    if chat_id is None:
        return
    cmd = text.split()[0].split("@", 1)[0].lower()

    if cmd in ("/start", "/help"):
        body = (
            "AlphaCycle X-Bot (Telegram-Listener)\n\n"
            "Auf Freigabe-Nachrichten:\n"
            "POST = auf X veröffentlichen\n"
            "SKIP = verwerfen\n\n"
            "Daily-Posts: eigene Karte mit POST/SKIP.\n\n"
            "Befehle: /status — /ping"
        )
    elif cmd == "/status":
        body = (
            "Listener: aktiv (Long-Polling).\n"
            "Callbacks: post:/skip: (Replies), dpost:/dskip: (Daily).\n"
            "Hinweis: bot.py separat starten (Scanner + Warteschlange)."
        )
    elif cmd == "/ping":
        body = "pong — Listener antwortet."
    else:
        return

    telegram_bot.send_feedback_message(body, chat_id=chat_id)


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

                if raw.startswith("post:"):
                    tweet_id = raw[5:].strip()
                    if not tweet_id:
                        _toast("Fehler: leere tweet_id")
                        _chat("Fehler: POST ohne Tweet-ID (Button ungültig).")
                        continue
                    print(
                        f"[LOG] telegram approval received: POST tweet_id={tweet_id} (from={from_user})"
                    )
                    ok = poster.post_reply(tweet_id)
                    _toast("Reply gesendet." if ok else "Post fehlgeschlagen (Log auf Server).")
                    if ok:
                        _chat(
                            f"Du hast POST gedrückt (Reply).\n"
                            f"Tweet-ID: {tweet_id}\n"
                            f"Ergebnis: Reply wurde auf X veröffentlicht."
                        )
                    else:
                        _chat(
                            f"Du hast POST gedrückt (Reply).\n"
                            f"Tweet-ID: {tweet_id}\n"
                            f"Ergebnis: fehlgeschlagen — Server-Log prüfen (OAuth/X API)."
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
