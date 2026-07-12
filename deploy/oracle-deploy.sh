#!/usr/bin/env bash
# Деплой бота на Oracle Cloud VPS одной командой (после создания сервера).
# Использование: ./deploy/oracle-deploy.sh ubuntu@ПУБЛИЧНЫЙ_IP
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [[ $# -lt 1 ]]; then
  echo ""
  echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${YELLOW}║  Oracle Cloud — бесплатный VPS 24/7                          ║${NC}"
  echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "${GREEN}ШАГ 1 — Регистрация${NC}"
  echo "  https://cloud.oracle.com"
  echo "  Карта только для верификации, Always Free = \$0 навсегда"
  echo ""
  echo -e "${GREEN}ШАГ 2 — Создать сервер${NC}"
  echo "  Compute → Instances → Create instance"
  echo "  • Name: dw-bot"
  echo "  • Image: Ubuntu 22.04 (aarch64)"
  echo "  • Shape: VM.Standard.A1.Flex (Ampere ARM)"
  echo "    OCPU: 1   Memory: 6 GB  (хватит с запасом)"
  echo "  • SSH keys: Add → Generate или вставь свой ~/.ssh/id_ed25519.pub"
  echo "  • Public IP: включи"
  echo ""
  echo "  Если «Out of capacity» — смени Region или Availability Domain"
  echo "  Регионы: Frankfurt, Amsterdam, London часто свободны"
  echo ""
  echo -e "${GREEN}ШАГ 3 — Открыть SSH (порт 22)${NC}"
  echo "  Networking → Virtual cloud networks → твоя VCN"
  echo "  → Security Lists → Default → Ingress Rules → Add:"
  echo "    Source: 0.0.0.0/0   Protocol: TCP   Port: 22"
  echo ""
  echo -e "${GREEN}ШАГ 4 — Деплой бота${NC}"
  echo "  ./deploy/oracle-deploy.sh ubuntu@ТВОЙ_ПУБЛИЧНЫЙ_IP"
  echo ""
  echo "Пример:"
  echo "  ./deploy/oracle-deploy.sh ubuntu@123.45.67.89"
  echo ""
  exit 0
fi

HOST="$1"

if [[ ! -f .env ]]; then
  echo -e "${RED}Нет .env — создай с DISCORD_BOT_TOKEN и DISCORD_GUILD_ID${NC}"
  exit 1
fi

if grep -q 'your_bot_token_here' .env 2>/dev/null; then
  echo -e "${RED}Заполни DISCORD_BOT_TOKEN в .env${NC}"
  exit 1
fi

echo "=== Останавливаем Fly и локальный бот ==="
export PATH="${HOME}/.fly/bin:${PATH}"
flyctl machine stop 825999b726e9d8 -a dw-moderation-bot 2>/dev/null || true
pkill -f 'python3 -u ticket_bot.py' 2>/dev/null || true

echo "=== Проверка SSH: ${HOST} ==="
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "${HOST}" "echo ok" 2>/dev/null; then
  echo -e "${RED}Не могу подключиться по SSH.${NC}"
  echo "  • Проверь IP и что ключ добавлен в Oracle"
  echo "  • Проверь Ingress Rule для порта 22"
  echo "  • Попробуй: ssh ${HOST}"
  exit 1
fi

echo "=== Загрузка проекта ==="
bash "${ROOT}/deploy/upload-to-vps.sh" "${HOST}"

echo "=== Установка и запуск на сервере ==="
ssh -t "${HOST}" "sudo bash /opt/discord-server-manager/deploy/install-vps.sh"

echo ""
echo -e "${GREEN}✅ Бот на Oracle VPS работает 24/7${NC}"
echo "   Логи:  ssh ${HOST} 'sudo journalctl -u discord-bot -f'"
echo "   Статус: ssh ${HOST} 'sudo systemctl status discord-bot'"
