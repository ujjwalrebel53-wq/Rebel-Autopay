#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "Error: TELEGRAM_BOT_TOKEN set karo"
  echo "Example: export TELEGRAM_BOT_TOKEN='your_bot_token_here'"
  exit 1
fi

python3 bot.py
