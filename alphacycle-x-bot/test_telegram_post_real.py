"""
Telegram POST test with a REAL X tweet id (creates an actual reply on X).

Usage (on server, listener must run: telegram_listener.py):
  python3 test_telegram_post_real.py DEINE_TWEET_ID

Example — reply to your own tweet (id from URL .../status/123...):
  python3 test_telegram_post_real.py 2042408199127544289

After sending, open Telegram and tap POST.
Wait: poster uses a random delay (several minutes) before tweeting — that is normal.

Requires: tweet you are allowed to reply to (often your own tweet works best).
"""
import sys

import database
import telegram_bot
import config


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 test_telegram_post_real.py <tweet_id_snowflake>")
        print("Example: python3 test_telegram_post_real.py 2042408199127544289")
        return 1

    tweet_id = sys.argv[1].strip()
    if not tweet_id.isdigit():
        print("tweet_id must be digits only (snowflake).")
        return 1

    username = (sys.argv[2].strip().lstrip("@") if len(sys.argv) > 2 else "Real_AlphaCycle")
    url = f"https://x.com/{username}/status/{tweet_id}"
    body = (
        "Telegram POST test — reply from AlphaCycle bot (safe short text)."
    )

    database.init_db()
    database.delete_pending_reply(tweet_id)
    if not database.insert_pending_reply(tweet_id, url, username, body):
        print("[WARN] insert_pending_reply returned False — check DB.")
    ok = telegram_bot.send_approval(url, body, tweet_id, username)
    if not ok:
        print("[FEHLER] Telegram send_approval failed.")
        return 1

    print("[OK] Telegram sent. Open Telegram, tap POST.")
    print(
        f"[INFO] Random wait {config.REPLY_DELAY_MIN}-{config.REPLY_DELAY_MAX}s before X posts — be patient."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
