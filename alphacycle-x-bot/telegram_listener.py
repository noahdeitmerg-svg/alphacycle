"""
Telegram long-polling: handle POST / SKIP inline buttons for pending replies.
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
                    continue
                cq_id = cq["id"]
                raw = (cq.get("data") or "").strip()
                from_user = (cq.get("from") or {}).get("username") or cq.get("from", {}).get(
                    "id", "?"
                )
                print(f"[LISTENER] callback_query data={raw!r} from={from_user}")

                if raw.startswith("post:"):
                    tweet_id = raw[5:].strip()
                    if not tweet_id:
                        telegram_bot.answer_callback_query(cq_id, "Fehler: leere tweet_id")
                        continue
                    print(
                        f"[LOG] telegram approval received: POST tweet_id={tweet_id} (from={from_user})"
                    )
                    ok = poster.post_reply(tweet_id)
                    telegram_bot.answer_callback_query(
                        cq_id,
                        "Reply gesendet." if ok else "Post fehlgeschlagen (Log auf Server).",
                    )
                elif raw.startswith("skip:"):
                    tweet_id = raw[5:].strip()
                    if not tweet_id:
                        telegram_bot.answer_callback_query(cq_id, "Fehler: leere tweet_id")
                        continue
                    print(
                        f"[LOG] telegram approval received: SKIP tweet_id={tweet_id} (from={from_user})"
                    )
                    if database.mark_pending_skipped(tweet_id):
                        print(f"[LOG] reply skipped tweet_id={tweet_id}")
                        telegram_bot.answer_callback_query(cq_id, "Skip gespeichert.")
                    else:
                        print(
                            f"[LISTENER] Skip ignored (no pending row or already finalized) tweet_id={tweet_id}"
                        )
                        telegram_bot.answer_callback_query(
                            cq_id,
                            "Kein offener Eintrag (schon erledigt oder alter Button).",
                        )
                else:
                    telegram_bot.answer_callback_query(cq_id, "Unbekannter Button.")

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
