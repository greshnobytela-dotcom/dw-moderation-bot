#!/usr/bin/env python3
"""Архив тикетов: доступ только • Высшая Модерация и выше."""

from __future__ import annotations

import asyncio
import os

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

R_HIGH_MOD = "• Высшая Модерация"
# Высшая модерация и все роли выше неё
R_ARCHIVE_VIEW = [
    R_HIGH_MOD,
    "• Отдел SS",
    "• Администрация",
    "• Высшая Администрация",
    "• Руководство",
    "⭐",
]

ARCHIVE_KEYWORDS = ("архив", "archive", "closed", "закрыт")


def archive_ows(guild: discord.Guild, roles: dict[str, discord.Role]) -> dict:
    ows: dict = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    for rn in R_ARCHIVE_VIEW:
        r = roles.get(rn)
        if r:
            ows[r] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                attach_files=False,
            )
    return ows


def is_archive_category(name: str) -> bool:
    low = name.lower()
    return any(k in low for k in ARCHIVE_KEYWORDS)


async def apply(guild: discord.Guild) -> None:
    await guild.fetch_channels()
    roles = {r.name: r for r in guild.roles}
    ows = archive_ows(guild, roles)

    found = 0
    for cat in guild.categories:
        if not is_archive_category(cat.name):
            continue
        await cat.edit(overwrites=ows, reason="archive: high mod+ only")
        print(f"  ✓ категория: {cat.name}")
        found += 1
        for ch in cat.channels:
            await ch.edit(overwrites=ows, reason="archive: high mod+ only")
            print(f"    ✓ {ch.name}")
            await asyncio.sleep(0.35)

    if found == 0:
        print("  ⚠ категория архива не найдена (появится после первого закрытого тикета Ticket Tool)")
        print("  Запусти скрипт снова после /setup-panel и закрытия тикета.")


async def main() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    gid = int(os.getenv("DISCORD_GUILD_ID", "0"))
    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        guild = client.get_guild(gid) or await client.fetch_guild(gid)
        print(f"Сервер: {guild.name}")
        await apply(guild)
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
