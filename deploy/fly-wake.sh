#!/usr/bin/env bash
# Будит бота на Fly.io. Запускай с cron-job.org каждые 3 мин (без карты и без ПК).
# 1) fly tokens create deploy -a dw-moderation-bot
# 2) export FLY_API_TOKEN='токен'
# 3) ./deploy/fly-wake.sh
set -euo pipefail

APP="${FLY_APP:-dw-moderation-bot}"
MACHINE="${FLY_MACHINE:-825999b726e9d8}"
TOKEN="${FLY_API_TOKEN:?Задай FLY_API_TOKEN}"

STATE=$(curl -sf \
  -H "Authorization: ${TOKEN}" \
  "https://api.machines.dev/v1/apps/${APP}/machines/${MACHINE}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('state',''))")

if [[ "${STATE}" == "started" ]]; then
  echo "already running"
  exit 0
fi

curl -sf -X POST \
  -H "Authorization: ${TOKEN}" \
  "https://api.machines.dev/v1/apps/${APP}/machines/${MACHINE}/start" \
  -o /dev/null

echo "started"
