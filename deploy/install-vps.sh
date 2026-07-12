#!/usr/bin/env bash
# Установка бота на Ubuntu/Debian VPS (24/7).
# Запуск на сервере: sudo bash install-vps.sh
set -euo pipefail

APP_DIR="/opt/discord-server-manager"
APP_USER="bot"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Запусти от root: sudo bash $0"
  exit 1
fi

echo "=== Установка зависимостей ==="
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git rsync iptables-persistent 2>/dev/null \
  || apt-get install -y -qq python3 python3-venv python3-pip git rsync

# Oracle Ubuntu иногда блокирует SSH через iptables
if command -v iptables &>/dev/null; then
  iptables -I INPUT 6 -m state --state NEW -p tcp --dport 22 -j ACCEPT 2>/dev/null || true
  netfilter-persistent save 2>/dev/null || true
fi

if ! id -u "${APP_USER}" &>/dev/null; then
  useradd --system --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

mkdir -p "${APP_DIR}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

echo "=== Копирование файлов ==="
rsync -a --delete \
  --exclude '.venv' \
  --exclude 'backups' \
  --exclude '__pycache__' \
  --exclude '.git' \
  "${PROJECT_DIR}/" "${APP_DIR}/"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  echo ""
  echo "Создай ${APP_DIR}/.env:"
  echo "  DISCORD_BOT_TOKEN=твой_токен"
  echo "  DISCORD_GUILD_ID=1500480346540474490"
  echo ""
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  echo "Шаблон скопирован в ${APP_DIR}/.env — отредактируй и запусти скрипт снова."
  exit 1
fi

if grep -q 'your_bot_token_here' "${APP_DIR}/.env"; then
  echo "Заполни DISCORD_BOT_TOKEN в ${APP_DIR}/.env"
  exit 1
fi

echo "=== Python venv ==="
python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install -q -r "${APP_DIR}/requirements.txt"

mkdir -p "${APP_DIR}/data"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "=== systemd ==="
cp "${APP_DIR}/deploy/discord-bot.service" /etc/systemd/system/discord-bot.service
systemctl daemon-reload
systemctl enable discord-bot
systemctl restart discord-bot

echo ""
echo "✅ Бот запущен на сервере."
echo "   Статус:  systemctl status discord-bot"
echo "   Логи:    journalctl -u discord-bot -f"
echo ""
echo "⚠️  Останови бота на своём ПК — одновременно должен работать только один экземпляр."
