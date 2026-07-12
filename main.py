#!/usr/bin/env python3
"""Точка входа для хостинг-панелей (MonkeyBytes, Kerit и т.д.)."""
from ticket_bot import bot
import os

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Задай DISCORD_BOT_TOKEN в переменных окружения панели")
    bot.run(token)
