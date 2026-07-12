#!/usr/bin/env python3
"""Автонастройка: создаёт .env, проверяет бота, делает backup и применяет конфиг."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def read_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    data: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def write_env(token: str, guild_id: str) -> None:
    ENV_PATH.write_text(
        f"DISCORD_BOT_TOKEN={token}\nDISCORD_GUILD_ID={guild_id}\n",
        encoding="utf-8",
    )


async def verify_bot(token: str, guild_id: str) -> tuple[bool, str]:
    import discord

    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)
    ok = False
    message = ""

    @client.event
    async def on_ready() -> None:
        nonlocal ok, message
        guild = client.get_guild(int(guild_id))
        if guild is None:
            try:
                guild = await client.fetch_guild(int(guild_id))
            except discord.NotFound:
                message = f"Сервер с ID {guild_id} не найден. Бот добавлен на сервер?"
                await client.close()
                return
            except discord.Forbidden:
                message = "Бот не имеет доступа к серверу. Пригласи бота с правами Administrator."
                await client.close()
                return

        me = guild.me
        if me is None:
            message = "Бот не на сервере. Пригласи его по OAuth2 URL."
            await client.close()
            return

        perms = me.guild_permissions
        if not perms.manage_roles or not perms.manage_channels:
            message = (
                f"Бот на сервере «{guild.name}», но не хватает прав: "
                f"manage_roles={perms.manage_roles}, manage_channels={perms.manage_channels}"
            )
        else:
            ok = True
            message = f"OK: {guild.name} ({guild.id}), бот: {me.display_name}"
        await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure:
        return False, "Неверный токен бота"
    except Exception as exc:
        return False, str(exc)

    return ok, message


def parse_args() -> tuple[str | None, str | None]:
    token = None
    guild_id = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("--token", "-t") and i + 1 < len(args):
            token = args[i + 1]
            i += 2
        elif args[i] in ("--guild", "-g") and i + 1 < len(args):
            guild_id = args[i + 1]
            i += 2
        else:
            i += 1
    return token, guild_id


def print_setup_instructions() -> None:
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║  Нужен токен СВОЕГО бота (JuniperBot не подходит)           ║
╠══════════════════════════════════════════════════════════════╣
║  1. Открой: https://discord.com/developers/applications      ║
║  2. New Application → Bot → Reset Token                      ║
║  3. OAuth2 → bot + Administrator → скопируй URL, пригласи    ║
║  4. ID сервера: ПКМ по иконке сервера → Копировать ID        ║
║     (Настройки → Расширенные → Режим разработчика)           ║
╚══════════════════════════════════════════════════════════════╝

Запуск с данными:
  python3 setup_and_run.py --token TOKEN --guild SERVER_ID

Или создай файл .env вручную (см. .env.example).
"""
    )


async def main() -> None:
    token_arg, guild_arg = parse_args()
    env = read_env()

    token = token_arg or env.get("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
    guild_id = guild_arg or env.get("DISCORD_GUILD_ID") or os.getenv("DISCORD_GUILD_ID")

    if not token or not guild_id or token == "your_bot_token_here":
        print_setup_instructions()
        raise SystemExit(1)

    if not re.fullmatch(r"\d{17,20}", guild_id):
        raise SystemExit(f"Неверный DISCORD_GUILD_ID: {guild_id}")

    write_env(token, guild_id)
    print("Проверяю бота...")
    ok, msg = await verify_bot(token, guild_id)
    print(msg)
    if not ok:
        raise SystemExit(1)

    print("\n=== Backup ===")
    subprocess.run([sys.executable, str(ROOT / "backup.py")], check=True)

    print("\n=== Применение конфига ===")
    subprocess.run([sys.executable, str(ROOT / "apply_config.py"), "--no-backup"], check=True)

    print("\n✅ Готово! Backup в папке backups/")


if __name__ == "__main__":
    asyncio.run(main())
