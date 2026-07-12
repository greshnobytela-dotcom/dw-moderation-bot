#!/usr/bin/env bash
# Бесплатный деплой на Fly.io (256 MB RAM, 24/7).
# Нужна карта только для верификации — списаний на free tier нет.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if ! command -v flyctl &>/dev/null; then
  echo "Установи Fly CLI:"
  echo "  curl -L https://fly.io/install.sh | sh"
  echo "  export PATH=\"\$HOME/.fly/bin:\$PATH\""
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Создай .env с DISCORD_BOT_TOKEN и DISCORD_GUILD_ID"
  exit 1
fi

# shellcheck disable=SC1091
source <(grep -v '^#' .env | sed 's/^/export /')

if [[ -z "${DISCORD_BOT_TOKEN:-}" ]] || [[ "${DISCORD_BOT_TOKEN}" == "your_bot_token_here" ]]; then
  echo "Заполни DISCORD_BOT_TOKEN в .env"
  exit 1
fi

APP_NAME="$(grep '^app = ' fly.toml | sed 's/app = "\(.*\)"/\1/')"
REGION="$(grep '^primary_region = ' fly.toml | sed 's/primary_region = "\(.*\)"/\1/')"

echo "=== Fly.io: ${APP_NAME} ==="
echo "Останови бота на ПК: pkill -f 'python3 -u ticket_bot.py'"
echo ""

if ! flyctl apps list 2>/dev/null | grep -q "${APP_NAME}"; then
  echo "Создаю приложение..."
  flyctl apps create "${APP_NAME}" --org personal 2>/dev/null || flyctl apps create "${APP_NAME}"
fi

if ! flyctl volumes list -a "${APP_NAME}" 2>/dev/null | grep -q bot_data; then
  echo "Создаю диск для счётчиков (data/)..."
  flyctl volumes create bot_data --size 1 --region "${REGION}" -a "${APP_NAME}" --yes
fi

echo "=== Секреты ==="
flyctl secrets set \
  DISCORD_BOT_TOKEN="${DISCORD_BOT_TOKEN}" \
  DISCORD_GUILD_ID="${DISCORD_GUILD_ID:-1500480346540474490}" \
  -a "${APP_NAME}"

echo "=== Деплой ==="
flyctl deploy -a "${APP_NAME}"

echo ""
echo "✅ Готово!"
echo "   Логи:  flyctl logs -a ${APP_NAME}"
echo "   Статус: flyctl status -a ${APP_NAME}"
