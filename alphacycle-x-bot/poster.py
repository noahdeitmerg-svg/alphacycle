import logging
import random
import time
from datetime import datetime, timezone

import tweepy

import config
import daily_post_engine
import database
import growth_engine
import telegram_bot

_X_PUBLIC_HANDLE = "Real_AlphaCycle"
logger = logging.getLogger(__name__)


def _telegram_post_confirmation(text: str) -> None:
    """Best-effort; posting already succeeded on X."""
    body = (text or "")[:4096]
    if body:
        telegram_bot.send_feedback_message(body)


def oauth_user_credentials_ready() -> bool:
    """Posting uses OAuth 1.0a user context only (not the bearer token)."""
    return all(
        (
            config.TWITTER_API_KEY,
            config.TWITTER_API_SECRET,
            config.TWITTER_ACCESS_TOKEN,
            config.TWITTER_ACCESS_SECRET,
        )
    )


def get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=config.TWITTER_API_KEY,
        consumer_secret=config.TWITTER_API_SECRET,
        access_token=config.TWITTER_ACCESS_TOKEN,
        access_token_secret=config.TWITTER_ACCESS_SECRET,
        wait_on_rate_limit=True,
    )


def _enforce_rate_limits() -> bool:
    hourly = database.replies_last_hour()
    if hourly >= config.MAX_REPLIES_PER_HOUR:
        print(f"[POSTER] Hourly limit reached ({hourly}/{config.MAX_REPLIES_PER_HOUR})")
        return False

    daily = database.replies_today()
    if daily >= config.MAX_REPLIES_PER_DAY:
        print(f"[POSTER] Daily limit reached ({daily}/{config.MAX_REPLIES_PER_DAY})")
        return False
    return True


def post_reply(reply_text: str, tweet_author: str, tweet_id: str) -> bool:
    """Send reply to Telegram for manual posting. No X API attempt."""
    a = (tweet_author or "").strip().lstrip("@")
    tid = str(tweet_id or "").strip()
    info_msg = (
        "New Reply\n\n"
        f"Account: @{a}\n"
        f"Tweet: https://x.com/{a}/status/{tid}\n\n"
        "Tap tweet link, then paste reply below.\n\n"
        f"[MANUAL_REPLY] tweet_id={tid} author={a}"
    )
    ok1 = telegram_bot.send_feedback_message(info_msg)
    ok2 = telegram_bot.send_plain_message((reply_text or "").strip())
    if ok1 and ok2:
        logger.info("[POSTER] Reply sent to Telegram: @%s", a)
    else:
        logger.error("[POSTER] Telegram send failed ok1=%s ok2=%s @%s", ok1, ok2, a)
    return bool(ok1 and ok2)


def complete_approved_reply(tweet_id: str) -> str:
    """
    After Telegram POST: send two-part copy instructions, log reply, finalize pending.
    Returns \"telegram\" on success, \"failed\" otherwise. No X reply API call.
    """
    row = database.get_pending_by_tweet_id(tweet_id)
    if not row:
        print(f"[POSTER] No pending row for tweet_id={tweet_id}")
        return "failed"

    status = row["status"]
    if status == "skipped":
        print(f"[POSTER] Tweet {tweet_id} marked skipped — not sending")
        return "failed"
    if status == "posted":
        print(f"[POSTER] Tweet {tweet_id} already finalized")
        return "failed"
    if status not in ("pending", "approved"):
        print(f"[POSTER] Cannot finalize from status={status}")
        return "failed"

    author = row["username"]
    reply_text = row["reply_text"]
    approach = row.get("approach") or ""
    pattern = row.get("pattern") or ""

    if status == "pending":
        if not database.try_transition_pending_status(tweet_id, "pending", "approved"):
            row2 = database.get_pending_by_tweet_id(tweet_id)
            if not row2 or row2["status"] != "approved":
                print(f"[POSTER] Could not lock pending row for tweet_id={tweet_id}")
                return "failed"

    if not post_reply(reply_text, author, tweet_id):
        database.try_transition_pending_status(tweet_id, "approved", "pending")
        return "failed"

    database.log_reply(tweet_id, author, reply_text)
    database.insert_reply_history(reply_text, author, approach or "", pattern or "")
    database.increment_reply_stat("paste")
    database.set_pending_status(tweet_id, "posted")
    logger.info("[POSTER] @%s reply finalized (Telegram handoff) tweet_id=%s", author, tweet_id)
    return "telegram"


