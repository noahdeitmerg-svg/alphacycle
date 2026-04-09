import os

# Strip: trailing newlines/spaces from .env or copy-paste break OAuth1 signatures (401).
TWITTER_API_KEY = (os.getenv("TWITTER_API_KEY", "") or "").strip()
TWITTER_API_SECRET = (os.getenv("TWITTER_API_SECRET", "") or "").strip()
TWITTER_ACCESS_TOKEN = (os.getenv("TWITTER_ACCESS_TOKEN", "") or "").strip()
TWITTER_ACCESS_SECRET = (os.getenv("TWITTER_ACCESS_SECRET", "") or "").strip()
TWITTER_BEARER = (os.getenv("TWITTER_BEARER", "") or "").strip()

CLAUDE_API_KEY = (os.getenv("CLAUDE_API_KEY", "") or "").strip()
CLAUDE_MODEL = "claude-sonnet-4-20250514"

ALPHACYCLE_API = "https://alphacycle-production.up.railway.app"

TRACKED_ACCOUNTS = [
    "WClementeIII",
    "RaoulGMI",
    "LynAldenContact",
    "100trillionUSD",
    "capaboreal",
    "TechDev_52",
    "CryptoCred",
    "DylanLeClair_",
]

MAX_REPLIES_PER_HOUR = 3
MAX_REPLIES_PER_DAY = 15
SCAN_INTERVAL_SECONDS = 600

REPLY_DELAY_MIN = 360
REPLY_DELAY_MAX = 1320

MIN_TWEET_AGE_SECONDS = 60
MAX_TWEET_AGE_SECONDS = 3600
MIN_LIKES_TO_REPLY = 5

DB_PATH = "database.db"
