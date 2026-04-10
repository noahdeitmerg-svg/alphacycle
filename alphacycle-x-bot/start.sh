#!/usr/bin/env bash
# Run from repo root on Linux/macOS. Loads .env via config.py (python-dotenv).
# Telegram approval: run two processes (e.g. two screen sessions):
#   screen -S xbot   -> python3 bot.py
#   screen -S tg     -> python3 telegram_listener.py
set -euo pipefail
cd "$(dirname "$0")"
exec python3 bot.py "$@"
