import tweepy
from datetime import datetime, timezone
import config
import database


def get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=config.TWITTER_BEARER,
        consumer_key=config.TWITTER_API_KEY,
        consumer_secret=config.TWITTER_API_SECRET,
        access_token=config.TWITTER_ACCESS_TOKEN,
        access_token_secret=config.TWITTER_ACCESS_SECRET,
        wait_on_rate_limit=True,
    )


def get_latest_tweets(username: str, client: tweepy.Client) -> list[dict]:
    try:
        user = client.get_user(username=username)
        if not user.data:
            errs = getattr(user, "errors", None) or []
            if errs:
                print(f"[SCANNER] User @{username}: API errors: {errs}")
            else:
                print(f"[SCANNER] User @{username} not found (wrong handle, suspended, or renamed)")
            return []

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
                "author": username,
                "text": tweet.text,
                "likes": likes,
                "age_seconds": int(age),
            })

        return results

    except Exception as e:
        print(f"[SCANNER] Error fetching @{username}: {e}")
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
