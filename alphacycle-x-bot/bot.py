import argparse
import time
import sys
import database
import scanner
import reply_engine
import telegram_bot
import config


def preflight_check() -> bool:
    ok = True
    if not config.TWITTER_BEARER:
        print("[BOT] MISSING: TWITTER_BEARER")
        ok = False
    if not config.TWITTER_API_KEY:
        print("[BOT] MISSING: TWITTER_API_KEY")
        ok = False
    if not config.TWITTER_API_SECRET:
        print("[BOT] MISSING: TWITTER_API_SECRET")
        ok = False
    if not config.TWITTER_ACCESS_TOKEN:
        print("[BOT] MISSING: TWITTER_ACCESS_TOKEN")
        ok = False
    if not config.TWITTER_ACCESS_SECRET:
        print("[BOT] MISSING: TWITTER_ACCESS_SECRET")
        ok = False
    if not config.CLAUDE_API_KEY:
        print("[BOT] MISSING: CLAUDE_API_KEY")
        ok = False
    if not config.TELEGRAM_BOT_TOKEN:
        print("[BOT] MISSING: TELEGRAM_BOT_TOKEN")
        ok = False
    if not config.TELEGRAM_CHAT_ID:
        print("[BOT] MISSING: TELEGRAM_CHAT_ID")
        ok = False
    return ok


def _tweet_url(username: str, tweet_id: str) -> str:
    u = (username or "").lstrip("@")
    return f"https://x.com/{u}/status/{tweet_id}"


def run_cycle():
    print("\n" + "=" * 50)
    print("[BOT] Starting scan cycle...")

    candidates = scanner.scan_tweets()
    if not candidates:
        print("[BOT] No candidates — sleeping.")
        return

    arc = reply_engine.fetch_arc_context()
    if not arc:
        print("[BOT] No ARC data — skipping cycle.")
        return

    print(f"[BOT] ARC: {arc.get('arc_score', '?')} ({arc.get('zone_name', '?')})")

    queued = 0
    for tweet in candidates:
        if database.already_replied(tweet["id"]):
            continue

        reply_text = reply_engine.generate_reply(tweet, arc)
        if not reply_text:
            database.log_scanned(tweet["id"], tweet["author"], "no_reply_generated")
            continue

        tw_url = _tweet_url(tweet["author"], tweet["id"])
        if not database.insert_pending_reply(
            tweet["id"], tw_url, tweet["author"], reply_text
        ):
            print(f"[BOT] Pending row already exists for tweet {tweet['id']} — skip duplicate queue")
            continue

        sent = telegram_bot.send_approval(
            tw_url, reply_text, tweet["id"], tweet["author"]
        )
        if sent:
            queued += 1
        else:
            database.delete_pending_reply(tweet["id"])
            print(f"[BOT] Telegram send failed — removed pending row for tweet {tweet['id']}")

    print(
        f"[BOT] Cycle done. Queued for Telegram approval: {queued}. "
        f"Posted today (already on X): {database.replies_today()}/{config.MAX_REPLIES_PER_DAY}"
    )


def main():
    parser = argparse.ArgumentParser(description="AlphaCycle X Bot")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan cycle then exit (good for smoke tests).",
    )
    args = parser.parse_args()

    print("[BOT] AlphaCycle X Bot v2 starting...")
    print("[BOT] Config: .env auto-loaded from folder containing config.py (python-dotenv).")
    print("[BOT] Mode: replies require Telegram approval (run telegram_listener.py).")
    print(f"[BOT] Tracking: {', '.join(config.TRACKED_ACCOUNTS)}")
    print(f"[BOT] Interval: {config.SCAN_INTERVAL_SECONDS}s")
    print(f"[BOT] Limits: {config.MAX_REPLIES_PER_HOUR}/hr, {config.MAX_REPLIES_PER_DAY}/day")
    print(f"[BOT] Delay: {config.REPLY_DELAY_MIN}-{config.REPLY_DELAY_MAX}s per reply")

    if not preflight_check():
        print("[BOT] Preflight failed — add secrets to .env next to config.py and retry.")
        sys.exit(1)

    database.init_db()
    print("[BOT] Database ready.")
    print("[BOT] All systems go.\n")

    if args.once:
        try:
            run_cycle()
        except KeyboardInterrupt:
            print("\n[BOT] Stopped.")
        except Exception as e:
            print(f"[BOT] Cycle error: {e}")
        return

    while True:
        try:
            run_cycle()
        except KeyboardInterrupt:
            print("\n[BOT] Stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"[BOT] Cycle error: {e}")

        print(f"[BOT] Sleeping {config.SCAN_INTERVAL_SECONDS}s...")
        time.sleep(config.SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
