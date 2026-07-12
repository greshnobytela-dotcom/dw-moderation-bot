#!/usr/bin/env python3
"""Создание категорий, переименование отчётов, панель экстренной связи."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

ROOT = Path(__file__).parent
DATA = ROOT / "data"

CAT_EMERGENCY = "экстренная-связь"

PANEL_CHANNEL = "〈-📞-〉панель"
MUSIC_CHANNEL_OLD = "〈-🎵-〉└・музло"
MUSIC_CHANNEL_NEW = "🎵・музло"

R_STAFF = "•  Сотрудники"
R_HIGH_ADMIN = "• Высшая Администрация"
R_ADMIN = "• Администрация"
R_HIGH_MOD = "• Высшая Модерация"
R_SS = "• Отдел SS"
R_MOD_PLUS = "• Модерация+"
R_MOD = "• Модерация"
R_MUSIC = "•  Музло"


def report_name(nick: str) -> str:
    return f"📝・{nick}"


async def ensure_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    cat = discord.utils.get(guild.categories, name=name)
    if cat:
        return cat
    return await guild.create_category(name, reason="setup emergency")


async def ensure_text(
    guild: discord.Guild,
    name: str,
    category: discord.CategoryChannel | None,
) -> discord.TextChannel:
    ch = discord.utils.get(guild.text_channels, name=name)
    if ch:
        if category and ch.category_id != category.id:
            await ch.edit(category=category, reason="move channel")
        return ch
    return await guild.create_text_channel(name, category=category, reason="setup channel")


def ow(**kwargs) -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(**kwargs)


async def setup_permissions(guild: discord.Guild, roles: dict[str, discord.Role]) -> None:
    staff_roles = [R_MOD, R_MOD_PLUS, R_HIGH_MOD, R_SS, R_ADMIN, R_HIGH_ADMIN]
    cat = discord.utils.get(guild.categories, name=CAT_EMERGENCY)
    if cat:
        ows = {guild.default_role: ow(view_channel=True, send_messages=False)}
        for rn in staff_roles:
            r = roles.get(rn)
            if r:
                ows[r] = ow(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
        await cat.edit(overwrites=ows)

    music = discord.utils.get(guild.text_channels, name=MUSIC_CHANNEL_NEW) or discord.utils.get(
        guild.text_channels, name=MUSIC_CHANNEL_OLD
    )
    if music:
        ows = {
            guild.default_role: ow(view_channel=True, send_messages=False),
        }
        music_role = roles.get(R_MUSIC)
        if music_role:
            ows[music_role] = ow(view_channel=True, send_messages=True, read_message_history=True)
        for rn in [R_ADMIN, R_HIGH_ADMIN, R_MOD, R_MOD_PLUS]:
            r = roles.get(rn)
            if r:
                ows[r] = ow(view_channel=True, send_messages=True, read_message_history=True)
        await music.edit(overwrites=ows)


async def rename_reports(guild: discord.Guild) -> None:
    cat = discord.utils.get(guild.categories, name="[ 📋 ] Отчёты")
    if not cat:
        return
    for ch in list(cat.text_channels):
        if ch.name.startswith("📝・"):
            continue
        nick = ch.name
        for prefix in ("〈-📝-〉├・", "〈-📝-〉└・", "〈-📝-〉╭・", "〈-📂-〉╭・", "отчёты-"):
            if prefix in nick or nick.startswith(prefix):
                nick = nick.split("・")[-1]
                break
        if nick in ("все-проверки", "всех-проверок"):
            new = "📂・все-проверки"
        else:
            new = report_name(nick)
        if ch.name != new:
            await ch.edit(name=new)
            print(f"  отчёт: {ch.name} → {new}")
            await asyncio.sleep(0.4)


async def post_panel(channel: discord.TextChannel) -> None:
    """Панель ставит Ticket Tool через /setup-panel — наш бот не создаёт тикеты."""
    return


async def run_setup(guild: discord.Guild) -> None:
    await guild.fetch_channels()
    roles = {r.name: r for r in guild.roles}

    em_cat = await ensure_category(guild, CAT_EMERGENCY)
    panel_ch = await ensure_text(guild, PANEL_CHANNEL, em_cat)

    # музло
    music = discord.utils.get(guild.text_channels, name=MUSIC_CHANNEL_OLD)
    if music:
        await music.edit(name=MUSIC_CHANNEL_NEW)
        print(f"  музло → {MUSIC_CHANNEL_NEW}")

    await rename_reports(guild)
    await setup_permissions(guild, roles)

    # Панель
    await post_panel(panel_ch)

    music_ch = discord.utils.get(guild.text_channels, name=MUSIC_CHANNEL_NEW)
    if music_ch:
        pass  # Настроебань не пишет в каналы — инструкции по VK Music вручную или через Ticket Tool

    DATA.mkdir(exist_ok=True)
    if not (DATA / "ticket_counter.json").exists():
        (DATA / "ticket_counter.json").write_text('{"next_id": 0}')

    print("✅ Структура готова")


async def main() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    guild_id = int(os.getenv("DISCORD_GUILD_ID", "0"))
    intents = discord.Intents.default()
    intents.guilds = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        guild = client.get_guild(guild_id) or await client.fetch_guild(guild_id)
        print(f"Сервер: {guild.name}")
        await run_setup(guild)
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
