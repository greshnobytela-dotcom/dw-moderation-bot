#!/usr/bin/env bash
# Копирует проект на VPS с твоего ПК.
# Использование: ./deploy/upload-to-vps.sh user@IP_СЕРВЕРА
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Использование: $0 user@сервер"
  echo "Пример:        $0 root@123.45.67.89"
  exit 1
fi

HOST="$1"
REMOTE_DIR="/opt/discord-server-manager"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Загрузка на ${HOST} ==="
ssh "${HOST}" "mkdir -p ${REMOTE_DIR}"

rsync -avz --progress \
  --exclude '.venv' \
  --exclude 'backups' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude '.cursor' \
  "${ROOT}/" "${HOST}:${REMOTE_DIR}/"

echo ""
echo "Готово. На сервере выполни:"
echo "  ssh ${HOST}"
echo "  sudo bash ${REMOTE_DIR}/deploy/install-vps.sh"
