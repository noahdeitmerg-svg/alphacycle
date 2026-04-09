"""
Manual OAuth 1.0a post test (same path as poster.post_reply).

Usage (from alphacycle-x-bot directory, with env vars set):
  python3 test_manual_reply.py

Requires: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
Optional first step: GET /2/users/me verifies user context before replying.
"""
import sys

import tweepy

import config


TWEET_ID = "2041208184392798550"
TEST_TEXT = "Manual OAuth test reply (debug)."


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
        print("Missing:", ", ".join(missing))
        return 1

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
        print("get_me 401 (fix OAuth keys before create_tweet):", e)
        if getattr(e, "response", None) is not None:
            print(getattr(e.response, "text", "")[:500])
        return 1

    try:
        r = client.create_tweet(
            text=TEST_TEXT,
            in_reply_to_tweet_id=TWEET_ID,
            user_auth=True,
        )
        print("create_tweet:", r)
    except tweepy.Unauthorized as e:
        print("create_tweet 401:", e)
        if getattr(e, "response", None) is not None:
            print(getattr(e.response, "text", "")[:500])
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
