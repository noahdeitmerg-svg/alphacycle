import logging
from datetime import datetime, timezone

import tweepy

import config
import database

logger = logging.getLogger(__name__)


def _tweet_has_blocked_keyword(tweet_text: str) -> bool:
    t = (tweet_text or "").lower()
    for kw in config.BLOCKED_KEYWORDS:
        s = (kw or "").strip()
        if s and s.lower() in t:
            return True
    return False


def get_client() -> tweepy.Client:
    # Reads (get_user, user timeline) use Bearer by default (user_auth=False).
    # Do not pass OAuth1 here: invalid user keys can break lookups; Bearer is enough for public data.
    if not config.TWITTER_BEARER:
        raise RuntimeError("TWITTER_BEARER missing — scanner cannot run.")
    return tweepy.Client(
        bearer_token=config.TWITTER_BEARER,
        wait_on_rate_limit=True,
    )


def _fetch_user(client: tweepy.Client, account_spec: str):
    """
    account_spec: Twitter handle (no @) OR 'id:123456789' when username lookup returns not-found
    (handles renames / API quirks).
    """
    spec = (account_spec or "").strip()
    if spec.lower().startswith("id:"):
        uid = spec[3:].strip()
        if not uid.isdigit():
            print(f"[SCANNER] Invalid id spec (need digits): {account_spec!r}")
            return None, spec
        return client.get_user(id=uid), spec
    return client.get_user(username=spec), spec


def get_latest_tweets(account_spec: str, client: tweepy.Client) -> list[dict]:
    try:
        user, spec = _fetch_user(client, account_spec)
        if not user.data:
            errs = getattr(user, "errors", None) or []
            if errs:
                print(f"[SCANNER] User {spec!r}: API errors: {errs}")
            else:
                print(f"[SCANNER] User {spec!r} not found (wrong handle, suspended, or renamed)")
            return []

        handle = (user.data.username or spec).strip()
        tweets = client.get_users_tweets(
            user.data.id,
            max_results=5,
            tweet_fields=["created_at", "public_metrics"],
            exclude=["retweets", "replies"],
        )

        if not tweets.data:
            return []

        now = datetime.now(timezone.utc)
        results = []

        for tweet in tweets.data:
            age = (now - tweet.created_at).total_seconds()

            if age < config.MIN_TWEET_AGE_SECONDS:
                logger.info(
                    "[SCANNER] Skipped @%s: too_recent (age=%ds, min=%ds)",
                    handle,
                    int(age),
                    config.MIN_TWEET_AGE_SECONDS,
                )
                continue
            if age > config.MAX_TWEET_AGE_SECONDS:
                logger.info(
                    "[SCANNER] Skipped @%s: too_old (age=%ds, max=%ds)",
                    handle,
                    int(age),
                    config.MAX_TWEET_AGE_SECONDS,
                )
                continue

            likes = tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0
            if likes < config.MIN_LIKES_TO_REPLY:
                logger.info(
                    "[SCANNER] Skipped @%s: low_likes (likes=%s, min=%s)",
                    handle,
                    likes,
                    config.MIN_LIKES_TO_REPLY,
                )
                continue

            results.append({
                "id": str(tweet.id),
                "author": handle,
                "text": tweet.text,
                "likes": likes,
                "age_seconds": int(age),
            })

        return results

    except Exception as e:
        print(f"[SCANNER] Error fetching {account_spec!r}: {e}")
        return []


def scan_tweets() -> list[dict]:
    client = get_client()
    candidates = []

    for account in config.TRACKED_ACCOUNTS:
        tweets = get_latest_tweets(account, client)

        for tweet in tweets:
            author = tweet["author"]
            if _tweet_has_blocked_keyword(tweet["text"]):
                logger.info("[SCANNER] Skipped @%s: blocked_keyword", author)
                database.log_scanned(
                    tweet["id"], author, "blocked_keyword"
                )
                continue
            if database.already_scanned(tweet["id"]):
                logger.info("[SCANNER] Skipped @%s: already_scanned", author)
                continue
            if database.already_replied(tweet["id"]):
                logger.info("[SCANNER] Skipped @%s: already_replied", author)
                database.log_scanned(tweet["id"], author, "already_replied")
                continue
            if not database.is_author_spacing_ok_for_reply(author):
                logger.info("[SCANNER] Skipped @%s: same_account_limit (author_spacing)", author)
                database.log_scanned(
                    tweet["id"], author, "author_spacing"
                )
                continue
            if (
                database.count_replies_to_author_today_utc(author)
                >= config.MAX_REPLIES_PER_ACCOUNT_PER_DAY
            ):
                logger.info("[SCANNER] Skipped @%s: same_account_limit (daily_reply_limit)", author)
                database.log_scanned(
                    tweet["id"], author, "daily_reply_limit"
                )
                continue

            database.log_scanned(tweet["id"], author)
            candidates.append(tweet)

    n_accounts = len(config.TRACKED_ACCOUNTS)
    print(
        f"[SCANNER] Scanned {n_accounts} accounts, {len(candidates)} candidates "
        f"(tweet window: {config.MIN_TWEET_AGE_SECONDS}s–{config.MAX_TWEET_AGE_SECONDS}s, "
        f"min likes {config.MIN_LIKES_TO_REPLY})"
    )
    return candidates
