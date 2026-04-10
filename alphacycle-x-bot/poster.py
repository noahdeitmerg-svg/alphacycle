import time
import random
import tweepy
import config
import daily_post_engine
import database


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


def _post_reply_impl(
    tweet_id: str, author: str, reply_text: str, approach: str = ""
) -> bool:
    """Create tweet reply and persist to replies table (used after approval)."""
    if not _enforce_rate_limits():
        return False

    delay = random.randint(config.REPLY_DELAY_MIN, config.REPLY_DELAY_MAX)
    print(f"[POSTER] Waiting {delay}s before replying to @{author}...")
    time.sleep(delay)

    if not _enforce_rate_limits():
        print("[POSTER] Hourly or daily limit reached after delay")
        return False

    if not oauth_user_credentials_ready():
        print(
            "[POSTER] OAuth 1.0a user credentials missing (API key/secret + access token/secret). "
            "Scanner can still work with TWITTER_BEARER only; posting cannot."
        )
        return False

    try:
        client = get_client()
        response = client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=str(tweet_id),
            user_auth=True,
        )

        if response.data:
            database.log_reply(tweet_id, author, reply_text)
            database.insert_reply_history(reply_text, author, approach or "")
            print(f"[POSTER] Reply posted to @{author}: {reply_text[:60]}...")
            print(f"[LOG] reply posted tweet_id={tweet_id}")
            return True
        print(f"[POSTER] Twitter returned no data for reply to @{author}")
        return False

    except tweepy.TooManyRequests:
        print("[POSTER] Twitter rate limit hit — backing off")
        return False
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
        return False
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
        return False
    except Exception as e:
        print(f"[POSTER] Error posting reply: {e}")
        return False


def post_reply(tweet_id: str) -> bool:
    """
    Post a reply for an approved pending row (Telegram POST button).
    Loads reply text and author from pending_replies; enforces hourly/daily limits.
    """
    row = database.get_pending_by_tweet_id(tweet_id)
    if not row:
        print(f"[POSTER] No pending row for tweet_id={tweet_id}")
        return False

    status = row["status"]
    if status == "skipped":
        print(f"[POSTER] Tweet {tweet_id} marked skipped — not posting")
        return False
    if status == "posted":
        print(f"[POSTER] Tweet {tweet_id} already posted")
        return False
    if status not in ("pending", "approved"):
        print(f"[POSTER] Cannot post from status={status}")
        return False

    author = row["username"]
    reply_text = row["reply_text"]
    approach = row.get("approach") or ""

    if status == "pending":
        if not database.try_transition_pending_status(tweet_id, "pending", "approved"):
            row2 = database.get_pending_by_tweet_id(tweet_id)
            if not row2 or row2["status"] != "approved":
                print(f"[POSTER] Could not lock pending row for tweet_id={tweet_id}")
                return False

    ok = _post_reply_impl(tweet_id, author, reply_text, approach)
    if ok:
        database.set_pending_status(tweet_id, "posted")
    else:
        database.try_transition_pending_status(tweet_id, "approved", "pending")
    return ok


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
            database.record_daily_post_topic(
                daily_post_engine.topic_snippet_from_post(text),
                post_preview=text[:2000],
            )
            database.set_pending_daily_status(pending_id, "posted")
            print(f"[POSTER] Daily post published: {text[:60]}...")
            print(f"[LOG] daily post posted pending_id={pending_id}")
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
