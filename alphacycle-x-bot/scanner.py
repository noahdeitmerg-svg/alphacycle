import tweepy
from datetime import datetime, timezone
import config
import database


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
                continue
            if age > config.MAX_TWEET_AGE_SECONDS:
                continue

            likes = tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0
            if likes < config.MIN_LIKES_TO_REPLY:
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
            if database.already_scanned(tweet["id"]):
                continue
            if database.already_replied(tweet["id"]):
                database.log_scanned(tweet["id"], tweet["author"], "already_replied")
                continue

            database.log_scanned(tweet["id"], tweet["author"])
            candidates.append(tweet)

    print(f"[SCANNER] Scanned {len(config.TRACKED_ACCOUNTS)} accounts, {len(candidates)} candidates")
    return candidates
