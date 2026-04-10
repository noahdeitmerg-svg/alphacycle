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
                    "allowed_updates": ["callback_query"],
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

                telegram_bot.answer_callback_query(cq_id)

                if raw.startswith("post:"):
                    tweet_id = raw[5:].strip()
                    if not tweet_id:
                        continue
                    print(
                        f"[LOG] telegram approval received: POST tweet_id={tweet_id} (from={from_user})"
                    )
                    poster.post_reply(tweet_id)
                elif raw.startswith("skip:"):
                    tweet_id = raw[5:].strip()
                    if not tweet_id:
                        continue
                    print(
                        f"[LOG] telegram approval received: SKIP tweet_id={tweet_id} (from={from_user})"
                    )
                    if database.mark_pending_skipped(tweet_id):
                        print(f"[LOG] reply skipped tweet_id={tweet_id}")
                    else:
                        print(
                            f"[LISTENER] Skip ignored (no pending row or already finalized) tweet_id={tweet_id}"
                        )
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
    poll_loop()


if __name__ == "__main__":
    main()
