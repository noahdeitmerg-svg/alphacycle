"""Resolve @handle to user id using Bearer (same as scanner). Usage: python3 resolve_user.py WClemente"""
import sys

import tweepy

import config


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 resolve_user.py USERNAME  (no @)")
        return 1
    name = sys.argv[1].strip().lstrip("@")
    if not config.TWITTER_BEARER:
        print("TWITTER_BEARER missing")
        return 1
    c = tweepy.Client(bearer_token=config.TWITTER_BEARER, wait_on_rate_limit=True)
    r = c.get_user(username=name)
    if r.data:
        print(f"username={r.data.username!r} id={r.data.id}")
        return 0
    print("errors:", getattr(r, "errors", r))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
