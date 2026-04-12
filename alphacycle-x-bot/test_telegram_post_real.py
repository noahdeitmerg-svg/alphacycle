"""
Telegram POST test with a real-looking pending row (no X API reply).

Usage (on server, listener must run: telegram_listener.py):
  python3 test_telegram_post_real.py DEINE_TWEET_ID [username]

Example:
  python3 test_telegram_post_real.py 2042408199127544289 Real_AlphaCycle

After sending, open Telegram and tap POST: you get two Telegram messages
(link + copy text) only — nothing is posted to X via API.
"""
import sys

import database
import telegram_bot


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 test_telegram_post_real.py <tweet_id_snowflake> [username]")
        print("Example: python3 test_telegram_post_real.py 2042408199127544289 Real_AlphaCycle")
        return 1

    tweet_id = sys.argv[1].strip()
    if not tweet_id.isdigit():
        print("tweet_id must be digits only (snowflake).")
        return 1

    username = (sys.argv[2].strip().lstrip("@") if len(sys.argv) > 2 else "Real_AlphaCycle")
    url = f"https://x.com/{username}/status/{tweet_id}"
    body = "Telegram POST test — short reply body for copy-paste handoff."

    database.init_db()
    database.delete_pending_reply(tweet_id)
    if not database.insert_pending_reply(tweet_id, url, username, body):
        print("[WARN] insert_pending_reply returned False — check DB.")
    ok = telegram_bot.send_approval(url, body, tweet_id, username)
    if not ok:
        print("[FEHLER] Telegram send_approval failed.")
        return 1

    print("[OK] Telegram sent. Open Telegram, tap POST for two-part Telegram handoff (no X API).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
