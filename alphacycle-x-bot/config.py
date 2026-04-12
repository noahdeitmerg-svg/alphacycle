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
# screen -S <name> for /logbot and /logtg (Telegram tail of scrollback via hardcopy -h).
SCREEN_SESSION_BOT = (os.getenv("SCREEN_SESSION_BOT", "xbot") or "xbot").strip()
SCREEN_SESSION_TG = (os.getenv("SCREEN_SESSION_TG", "tg") or "tg").strip()

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

# Structural reply patterns (rotate with approaches; weights sum ~1.0)
REPLY_PATTERNS = {
    "contrarian_insight_hook": 0.25,
    "cycle_reframe": 0.30,
    "historical_memory": 0.25,
    "structural_insight": 0.20,
}

# Claude Model
CLAUDE_MODEL = "claude-sonnet-4-20250514"
# Daily post only: if Sonnet returns 529 overloaded, try this model immediately (often different capacity).
# Set CLAUDE_MODEL_DAILY_FALLBACK=none (or off/false/0) to disable fallback (primary + long sleeps only).
_CLAUDE_FB = (os.getenv("CLAUDE_MODEL_DAILY_FALLBACK") or "").strip()
if _CLAUDE_FB.lower() in ("none", "off", "false", "0"):
    CLAUDE_MODEL_DAILY_FALLBACK = ""
elif _CLAUDE_FB:
    CLAUDE_MODEL_DAILY_FALLBACK = _CLAUDE_FB
else:
    CLAUDE_MODEL_DAILY_FALLBACK = "claude-3-5-haiku-20241022"

# ============================================================
# TRACKED ACCOUNTS — AlphaCycle Reply Targets
# 50 Accounts total (10 + 20 + 20 — not 60; tiers sum to 50).
# Read budget: default SCAN_INTERVAL_SECONDS=3600 (60 min) => 50*24=1200 timeline reads/day.
#   Override in .env (e.g. 1800) if X read credits allow shorter interval.
# ============================================================

TIER_1_ACCOUNTS = [
    "RaoulGMI",
    "LynAldenContact",
    "APompliano",
    "nic_carter",
    "CryptoHayes",
    "WClemente",
    "krugermacro",
    "willywoo",
    "BitcoinMagazine",
    "GlassnodeAlerts",
]

TIER_2_ACCOUNTS = [
    "_Checkmatey_",
    "DylanLeClair",
    "LukeGromen",
    "JeffBooth",
    "PrestonPysh",
    "danheld",
    "100trillionUSD",
    "MartyBent",
    "ErikVoorhees",
    "balaji",
    "FossGregfoss",
    "real_vijay",
    "MarkYusko",
    "LawrenceLepard",
    "TuurDemeester",
    "KevinSvenson",
    "JurrienTimmer",
    "DoctorProfit",
    "JSeyff",
    "cburniske",
]

TIER_3_ACCOUNTS = [
    "CryptoCon_",
    "TechDev_52",
    "in2cryptoversee",
    "TheRealPlanC",
    "therationalroot",
    "VentureCoinist",
    "MacroAlf",
    "TXMCtrades",
    "GameofTrades_",
    "fejau_inc",
    "PositiveCrypto",
    "CryptoCred",
    "milesdeutscher",
    "MacroScope17",
    "Trader_XO",
    "stackhodler",
    "ecoinometrics",
    "coinmetrics",
    "MacroCharts",
    "KobeissiLetter",
]

TRACKED_ACCOUNTS = TIER_1_ACCOUNTS + TIER_2_ACCOUNTS + TIER_3_ACCOUNTS

# Verify: len(TRACKED_ACCOUNTS) == 50 (10 + 20 + 20)

# Temporarily empty for higher reply throughput during testing; restore list to tighten.
BLOCKED_KEYWORDS: list = []

# Reply rate caps (also referenced as REPLY_LIMIT_* in docs).
MAX_REPLIES_PER_HOUR = 10
MAX_REPLIES_PER_DAY = 30
# Default 3600 = 60 min between scan cycles (50 tracked accounts; override SCAN_INTERVAL_SECONDS in .env for 30 min).
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "3600"))

REPLY_DELAY_MIN = 30
REPLY_DELAY_MAX = 120

MIN_TWEET_AGE_SECONDS = int(os.getenv("MIN_TWEET_AGE_SECONDS", "60"))
# Wider window = more candidates (Telegram /scan can still yield 0 if all tweets are old/low-likes/spaced-out).
MAX_TWEET_AGE_SECONDS = int(os.getenv("MAX_TWEET_AGE_SECONDS", "21600"))
MIN_LIKES_TO_REPLY = int(os.getenv("MIN_LIKES_TO_REPLY", "0"))

DB_PATH = str(_BASE_DIR / "database.db")
