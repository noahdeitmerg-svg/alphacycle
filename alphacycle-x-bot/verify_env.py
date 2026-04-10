"""Print secret lengths and obvious .env issues (no values shown). Run: python3 verify_env.py"""
from datetime import datetime, timezone

import config


def _line(name: str, value: str) -> None:
    bad = "\n" in value or "\r" in value
    print(f"{name}: len={len(value)} newline_inside={bad}")


def main() -> None:
    path = config.ENV_FILE
    print(f"ENV_FILE: {path} | exists: {path.exists()}")
    _line("TWITTER_BEARER", config.TWITTER_BEARER)
    _line("TWITTER_API_KEY", config.TWITTER_API_KEY)
    _line("TWITTER_API_SECRET", config.TWITTER_API_SECRET)
    _line("TWITTER_ACCESS_TOKEN", config.TWITTER_ACCESS_TOKEN)
    _line("TWITTER_ACCESS_SECRET", config.TWITTER_ACCESS_SECRET)
    _line("CLAUDE_API_KEY", config.CLAUDE_API_KEY)
    _line("TELEGRAM_BOT_TOKEN", config.TELEGRAM_BOT_TOKEN)
    _line("TELEGRAM_CHAT_ID", config.TELEGRAM_CHAT_ID)
    if config.TWITTER_BEARER and len(config.TWITTER_BEARER) < 80:
        print("Hint: Bearer usually long; len<80 may be truncated in .env (line break?).")
    if config.TWITTER_API_SECRET and len(config.TWITTER_API_SECRET) < 40:
        print("Hint: API secret often ~50 chars; check for truncated line in .env.")
    if config.TWITTER_ACCESS_SECRET and len(config.TWITTER_ACCESS_SECRET) < 40:
        print("Hint: Access token secret often ~45 chars; check .env single-line value.")
    print("Server UTC now:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"))
    print("If get_me 401: run `timedatectl` / sync NTP; in X Portal regenerate Key+Secret AND Access+Secret for same app.")


if __name__ == "__main__":
    main()
