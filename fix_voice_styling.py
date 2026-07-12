#!/usr/bin/env python3
"""Войсы: только emoji・name (без скобок)."""

from __future__ import annotations

import asyncio
import os

import discord
from dotenv import load_dotenv

from channel_styling import apply_server_styling

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


async def main() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    guild_id = int(os.getenv("DISCORD_GUILD_ID", "0"))
    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        guild = client.get_guild(guild_id) or await client.fetch_guild(guild_id)
        print(f"Сервер: {guild.name}\n")
        await apply_server_styling(guild)
        print("\n✅ Готово. Запусти: python3 apply_dw_permissions.py")
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
