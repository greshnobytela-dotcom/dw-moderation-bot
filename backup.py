#!/usr/bin/env python3
"""Полный backup Discord-сервера: роли, категории, каналы, права."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
BACKUPS_DIR = ROOT / "backups"


def permission_overwrite_to_dict(overwrite: discord.PermissionOverwrite) -> dict:
    result: dict[str, bool | None] = {}
    for name, value in overwrite:
        if value is not None:
            result[name] = value
    return result


def serialize_channel(channel: discord.abc.GuildChannel) -> dict:
    data: dict = {
        "id": str(channel.id),
        "name": channel.name,
        "type": str(channel.type),
        "position": channel.position,
        "overwrites": {},
    }

    if isinstance(channel, discord.CategoryChannel):
        data["category_id"] = None
    else:
        data["category_id"] = str(channel.category_id) if channel.category_id else None

    if isinstance(channel, discord.TextChannel):
        data.update(
            {
                "topic": channel.topic,
                "nsfw": channel.nsfw,
                "slowmode_delay": channel.slowmode_delay,
            }
        )
    elif isinstance(channel, discord.VoiceChannel):
        data.update(
            {
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit,
                "rtc_region": str(channel.rtc_region) if channel.rtc_region else None,
            }
        )

    for target, overwrite in channel.overwrites.items():
        key = f"role:{target.id}" if isinstance(target, discord.Role) else f"member:{target.id}"
        data["overwrites"][key] = {
            "target_name": target.name if hasattr(target, "name") else str(target),
            "allow": permission_overwrite_to_dict(overwrite),
        }

    return data


def serialize_role(role: discord.Role) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "color": role.color.value,
        "hoist": role.hoist,
        "mentionable": role.mentionable,
        "position": role.position,
        "permissions": role.permissions.value,
        "icon": str(role.icon.url) if role.icon else None,
        "unicode_emoji": role.unicode_emoji,
    }


async def backup_guild(guild: discord.Guild, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "meta": {
            "guild_id": str(guild.id),
            "guild_name": guild.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "member_count": guild.member_count,
        },
        "roles": [serialize_role(role) for role in sorted(guild.roles, key=lambda r: r.position, reverse=True)],
        "channels": [serialize_channel(channel) for channel in guild.channels],
    }

    outfile = output_dir / "guild_backup.json"
    outfile.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "guild": guild.name,
        "roles": len(payload["roles"]),
        "channels": len(payload["channels"]),
        "backup_file": str(outfile),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return outfile


async def main() -> None:
    load_dotenv(ROOT / ".env")
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id = os.getenv("DISCORD_GUILD_ID")

    token = (token or "").strip()
    guild_id = (guild_id or "").strip()
    if not token:
        raise SystemExit(
            "Нет DISCORD_BOT_TOKEN.\n"
            "Получи токен: https://discord.com/developers/applications → Bot → Reset Token\n"
            "Запуск: DISCORD_BOT_TOKEN='токен' python3 backup.py"
        )
    if not guild_id:
        raise SystemExit("Нет DISCORD_GUILD_ID в .env")

    intents = discord.Intents.default()
    intents.guilds = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        guild = client.get_guild(int(guild_id))
        if guild is None:
            guild = await client.fetch_guild(int(guild_id))

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = BACKUPS_DIR / f"{guild.name}_{stamp}"
        outfile = await backup_guild(guild, backup_dir)

        print(f"Backup готов: {outfile}")
        print(f"Ролей: {len(guild.roles)}, каналов: {len(guild.channels)}")
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
