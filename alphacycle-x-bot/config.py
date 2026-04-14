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


def _parse_telegram_allowed_chat_ids(raw: str) -> tuple[str, ...]:
    """Comma or semicolon separated chat ids (private DM, group, supergroup). No spaces issues: strip each."""
    out: list[str] = []
    for part in (raw or "").replace(";", ",").split(","):
        s = part.strip()
        if s:
            out.append(s)
    return tuple(out)


_telegram_chat_raw = (os.getenv("TELEGRAM_CHAT_ID", "") or "").strip()
TELEGRAM_ALLOWED_CHAT_IDS: tuple[str, ...] = _parse_telegram_allowed_chat_ids(_telegram_chat_raw)
# First id: default target for outbound approvals / summaries when send_* omits chat_id.
TELEGRAM_CHAT_ID = TELEGRAM_ALLOWED_CHAT_IDS[0] if TELEGRAM_ALLOWED_CHAT_IDS else ""
# Optional: @username without @ for mention detection; if empty, telegram_listener uses getMe once.
TELEGRAM_BOT_USERNAME = (os.getenv("TELEGRAM_BOT_USERNAME", "") or "").strip().lstrip("@")
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
MAX_REPLY_HISTORY = 5
# Sonnet reply clip + growth_engine Telegram hard cap (same as reply_system / QA)
MAX_REPLY_GENERATION_CHARS = max(
    1, int((os.getenv("MAX_REPLY_GENERATION_CHARS", "260") or "260").strip())
)
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

# Pre-Telegram QA: second Claude call (Haiku) on generated reply
_QA_ENV = (os.getenv("QA_ENABLED", "true") or "").strip().lower()
QA_ENABLED = _QA_ENV not in ("0", "false", "no", "off")
QA_MODEL = (os.getenv("QA_MODEL") or "claude-haiku-4-5-20251001").strip() or "claude-haiku-4-5-20251001"
QA_MAX_ATTEMPTS = max(1, int(os.getenv("QA_MAX_ATTEMPTS", "3") or "3"))

# ============================================================
# TRACKED ACCOUNTS — AlphaCycle Reply Targets
# 41 Accounts total (10 + 16 + 15). Cleaned 2026-04-13.
# Read budget: default SCAN_INTERVAL_SECONDS=3600 (60 min) => 41*24 timeline reads/day.
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
    "FossGregfoss",
    "real_vijay",
    "MarkYusko",
    "LawrenceLepard",
    "TuurDemeester",
    "TimmerFidelity",
    "cburniske",
]

TIER_3_ACCOUNTS = [
    "CryptoCon_",
    "TechDev_52",
    "in2cryptoversee",
    "therationalroot",
    "MacroAlf",
    "TXMCtrades",
    "GameofTrades_",
    "fejau_inc",
    "PositiveCrypto",
    "MacroScope17",
    "stackhodler",
    "ecoinometrics",
    "coinmetrics",
    "MacroCharts",
    "KobeissiLetter",
]

TRACKED_ACCOUNTS = TIER_1_ACCOUNTS + TIER_2_ACCOUNTS + TIER_3_ACCOUNTS

# Verify: len(TRACKED_ACCOUNTS) == 41 (10 + 16 + 15)

BLOCKED_KEYWORDS: list = [
    # Sports
    "nba",
    "nfl",
    "mlb",
    "nhl",
    "champions league",
    "premier league",
    "baseball",
    "basketball",
    "football",
    "soccer",
    "touchdown",
    "strikeout",
    "slam dunk",
    "playoffs",
    "play-in",
    "double-double",
    "parlay",
    "sports betting",
    "over/under",
    # Spam/Promo
    "giveaway",
    "airdrop",
    "whitelist",
    "presale",
    "free mint",
    "follow and rt",
    "like and retweet",
    "sponsored",
    "promo",
    # Motivational/Generic
    "good morning",
    "gm everyone",
    "happy monday",
    "happy friday",
    "happy weekend",
    "let's get after it",
    "never bet against",
    "let's go",
    "lfg",
    "wagmi",
    "have a great",
    # Personal
    "birthday",
    "happy birthday",
    "congratulations",
    "rip ",
    "prayers",
    "my wife",
    "my kids",
    "vacation",
    "holiday",
]

RELEVANT_KEYWORDS: list = [
    # Bitcoin/Crypto
    "bitcoin",
    "btc",
    "crypto",
    "ethereum",
    "eth",
    "satoshi",
    "halving",
    "mining",
    "hash rate",
    "mempool",
    # Market Structure
    "market",
    "bull",
    "bear",
    "rally",
    "correction",
    "crash",
    "drawdown",
    "all-time high",
    "ath",
    "cycle",
    "bottom",
    "capitulation",
    "accumulation",
    "euphoria",
    # Macro
    "fed",
    "fomc",
    "rate cut",
    "rate hike",
    "inflation",
    "cpi",
    "ppi",
    "gdp",
    "recession",
    "employment",
    "jobs",
    "treasury",
    "yield",
    "bond",
    "credit",
    "spread",
    # Liquidity
    "liquidity",
    "stablecoin",
    "tether",
    "usdt",
    "usdc",
    "defi",
    "tvl",
    "funding rate",
    "leverage",
    "margin",
    "open interest",
    # Assets
    "gold",
    "oil",
    "dollar",
    "dxy",
    "equity",
    "equities",
    "s&p",
    "nasdaq",
    "dow",
    "vix",
    "commodities",
    # Geopolitics (market-relevant)
    "tariff",
    "sanctions",
    "iran",
    "hormuz",
    "war",
    "geopolitical",
    "trade war",
    "china",
    # Institutional
    "etf",
    "blackrock",
    "fidelity",
    "saylor",
    "microstrategy",
    "institutional",
    "whale",
    "reserve",
    # Onchain
    "onchain",
    "on-chain",
    "wallet",
    "exchange flow",
    "coinbase",
    "binance",
    # Sentiment
    "fear",
    "greed",
    "sentiment",
    "risk",
    "volatility",
]

# Reply / scanner limits (quality balance). Override via .env.
REPLY_LIMIT_HOURLY = int(os.getenv("REPLY_LIMIT_HOURLY", "5"))
REPLY_LIMIT_DAILY = int(os.getenv("REPLY_LIMIT_DAILY", "15"))
SCAN_TWEET_MAX_AGE = int(os.getenv("SCAN_TWEET_MAX_AGE", "14400"))
MAX_REPLIES_PER_ACCOUNT_PER_DAY = int(os.getenv("MAX_REPLIES_PER_ACCOUNT_PER_DAY", "2"))

MAX_REPLIES_PER_HOUR = REPLY_LIMIT_HOURLY
MAX_REPLIES_PER_DAY = REPLY_LIMIT_DAILY

# Default 3600 = 60 min between scan cycles (41 tracked accounts; override SCAN_INTERVAL_SECONDS in .env for 30 min).
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "3600"))

REPLY_DELAY_MIN = int(os.getenv("REPLY_DELAY_MIN", "30"))
REPLY_DELAY_MAX = int(os.getenv("REPLY_DELAY_MAX", "120"))

MIN_TWEET_AGE_SECONDS = int(os.getenv("MIN_TWEET_AGE_SECONDS", "10"))
MAX_TWEET_AGE_SECONDS = int(os.getenv("MAX_TWEET_AGE_SECONDS", str(SCAN_TWEET_MAX_AGE)))
MIN_LIKES_TO_REPLY = int(os.getenv("MIN_LIKES_TO_REPLY", "0"))

DB_PATH = str(_BASE_DIR / "database.db")
