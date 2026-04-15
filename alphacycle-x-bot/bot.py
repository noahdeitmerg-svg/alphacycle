import argparse
import asyncio
import logging
import os
import sys
import time
import uuid

import schedule

import database
import telegram_bot
import config
import growth_engine

_logger = logging.getLogger(__name__)
from daily_post_engine import fetch_arc_data, generate_daily_post
import scanner
import reply_engine


def _configure_schedule_utc() -> None:
    """Make schedule.every().day.at(DAILY_POST_TIME) fire at that clock time in the process TZ (tzset for UTC)."""
    if sys.platform != "win32" and hasattr(time, "tzset"):
        os.environ["TZ"] = "UTC"
        time.tzset()


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


def _arc_score_for_pending(arc: dict | None) -> float | None:
    """Raw ARC score from fetch_arc_data for pending_daily_posts.arc_score (REAL)."""
    if not arc:
        return None
    v = arc.get("arc_score")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def schedule_daily_post() -> None:
    """
    Daily 13:00 (UTC if TZ=UTC / tzset on Linux): fetch ARC, generate post, queue Telegram approval.
    """
    print("[DAILY] schedule_daily_post triggered")
    arc = fetch_arc_data()
    if not arc:
        print("[DAILY] WARNING: fetch_arc_data failed — no daily post queued")
        return
    text, post_type = generate_daily_post(arc, None)
    if not text:
        print("[DAILY] WARNING: generate_daily_post returned nothing — skip queue")
        return
    pending_id = str(uuid.uuid4())
    arc_snap = _arc_score_for_pending(arc)
    if not database.insert_pending_daily_post(
        pending_id, text, post_type, arc_snap
    ):
        print(f"[DAILY] WARNING: insert pending daily failed id={pending_id}")
        return
    image_buf = None
    try:
        from signal_visual import generate_from_api

        image_buf, _arc_data = asyncio.run(generate_from_api(config.ARC_API_URL))
        _logger.info("[DAILY] Telegram preview image generated")
    except Exception as e:
        _logger.warning("[DAILY] Telegram preview image failed: %s — text-only approval", e)
        image_buf = None

    sent = telegram_bot.send_daily_post_approval(text, pending_id, image_buf)
    if not sent:
        database.delete_pending_daily_post(pending_id)
        print("[DAILY] Telegram send failed — removed pending daily row")


def _weekly_banner_job() -> None:
    """
    Sunday 12:00 UTC: screenshot alphacycle.app hero -> 1500x500 PNG, optional X header upload.
    """
    print("[BANNER] Weekly banner job triggered")
    try:
        from generate_banner import generate_and_upload_banner
    except ImportError as e:
        print(f"[BANNER] Import failed: {e}")
        telegram_bot.send_feedback_message(
            "[BANNER] generate_banner not importable. Install: pip install playwright Pillow "
            "and playwright install chromium."
        )
        return
    try:
        filepath, success = asyncio.run(generate_and_upload_banner())
    except Exception as e:
        _logger.exception("[BANNER] Job failed")
        telegram_bot.send_feedback_message(f"[BANNER] Job failed: {e}")
        return
    if success:
        telegram_bot.send_feedback_message(
            "[BANNER] X profile header updated from latest alphacycle.app screenshot."
        )
    elif filepath:
        telegram_bot.send_feedback_message(
            f"[BANNER] PNG generated but X upload failed.\nFile: {filepath}\nUpload manually on X."
        )
    else:
        telegram_bot.send_feedback_message(
            "[BANNER] Screenshot failed. Check logs; ensure playwright+Pillow and chromium."
        )


