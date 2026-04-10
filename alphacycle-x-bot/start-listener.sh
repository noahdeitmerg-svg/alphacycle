#!/usr/bin/env bash
# Second process: Telegram inline-button handler (POST / SKIP).
set -euo pipefail
cd "$(dirname "$0")"
exec python3 telegram_listener.py
