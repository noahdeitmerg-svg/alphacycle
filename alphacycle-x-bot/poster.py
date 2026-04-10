import time
import random
from datetime import datetime, timezone

import requests
import tweepy
import config
import daily_post_engine
import database
import growth_engine
import telegram_bot

_X_PUBLIC_HANDLE = "Real_AlphaCycle"


def _telegram_post_confirmation(text: str) -> None:
    """Best-effort; posting already succeeded on X."""
    body = (text or "")[:4096]
    if body:
        telegram_bot.send_feedback_message(body)


def _send_manual_copy_paste(author: str, tweet_id: str, reply_text: str) -> None:
    a = (author or "").strip().lstrip("@")
    txt = (reply_text or "").strip()
    body = (
        "⚠️ API blocked — manual post needed\n\n"
        f"Reply to: @{a}\n"
        f"Tweet: https://x.com/{a}/status/{tweet_id}\n\n"
        "Copy this reply:\n"
        "─────────────────\n"
        f"{txt}\n"
        "─────────────────\n\n"
        "Tap the tweet link, paste the reply, done.\n\n"
        f"[MANUAL_REPLY] tweet_id={tweet_id} author={a}"
    )
    body = body[:4096]
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": body,
    }
    try:
        requests.post(url, json=payload, timeout=30)
    except Exception as e:
        print(f"[POSTER] Telegram manual fallback send failed: {e}")


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


def _post_reply_impl(tweet_id: str, author: str, reply_text: str, approach: str = "") -> str:
    """Create tweet reply and persist to replies table (used after approval)."""
    if not _enforce_rate_limits():
        return "failed"

    delay = random.randint(config.REPLY_DELAY_MIN, config.REPLY_DELAY_MAX)
    print(f"[POSTER] Waiting {delay}s before replying to @{author}...")
    time.sleep(delay)

    if not _enforce_rate_limits():
        print("[POSTER] Hourly or daily limit reached after delay")
        return "failed"

    if not oauth_user_credentials_ready():
        print(
            "[POSTER] OAuth 1.0a user credentials missing (API key/secret + access token/secret). "
            "Scanner can still work with TWITTER_BEARER only; posting cannot."
        )
        database.mark_api_blocked_account(author)
        _send_manual_copy_paste(author, tweet_id, reply_text)
        print(f"[POSTER] API blocked for @{author}, sent to Telegram for manual post")
        return "manual"

    try:
        client = get_client()
        response = client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=str(tweet_id),
            user_auth=True,
        )

        if response.data:
            new_id = getattr(response.data, "id", None)
            if new_id is None and isinstance(response.data, dict):
                new_id = response.data.get("id")
            new_id_str = str(new_id) if new_id is not None else ""
            database.log_reply(tweet_id, author, reply_text)
            database.insert_reply_history(reply_text, author, approach or "")
            print(f"[POSTER] Reply posted to @{author}: {reply_text[:60]}...")
            print(f"[LOG] reply posted tweet_id={tweet_id}")
            if new_id_str:
                _telegram_post_confirmation(
                    "\u2705 Posted reply to @{}\n{}\nLink: https://x.com/{}/status/{}".format(
                        author, reply_text, _X_PUBLIC_HANDLE, new_id_str
                    )
                )
            database.remove_api_blocked_account(author)
            return "posted"
        print(f"[POSTER] Twitter returned no data for reply to @{author}")
        database.mark_api_blocked_account(author)
        _send_manual_copy_paste(author, tweet_id, reply_text)
        print(f"[POSTER] API blocked for @{author}, sent to Telegram for manual post")
        return "manual"

    except tweepy.TooManyRequests:
        print("[POSTER] Twitter rate limit hit — backing off")
        database.mark_api_blocked_account(author)
        _send_manual_copy_paste(author, tweet_id, reply_text)
        print(f"[POSTER] API blocked for @{author}, sent to Telegram for manual post")
        return "manual"
    except tweepy.Unauthorized as e:
        detail = ""
        if getattr(e, "response", None) is not None:
            try:
                detail = e.response.text[:500]
            except Exception:
                detail = str(e.response)
        print(f"[POSTER] 401 Unauthorized (OAuth 1.0a user context): {e}")
        if detail:
            print(f"[POSTER] Response body: {detail}")
        print(
            "[POSTER] Check: (1) TWITTER_API_KEY + TWITTER_API_SECRET set in this same process/shell "
            "(e.g. screen session exports). (2) Access token + secret belong to THIS app and were "
            "regenerated after enabling Read and Write. (3) No wrong copy-paste / extra whitespace."
        )
        database.mark_api_blocked_account(author)
        _send_manual_copy_paste(author, tweet_id, reply_text)
        print(f"[POSTER] API blocked for @{author}, sent to Telegram for manual post")
        return "manual"
    except tweepy.Forbidden as e:
        detail = ""
        if getattr(e, "response", None) is not None:
            try:
                detail = e.response.text[:600]
            except Exception:
                detail = str(e.response)
        print(f"[POSTER] 403 Forbidden (X policy, not OAuth): {e}")
        if detail:
            print(f"[POSTER] Response body: {detail}")
        print(
            "[POSTER] Common cause: reply to a tweet where @you was not mentioned / no prior engagement. "
            "Try another candidate or a standalone tweet for testing."
        )
        database.mark_api_blocked_account(author)
        _send_manual_copy_paste(author, tweet_id, reply_text)
        print(f"[POSTER] API blocked for @{author}, sent to Telegram for manual post")
        return "manual"
    except Exception as e:
        print(f"[POSTER] Error posting reply: {e}")
        database.mark_api_blocked_account(author)
        _send_manual_copy_paste(author, tweet_id, reply_text)
        print(f"[POSTER] API blocked for @{author}, sent to Telegram for manual post")
        return "manual"


def post_reply(tweet_id: str) -> str:
    """
    Post a reply for an approved pending row (Telegram POST button).
    Loads reply text and author from pending_replies; enforces hourly/daily limits.
    """
    row = database.get_pending_by_tweet_id(tweet_id)
    if not row:
        print(f"[POSTER] No pending row for tweet_id={tweet_id}")
        return "failed"

    status = row["status"]
    if status == "skipped":
        print(f"[POSTER] Tweet {tweet_id} marked skipped — not posting")
        return "failed"
    if status == "posted":
        print(f"[POSTER] Tweet {tweet_id} already posted")
        return "failed"
    if status not in ("pending", "approved"):
        print(f"[POSTER] Cannot post from status={status}")
        return "failed"

    author = row["username"]
    reply_text = row["reply_text"]
    approach = row.get("approach") or ""

    if status == "pending":
        if not database.try_transition_pending_status(tweet_id, "pending", "approved"):
            row2 = database.get_pending_by_tweet_id(tweet_id)
            if not row2 or row2["status"] != "approved":
                print(f"[POSTER] Could not lock pending row for tweet_id={tweet_id}")
                return "failed"

    if database.is_api_blocked_recent(author, days=7):
        database.touch_api_blocked_attempt(author)
        _send_manual_copy_paste(author, tweet_id, reply_text)
        print(f"[POSTER] API blocked for @{author}, sent to Telegram for manual post")
        return "manual"

    result = _post_reply_impl(tweet_id, author, reply_text, approach)
    if result == "posted":
        database.set_pending_status(tweet_id, "posted")
    elif result == "manual":
        database.try_transition_pending_status(tweet_id, "approved", "pending")
    else:
        database.try_transition_pending_status(tweet_id, "approved", "pending")
    return result


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
