#!/usr/bin/env python3
"""
Применяет config/server_config.yml к Discord-серверу.
Перед изменениями автоматически делает backup.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import discord
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "server_config.yml"


def load_backup_module():
    spec = importlib.util.spec_from_file_location("backup_mod", ROOT / "backup.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def preset_to_overwrite(preset: dict[str, bool]) -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(**preset)


def resolve_preset(
    name: str,
    presets: dict[str, dict[str, bool]],
    guild: discord.Guild,
) -> tuple[discord.abc.Snowflake, discord.PermissionOverwrite] | None:
    if name == "@everyone":
        return guild.default_role, preset_to_overwrite(presets.get("deny", {"view_channel": False}))

    role = discord.utils.get(guild.roles, name=name)
    if role is None:
        print(f"  ⚠ Роль не найдена: {name}")
        return None

    preset = presets.get(name if name in presets else "", presets.get("view", {}))
    # name might be preset key like "full", "view", etc.
    if name in presets:
        preset = presets[name]
    return role, preset_to_overwrite(preset)


async def ensure_role(guild: discord.Guild, name: str, cfg: dict[str, Any]) -> discord.Role:
    role = discord.utils.get(guild.roles, name=name)
    color = discord.Color(int(cfg.get("color", "#95A5A6").lstrip("#"), 16))
    perms_dict = cfg.get("permissions", {})
    permissions = discord.Permissions(**{k: v for k, v in perms_dict.items() if v is not None})

    if role is None:
        role = await guild.create_role(
            name=name,
            color=color,
            hoist=cfg.get("hoist", False),
            mentionable=cfg.get("mentionable", False),
            permissions=permissions,
            reason="apply_config: create role",
        )
        print(f"  + Создана роль: {name}")
        return role

    await role.edit(
        color=color,
        hoist=cfg.get("hoist", False),
        mentionable=cfg.get("mentionable", False),
        permissions=permissions,
        reason="apply_config: update role",
    )
    print(f"  ✓ Обновлена роль: {name}")
    return role


async def ensure_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    category = discord.utils.get(guild.categories, name=name)
    if category is None:
        category = await guild.create_category(name, reason="apply_config: create category")
        print(f"  + Создана категория: {name}")
    return category


async def ensure_channel(
    guild: discord.Guild,
    category: discord.CategoryChannel,
    name: str,
    channel_type: str,
) -> discord.abc.GuildChannel:
    existing = discord.utils.get(category.channels, name=name)
    if existing is not None:
        return existing

    if channel_type == "voice":
        channel = await guild.create_voice_channel(name, category=category, reason="apply_config")
    else:
        channel = await guild.create_text_channel(name, category=category, reason="apply_config")

    print(f"    + Создан канал: {name} ({channel_type})")
    return channel


async def apply_category_access(
    guild: discord.Guild,
    channel: discord.abc.GuildChannel,
    access: dict[str, str],
    presets: dict[str, dict[str, bool]],
    extra_overrides: dict[str, dict[str, str]] | None = None,
) -> None:
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}

    channel_overrides = (extra_overrides or {}).get(channel.name, {})

    merged_access = dict(access)
    merged_access.update(channel_overrides)

    for role_name, preset_name in merged_access.items():
        preset = presets.get(preset_name)
        if preset is None:
            print(f"    ⚠ Неизвестный пресет '{preset_name}' для {role_name}")
            continue

        if role_name == "@everyone":
            target = guild.default_role
        else:
            target = discord.utils.get(guild.roles, name=role_name)
            if target is None:
                print(f"    ⚠ Роль не найдена для прав: {role_name}")
                continue

        overwrites[target] = preset_to_overwrite(preset)

    await channel.edit(overwrites=overwrites, reason="apply_config: channel permissions")
    print(f"    ✓ Права канала: {channel.name}")


async def reorder_roles(guild: discord.Guild, order: list[str]) -> None:
    roles = []
    for name in order:
        role = discord.utils.get(guild.roles, name=name)
        if role is not None:
            roles.append(role)

    if not roles:
        return

    base = max(r.position for r in guild.roles if not r.is_default()) + len(roles) + 2
    for index, role in enumerate(roles):
        await role.edit(position=base - index, reason="apply_config: reorder roles")
    print(f"  ✓ Порядок ролей обновлён ({len(roles)} шт.)")


async def apply_config(guild: discord.Guild, config: dict[str, Any], *, skip_backup: bool = False) -> None:
    presets = config.get("permission_presets", {})

    if not skip_backup:
        backup_mod = load_backup_module()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = ROOT / "backups" / f"before_apply_{guild.name}_{stamp}"
        outfile = await backup_mod.backup_guild(guild, backup_dir)
        print(f"\n📦 Backup перед применением: {outfile}\n")

    print("=== Роли ===")
    created_roles: list[discord.Role] = []
    for role_name, role_cfg in config.get("roles", {}).items():
        role = await ensure_role(guild, role_name, role_cfg)
        created_roles.append(role)

    order = config.get("server", {}).get("role_order", [])
    if order:
        await reorder_roles(guild, order)

    print("\n=== Категории и каналы ===")
    for category_cfg in config.get("categories", []):
        category = await ensure_category(guild, category_cfg["name"])

        for channel_cfg in category_cfg.get("channels", []):
            channel = await ensure_channel(
                guild,
                category,
                channel_cfg["name"],
                channel_cfg.get("type", "text"),
            )
            await apply_category_access(
                guild,
                channel,
                category_cfg.get("access", {}),
                presets,
                category_cfg.get("channel_overrides"),
            )

        # Права на саму категорию (наследуются каналами без своих overwrites)
        cat_overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}
        for role_name, preset_name in category_cfg.get("access", {}).items():
            preset = presets.get(preset_name)
            if preset is None:
                continue
            target = guild.default_role if role_name == "@everyone" else discord.utils.get(guild.roles, name=role_name)
            if target is not None:
                cat_overwrites[target] = preset_to_overwrite(preset)

        if cat_overwrites:
            await category.edit(overwrites=cat_overwrites, reason="apply_config: category permissions")
            print(f"  ✓ Права категории: {category.name}")

    print("\n✅ Конфиг применён.")


async def main() -> None:
    load_dotenv(ROOT / ".env")
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id = os.getenv("DISCORD_GUILD_ID")

    if not token or not guild_id:
        raise SystemExit(
            "Создай .env (скопируй .env.example) и укажи DISCORD_BOT_TOKEN + DISCORD_GUILD_ID."
        )

    if not CONFIG_PATH.exists():
        raise SystemExit(f"Конфиг не найден: {CONFIG_PATH}")

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    skip_backup = "--no-backup" in sys.argv

    intents = discord.Intents.default()
    intents.guilds = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        guild = client.get_guild(int(guild_id))
        if guild is None:
            guild = await client.fetch_guild(int(guild_id))
        print(f"Сервер: {guild.name} ({guild.id})")
        await apply_config(guild, config, skip_backup=skip_backup)
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
