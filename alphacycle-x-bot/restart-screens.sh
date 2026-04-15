#!/usr/bin/env bash
# Stop every screen socket named *.xbot or *.tg (avoids "several suitable screens" when
# duplicate names exist), then start one bot.py and one telegram_listener.py detached.
# Run from anywhere; uses this script's directory as the bot root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

quit_matching_screens() {
  # Lines look like: \t12345.tg (date) (Detached)
  local ids
  ids=$(screen -ls 2>/dev/null | grep -oE '[0-9]+\.(xbot|tg)\>' || true)
  if [[ -z "${ids}" ]]; then
    return 0
  fi
  for sid in ${ids}; do
    screen -S "${sid}" -X quit 2>/dev/null || true
  done
}

quit_matching_screens
sleep 1
quit_matching_screens

screen -S xbot -dm bash -lc "cd '${ROOT}' && source .venv/bin/activate && exec python3 bot.py"
screen -S tg -dm bash -lc "cd '${ROOT}' && source .venv/bin/activate && exec python3 telegram_listener.py"
echo "Started xbot + tg in ${ROOT}"
screen -ls
