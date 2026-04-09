"""
Post one standalone tweet (no reply). Verifies OAuth write.

Usage:
  python3 post_test_tweet.py
  python3 post_test_tweet.py "Your optional text here"
"""
import sys

import tweepy

import config


def main() -> int:
    missing = [
        n
        for n, v in [
            ("TWITTER_API_KEY", config.TWITTER_API_KEY),
            ("TWITTER_API_SECRET", config.TWITTER_API_SECRET),
            ("TWITTER_ACCESS_TOKEN", config.TWITTER_ACCESS_TOKEN),
            ("TWITTER_ACCESS_SECRET", config.TWITTER_ACCESS_SECRET),
        ]
        if not v
    ]
    if missing:
        print("Missing:", ", ".join(missing), "-- check .env next to config.py")
        return 1

    text = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else "AlphaCycle bot — write test (standalone)."
    text = text[:280]

    client = tweepy.Client(
        consumer_key=config.TWITTER_API_KEY,
        consumer_secret=config.TWITTER_API_SECRET,
        access_token=config.TWITTER_ACCESS_TOKEN,
        access_token_secret=config.TWITTER_ACCESS_SECRET,
        wait_on_rate_limit=True,
    )

    try:
        me = client.get_me(user_auth=True)
        print("get_me:", me)
    except tweepy.Unauthorized as e:
        print("get_me 401:", e)
        return 1

    try:
        r = client.create_tweet(text=text, user_auth=True)
        print("create_tweet:", r)
    except tweepy.Unauthorized as e:
        print("create_tweet 401:", e)
        return 1
    except tweepy.Forbidden as e:
        print("create_tweet 403:", e)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
