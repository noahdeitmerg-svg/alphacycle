#!/usr/bin/env bash
# Run from repo root on Linux/macOS. Loads .env via config.py (python-dotenv).
# Telegram: only you approve X posts (POST/SKIP). Run BOTH processes 24/7:
#   screen -S xbot   -> python3 bot.py
#   screen -S tg     -> python3 telegram_listener.py
# Or systemd: see systemd/*.service and RUN_24_7.md
set -euo pipefail
cd "$(dirname "$0")"
exec python3 bot.py "$@"
