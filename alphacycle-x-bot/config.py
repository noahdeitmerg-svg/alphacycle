import os
from pathlib import Path

from dotenv import load_dotenv

# Same directory as this file (works no matter what cwd is when starting bot.py).
_BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = _BASE_DIR / ".env"
# Use override=True so .env wins over empty exports (export TWITTER_API_KEY= blocks dotenv otherwise).
# utf-8-sig strips BOM from editors that save "UTF-8 with BOM" (would break first key otherwise).
load_dotenv(ENV_FILE, override=True, encoding="utf-8-sig")

# Strip: trailing newlines/spaces from .env or copy-paste break OAuth1 signatures (401).
TWITTER_API_KEY = (os.getenv("TWITTER_API_KEY", "") or "").strip()
TWITTER_API_SECRET = (os.getenv("TWITTER_API_SECRET", "") or "").strip()
TWITTER_ACCESS_TOKEN = (os.getenv("TWITTER_ACCESS_TOKEN", "") or "").strip()
TWITTER_ACCESS_SECRET = (os.getenv("TWITTER_ACCESS_SECRET", "") or "").strip()
TWITTER_BEARER = (os.getenv("TWITTER_BEARER", "") or "").strip()

CLAUDE_API_KEY = (os.getenv("CLAUDE_API_KEY", "") or "").strip()

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN", "") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID", "") or "").strip()

# AlphaCycle API: must be JSON (FastAPI). alphacycle.app/api/* often serves the SPA (HTML) — use Railway.
_DEFAULT_ARC_API_URL = "https://alphacycle-production.up.railway.app/api/arc-summary"
ARC_API_URL = (
    (os.getenv("ARC_API_URL", _DEFAULT_ARC_API_URL) or "").strip()
    or _DEFAULT_ARC_API_URL
)
ALPHACYCLE_API = "https://alphacycle-production.up.railway.app"
# Fallback host if ARC_API_URL is empty/malformed; ancillary GETs use host parsed from ARC_API_URL first.
ALPHACYCLE_PUBLIC_BASE = (
    os.getenv("ALPHACYCLE_PUBLIC_BASE", "https://alphacycle-production.up.railway.app")
    or ""
).strip().rstrip("/")
DAILY_POST_DASHBOARD_URL = (os.getenv("DAILY_POST_DASHBOARD_URL", "https://alphacycle.app") or "").strip()

# Daily Post Schedule (UTC)
DAILY_POST_TIME = "13:00"

# Growth Engine Settings
REPLY_HOOK_PROBABILITY = 0.4  # 40% = ca. 2 von 5
MAX_REPLY_HISTORY = 10
TOPIC_LOOKBACK_DAYS = 7

# Claude Model
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ============================================================
# TRACKED ACCOUNTS — AlphaCycle Reply Targets
# 25 Accounts total. Budget: ~1200 API calls/day at 30min intervals.
# ============================================================

TIER_1_ACCOUNTS = [
    "RaoulGMI",
    "LynAldenContact",
    "KobeissiLetter",
    "100trillionUSD",
    "WClemente",
]

TIER_2_ACCOUNTS = [
    "_Checkmatey_",
    "in2cryptoversee",
    "DylanLeClair",
    "CryptoCon_",
    "TechDev_52",
    "PositiveCrypto",
    "willywoo",
    "ecoinometrics",
    "coinmetrics",
    "stackhodler",
    "therationalroot",
    "BitcoinMagazine",
]

TIER_3_ACCOUNTS = [
    "TXMCtrades",
    "MacroCharts",
    "GameofTrades_",
    "fejau_inc",
    "CryptoHayes",
    "cburniske",
    "GlassnodeAlerts",
    "MacroAlf",
]

# Combined list for scanner
TRACKED_ACCOUNTS = TIER_1_ACCOUNTS + TIER_2_ACCOUNTS + TIER_3_ACCOUNTS

# Blocked keywords — skip tweets containing these
BLOCKED_KEYWORDS = [
    "LFG", "wagmi", "to the moon", "100x", "1000x",
    "BUY NOW", "FULL SEND", "PARABOLIC", "PUMP",
    "giveaway", "airdrop", "presale", "whitelist",
    "JOIN NOW", "FREE MINT", "LAST CHANCE",
]

MAX_REPLIES_PER_HOUR = 5
MAX_REPLIES_PER_DAY = 20
# Default 1800 = 30 min between scan cycles (saves X API read credits). Override in .env.
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "1800"))

REPLY_DELAY_MIN = 360
REPLY_DELAY_MAX = 1320

MIN_TWEET_AGE_SECONDS = 60
MAX_TWEET_AGE_SECONDS = 3600
MIN_LIKES_TO_REPLY = int(os.getenv("MIN_LIKES_TO_REPLY", "5"))

DB_PATH = str(_BASE_DIR / "database.db")
