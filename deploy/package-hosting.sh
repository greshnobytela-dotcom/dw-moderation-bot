#!/usr/bin/env bash
# Собирает ZIP для загрузки на бесплатный хостинг (MonkeyBytes, Kerit и др.)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/dw-bot-hosting.zip"

cd "${ROOT}"
rm -f "${OUT}"

zip -r "${OUT}" \
  main.py \
  ticket_bot.py \
  report_bot.py \
  salary_bot.py \
  channel_styling.py \
  requirements.txt \
  -x "*.pyc" "__pycache__/*"

echo ""
echo "✅ Готово: ${OUT}"
echo ""
echo "Залей этот ZIP на хостинг-панель."
