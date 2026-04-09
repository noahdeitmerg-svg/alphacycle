#!/usr/bin/env bash
# Run from repo root on Linux/macOS. Loads .env via config.py (python-dotenv).
set -euo pipefail
cd "$(dirname "$0")"
exec python3 bot.py "$@"