def run_cycle():
    try:
        print("\n" + "=" * 50)
        print("[BOT] Starting scan cycle...")

        candidates = scanner.scan_tweets()
        if not candidates:
            print(
                "[BOT] No candidates — sleeping.\n"
                "[BOT] Filters: tweet age "
                f"{config.MIN_TWEET_AGE_SECONDS}s–{config.MAX_TWEET_AGE_SECONDS}s, "
                f"min {config.MIN_LIKES_TO_REPLY} likes, no RT/reply; "
                "then blocked + relevant-keyword filters, not already scanned/replied, author spacing, "
                f"max {config.MAX_REPLIES_PER_ACCOUNT_PER_DAY} replies per @ per UTC day. "
                "Widen: .env SCAN_TWEET_MAX_AGE / MAX_TWEET_AGE_SECONDS, MIN_LIKES_TO_REPLY."
            )
            return

        arc = fetch_arc_data()
        if not arc:
            print("[BOT] No ARC data — skipping cycle.")
            return

        print(f"[BOT] ARC: {arc.get('arc_score', '?')} ({arc.get('zone_name', '?')})")

        queued = 0
        for tweet in candidates:
            if database.already_replied(tweet["id"]):
                continue

            if config.QA_ENABLED:
                (
                    reply_text,
                    qa_status,
                    qa_attempts,
                    approach_key,
                    pattern_key,
                ) = growth_engine.generate_reply_with_qa(tweet, arc_data=arc)
            else:
                reply_text, approach_key, pattern_key = reply_engine.generate_reply(
                    tweet, arc_data=arc
                )
                qa_status = None
                qa_attempts = 1
                if reply_text is None:
                    if approach_key and pattern_key:
                        database.log_scanned(
                            tweet["id"], tweet["author"], "skipped_off_topic"
                        )
                    else:
                        database.log_scanned(
                            tweet["id"], tweet["author"], "no_reply_generated"
                        )
                    continue

            if reply_text is None and qa_status == "SKIP_OFF_TOPIC":
                database.log_scanned(
                    tweet["id"], tweet["author"], "skipped_off_topic"
                )
                continue

            if not reply_text:
                database.log_scanned(
                    tweet["id"], tweet["author"], "no_reply_generated"
                )
                continue

            tw_url = _tweet_url(tweet["author"], tweet["id"])
            if not database.insert_pending_reply(
                tweet["id"],
                tw_url,
                tweet["author"],
                reply_text,
                approach_key or "",
                pattern_key or "",
            ):
                print(
                    f"[BOT] Pending row already exists for tweet {tweet['id']} — skip duplicate queue"
                )
                continue

            sent = telegram_bot.send_approval(
                tw_url,
                tweet["text"],
                reply_text,
                tweet["id"],
                tweet["author"],
                pattern_key=pattern_key,
                qa_status=qa_status if config.QA_ENABLED else None,
                qa_attempts=qa_attempts if config.QA_ENABLED else None,
            )
            if sent:
                queued += 1
            else:
                database.delete_pending_reply(tweet["id"])
                print(
                    f"[BOT] Telegram send failed — removed pending row for tweet {tweet['id']}"
                )

        print(
            f"[BOT] Cycle done. Queued for Telegram approval: {queued}. "
            f"Posted today (already on X): {database.replies_today()}/{config.MAX_REPLIES_PER_DAY}"
        )
    finally:
        database.record_scan_cycle_finished()


def main():
    parser = argparse.ArgumentParser(description="AlphaCycle X Bot")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan cycle then exit (good for smoke tests).",
    )
    parser.add_argument(
        "--queue-daily",
        action="store_true",
        help="Generate one daily post now and send Telegram approval (catch-up). Exits after.",
    )
    args = parser.parse_args()

    if args.queue_daily and args.once:
        print("[BOT] Use only one of --queue-daily or --once.")
        sys.exit(2)

    if args.queue_daily:
        if not logging.root.handlers:
            logging.basicConfig(level=logging.INFO, format="%(message)s")
        if not preflight_check():
            print("[BOT] Preflight failed — add secrets to .env next to config.py and retry.")
            sys.exit(1)
        database.init_db()
        _configure_schedule_utc()
        print("[BOT] --queue-daily: fetch ARC, generate post, queue Telegram approval...")
        schedule_daily_post()
        print("[BOT] --queue-daily finished.")
        return

    if not logging.root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("[BOT] AlphaCycle X Bot v2 starting...")
    print("[BOT] Config: .env auto-loaded from folder containing config.py (python-dotenv).")
    print("[BOT] Mode: replies + daily posts require Telegram approval (run telegram_listener.py).")
    print(f"[BOT] Tracking: {', '.join(config.TRACKED_ACCOUNTS)}")
    print(f"[BOT] Scan interval: {config.SCAN_INTERVAL_SECONDS}s (checked each 60s tick)")
    print(f"[BOT] Limits: {config.MAX_REPLIES_PER_HOUR}/hr, {config.MAX_REPLIES_PER_DAY}/day")
    print(f"[BOT] Delay: {config.REPLY_DELAY_MIN}-{config.REPLY_DELAY_MAX}s per reply")
    print(
        f"[BOT] Daily post: schedule {config.DAILY_POST_TIME} — on Linux UTC via TZ=UTC+tzset; "
        "else verify server timezone matches intent (10:00 BRT = 13:00 UTC)."
    )

    if not preflight_check():
        print("[BOT] Preflight failed — add secrets to .env next to config.py and retry.")
        sys.exit(1)

    database.init_db()
    database.set_bot_booted_now()
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

    _configure_schedule_utc()
    schedule.every().day.at(config.DAILY_POST_TIME).do(schedule_daily_post)
    print(
        f"[BOT] Daily post job registered: every day at {config.DAILY_POST_TIME} "
        "(local TZ; see note above for UTC)."
    )
    schedule.every().sunday.at("12:00").do(_weekly_banner_job)
    print("[BOT] Weekly banner job registered: every Sunday at 12:00 (process TZ; use UTC on Linux).")

    next_scan_at = 0.0
    while True:
        try:
            schedule.run_pending()
            now = time.monotonic()
            if now >= next_scan_at:
                try:
                    run_cycle()
                except Exception as e:
                    print(f"[BOT] Cycle error: {e}")
                next_scan_at = now + float(config.SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n[BOT] Stopped.")
            sys.exit(0)

        time.sleep(60)


if __name__ == "__main__":
    main()