def _arc_score_int_for_save_topic(row: dict) -> int | None:
    """ARC at queue time from pending row; else one fresh fetch_arc_data for save_topic."""
    v = row.get("arc_score")
    if v is not None and v != "":
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            pass
    arc = daily_post_engine.fetch_arc_data()
    if not arc:
        return None
    raw = arc.get("arc_score")
    if raw is None:
        return None
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def post_daily_post(pending_id: str) -> bool:
    """
    Post an approved daily original tweet (Telegram dpost: button).
    Does not use in_reply_to; records topic via record_daily_post_topic on success.
    """
    row = database.get_pending_daily_post(pending_id)
    if not row:
        print(f"[POSTER] No pending daily post for id={pending_id}")
        return False

    status = row["status"]
    if status == "skipped":
        print(f"[POSTER] Daily post {pending_id} skipped — not posting")
        return False
    if status == "posted":
        print(f"[POSTER] Daily post {pending_id} already posted")
        return False
    if status not in ("pending", "approved"):
        print(f"[POSTER] Cannot post daily from status={status}")
        return False

    post_text = (row["post_text"] or "").strip()
    if not post_text:
        print("[POSTER] Empty daily post text")
        return False

    if status == "pending":
        if not database.try_transition_daily_status(pending_id, "pending", "approved"):
            row2 = database.get_pending_daily_post(pending_id)
            if not row2 or row2["status"] != "approved":
                print(f"[POSTER] Could not lock daily pending id={pending_id}")
                return False

    if not _enforce_rate_limits():
        database.try_transition_daily_status(pending_id, "approved", "pending")
        return False

    delay = random.randint(30, 120)
    print(f"[POSTER] Waiting {delay}s before daily post...")
    time.sleep(delay)

    if not _enforce_rate_limits():
        print("[POSTER] Hourly or daily limit reached after delay (daily)")
        database.try_transition_daily_status(pending_id, "approved", "pending")
        return False

    if not oauth_user_credentials_ready():
        print("[POSTER] OAuth missing — cannot post daily")
        database.try_transition_daily_status(pending_id, "approved", "pending")
        return False

    text = post_text
    if len(text) > 280:
        text = text[:277] + "..."

    MAX_REPLY_CHARS = 260
    if text and len(text) > MAX_REPLY_CHARS:
        logger.warning(f"[HARD_LIMIT] Reply too long: {len(text)} chars. Truncating.")
        truncated = text[:257]
        last_period = truncated.rfind(".")
        last_dash = truncated.rfind("—")
        cut_point = max(last_period, last_dash)
        if cut_point > 150:
            text = text[: cut_point + 1]
        else:
            text = truncated.rsplit(" ", 1)[0].rstrip() + "..."

    try:
        client = get_client()
        response = client.create_tweet(text=text, user_auth=True)

        if response.data:
            new_id = getattr(response.data, "id", None)
            if new_id is None and isinstance(response.data, dict):
                new_id = response.data.get("id")
            new_id_str = str(new_id) if new_id is not None else ""
            database.record_daily_post_topic(
                daily_post_engine.topic_snippet_from_post(text),
                post_preview=text[:2000],
            )
            pt = (row.get("post_type") or "").strip()
            if not pt:
                wd = datetime.now(timezone.utc).weekday()
                pt = growth_engine.POST_TYPE_BY_WEEKDAY[wd % 7]
            summary = daily_post_engine.summarize_post_one_sentence(post_text)
            if not summary:
                summary = daily_post_engine.topic_snippet_from_post(
                    post_text, max_len=220
                )
            arc_for_topic = _arc_score_int_for_save_topic(row)
            database.save_topic(
                post_text=post_text,
                post_type=pt,
                arc_score=arc_for_topic,
                topic_summary=summary
                or daily_post_engine.topic_snippet_from_post(post_text, max_len=200),
            )
            database.set_pending_daily_status(pending_id, "posted")
            print(f"[POSTER] Daily post published: {text[:60]}...")
            print(f"[LOG] daily post posted pending_id={pending_id}")
            if new_id_str:
                _telegram_post_confirmation(
                    "\u2705 Daily post live\n{}\nLink: https://x.com/{}/status/{}".format(
                        text, _X_PUBLIC_HANDLE, new_id_str
                    )
                )
            return True
        print("[POSTER] Twitter returned no data for daily post")
        database.try_transition_daily_status(pending_id, "approved", "pending")
        return False

    except tweepy.TooManyRequests:
        print("[POSTER] Twitter rate limit (daily post)")
        database.try_transition_daily_status(pending_id, "approved", "pending")
        return False
    except tweepy.Unauthorized as e:
        print(f"[POSTER] 401 Unauthorized (daily post): {e}")
        database.try_transition_daily_status(pending_id, "approved", "pending")
        return False
    except tweepy.Forbidden as e:
        print(f"[POSTER] 403 Forbidden (daily post): {e}")
        database.try_transition_daily_status(pending_id, "approved", "pending")
        return False
    except Exception as e:
        print(f"[POSTER] Error posting daily tweet: {e}")
        database.try_transition_daily_status(pending_id, "approved", "pending")
        return False
