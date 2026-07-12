#!/usr/bin/env bash
# Настройка Fly.io для постоянной работы бота.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

export PATH="${HOME}/.fly/bin:${PATH}"

APP="dw-moderation-bot"
MACHINE="825999b726e9d8"

echo "=== Fly.io: always-on setup ==="
echo ""
echo "⚠️  Без привязанной карты Fly trial убивает машину каждые 5 минут."
echo "    Для нормальной работы 24/7: https://fly.io/dashboard/account/billing"
echo "    Стоимость ~\$2–4/мес за 256MB машину."
echo ""

if ! command -v flyctl &>/dev/null; then
  echo "Установи: curl -L https://fly.io/install.sh | sh"
  exit 1
fi

echo "Останавливаем локальный бот (если запущен)..."
pkill -f 'python3 -u ticket_bot.py' 2>/dev/null || true

echo "=== Деплой ==="
flyctl deploy -a "${APP}"

echo "=== Restart policy: always ==="
flyctl machine update "${MACHINE}" -a "${APP}" --restart always -y

echo "=== Запуск машины ==="
flyctl machine start "${MACHINE}" -a "${APP}" || true

echo ""
echo "✅ Бот на Fly.io"
echo "   Логи:   flyctl logs -a ${APP}"
echo "   Статус: flyctl status -a ${APP}"
echo "   Биллинг: https://fly.io/dashboard/account/billing"
