import time
import sys
import database
import scanner
import reply_engine
import poster
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
    return ok


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

    replied = 0
    for tweet in candidates:
        if database.already_replied(tweet["id"]):
            continue

        reply_text = reply_engine.generate_reply(tweet, arc)
        if not reply_text:
            database.log_scanned(tweet["id"], tweet["author"], "no_reply_generated")
            continue

        success = poster.post_reply(tweet["id"], tweet["author"], reply_text)
        if success:
            replied += 1

        # Stop after one successful reply per cycle to stay under limits
        if replied >= 1:
            print("[BOT] 1 reply posted this cycle — stopping to respect rate limits")
            break

    print(f"[BOT] Cycle done. Replied: {replied}. Today: {database.replies_today()}/{config.MAX_REPLIES_PER_DAY}")


def main():
    print("[BOT] AlphaCycle X Bot v2 starting...")
    print(f"[BOT] Tracking: {', '.join(config.TRACKED_ACCOUNTS)}")
    print(f"[BOT] Interval: {config.SCAN_INTERVAL_SECONDS}s")
    print(f"[BOT] Limits: {config.MAX_REPLIES_PER_HOUR}/hr, {config.MAX_REPLIES_PER_DAY}/day")
    print(f"[BOT] Delay: {config.REPLY_DELAY_MIN}-{config.REPLY_DELAY_MAX}s per reply")

    if not preflight_check():
        print("[BOT] Preflight failed — set missing env vars and restart.")
        sys.exit(1)

    database.init_db()
    print("[BOT] Database ready.")
    print("[BOT] All systems go.\n")

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
