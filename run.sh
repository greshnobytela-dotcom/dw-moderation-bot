#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Discord Server Manager ==="

if [[ -z "${DISCORD_BOT_TOKEN:-}" ]]; then
  if [[ -f .env ]]; then
    # shellcheck disable=SC1091
    source <(grep -v '^#' .env | sed 's/^/export /')
  fi
fi

if [[ -z "${DISCORD_BOT_TOKEN:-}" ]]; then
  echo ""
  echo "Нужен токен бота. Получи за 1 минуту:"
  echo "  1. https://discord.com/developers/applications → New Application → Bot → Reset Token"
  echo "  2. Пригласи бота: OAuth2 → bot + Administrator"
  echo "  3. Запусти: DISCORD_BOT_TOKEN='токен' ./run.sh"
  echo ""
  exit 1
fi

export DISCORD_BOT_TOKEN
export DISCORD_GUILD_ID="${DISCORD_GUILD_ID:-1500480346540474490}"

python3 setup_and_run.py --token "$DISCORD_BOT_TOKEN" --guild "$DISCORD_GUILD_ID"
