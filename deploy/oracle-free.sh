#!/usr/bin/env bash
# Oracle Cloud Always Free — навсегда бесплатный VPS (4 CPU, 24 GB RAM).
# Запускай НА СЕРВЕРЕ Oracle после создания Ubuntu ARM instance.
set -euo pipefail

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Oracle Cloud Always Free — установка бота                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Если сервер ещё не создан:"
echo "  1. https://cloud.oracle.com → Compute → Create instance"
echo "  2. Shape: VM.Standard.A1.Flex (ARM), 1 OCPU, 6 GB RAM"
echo "  3. OS: Ubuntu 22.04"
echo "  4. Открой порт SSH (22) в Security List"
echo "  5. Скопируй проект: ./deploy/upload-to-vps.sh ubuntu@ПУБЛИЧНЫЙ_IP"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec sudo bash "${SCRIPT_DIR}/install-vps.sh"
