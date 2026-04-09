import time
import random
import tweepy
import config
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


def post_reply(tweet_id: str, author: str, reply_text: str) -> bool:
    # Rate limit check
    hourly = database.replies_last_hour()
    if hourly >= config.MAX_REPLIES_PER_HOUR:
        print(f"[POSTER] Hourly limit reached ({hourly}/{config.MAX_REPLIES_PER_HOUR})")
        return False

    daily = database.replies_today()
    if daily >= config.MAX_REPLIES_PER_DAY:
        print(f"[POSTER] Daily limit reached ({daily}/{config.MAX_REPLIES_PER_DAY})")
        return False

    # Random delay — looks human, avoids detection
    delay = random.randint(config.REPLY_DELAY_MIN, config.REPLY_DELAY_MAX)
    print(f"[POSTER] Waiting {delay}s before replying to @{author}...")
    time.sleep(delay)

    # Re-check limits after delay (another reply may have posted during wait)
    if database.replies_last_hour() >= config.MAX_REPLIES_PER_HOUR:
        print(f"[POSTER] Hourly limit reached after delay")
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
            print(f"[POSTER] Reply posted to @{author}: {reply_text[:60]}...")
            return True
        else:
            print(f"[POSTER] Twitter returned no data for reply to @{author}")
            return False

    except tweepy.TooManyRequests:
        print(f"[POSTER] Twitter rate limit hit — backing off")
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
        print(f"[POSTER] Twitter forbidden: {e}")
        return False
    except Exception as e:
        print(f"[POSTER] Error posting reply: {e}")
        return False
