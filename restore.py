#!/usr/bin/env python3
"""Восстановление ролей и прав каналов из backup (без удаления лишнего)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import discord
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def dict_to_overwrite(data: dict) -> discord.PermissionOverwrite:
    kwargs = {key: value for key, value in data.items() if value is not None}
    return discord.PermissionOverwrite(**kwargs)


async def restore_from_backup(guild: discord.Guild, backup_path: Path) -> None:
    payload = json.loads(backup_path.read_text(encoding="utf-8"))

    role_by_id = {str(role.id): role for role in guild.roles}
    role_by_name = {role.name.lower(): role for role in guild.roles}

    restored_roles = 0
    for role_data in payload.get("roles", []):
        role = role_by_id.get(role_data["id"]) or role_by_name.get(role_data["name"].lower())
        if role is None or role.is_default() or role.managed:
            continue

        await role.edit(
            name=role_data["name"],
            color=discord.Color(role_data["color"]),
            hoist=role_data.get("hoist", False),
            mentionable=role_data.get("mentionable", False),
            permissions=discord.Permissions(role_data["permissions"]),
            reason="Restore from backup",
        )
        restored_roles += 1

    channel_by_id = {str(channel.id): channel for channel in guild.channels}
    channel_by_name = {channel.name.lower(): channel for channel in guild.channels}

    restored_channels = 0
    for channel_data in payload.get("channels", []):
        channel = channel_by_id.get(channel_data["id"]) or channel_by_name.get(
            channel_data["name"].lower()
        )
        if channel is None:
            continue

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}
        for target_key, ow_data in channel_data.get("overwrites", {}).items():
            target_id = int(target_key.split(":", 1)[1])
            if target_key.startswith("role:"):
                target = guild.get_role(target_id)
            else:
                target = guild.get_member(target_id)
            if target is None:
                continue
            overwrites[target] = dict_to_overwrite(ow_data["allow"])

        await channel.edit(overwrites=overwrites, reason="Restore channel permissions from backup")
        restored_channels += 1

    print(f"Восстановлено ролей: {restored_roles}")
    print(f"Восстановлено каналов: {restored_channels}")


async def main() -> None:
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Использование: python restore.py backups/<папка>/guild_backup.json")

    backup_path = Path(sys.argv[1]).resolve()
    if not backup_path.exists():
        raise SystemExit(f"Файл не найден: {backup_path}")

    load_dotenv(ROOT / ".env")
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if not token or not guild_id:
        raise SystemExit("Нужен .env с DISCORD_BOT_TOKEN и DISCORD_GUILD_ID")

    intents = discord.Intents.default()
    intents.guilds = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        guild = client.get_guild(int(guild_id))
        if guild is None:
            guild = await client.fetch_guild(int(guild_id))
        await restore_from_backup(guild, backup_path)
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
