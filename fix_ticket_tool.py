#!/usr/bin/env python3
"""Убрать тикеты Настроебань, одна категория, подготовка под Ticket Tool."""

from __future__ import annotations

import asyncio
import os

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CAT_MAIN = "экстренная-связь"
CAT_EXTRA = "[ 🚨 ] Экстренная связь"
CAT_ARCHIVE = "[ 📦 ] Архив"
PANEL = "〈-📞-〉панель"
TICKET_TOOL_ID = 557628352828014614
STAFF_ROLE_ID = 1525820362254713063

OUR_BOT_ID = 1525811629537624154


async def fix(guild: discord.Guild) -> None:
    await guild.fetch_channels()
    main = discord.utils.get(guild.categories, name=CAT_MAIN)
    extra = discord.utils.get(guild.categories, name=CAT_EXTRA)

    if main is None:
        main = await guild.create_category(CAT_MAIN, reason="single emergency category")

    # Перенести панель в основную категорию
    panel = discord.utils.get(guild.text_channels, name=PANEL)
    if panel and panel.category_id != main.id:
        await panel.edit(category=main, reason="merge categories")

    # Удалить лишнюю категорию
    if extra:
        for ch in list(extra.channels):
            await ch.edit(category=main)
        await extra.delete(reason="merge into экстренная-связь")
        print("  удалена лишняя категория [ 🚨 ]")

    # Удалить сообщения Настроебань с кнопками тикетов
    if panel:
        async for msg in panel.history(limit=20):
            if msg.author.id == OUR_BOT_ID:
                await msg.delete()
                print("  удалено сообщение панели от Настроебань")

    # Удалить/архивировать каналы 🚨・ созданные нашим ботом
    for ch in list(guild.text_channels):
        if ch.name.startswith("🚨・") and ch.category and ch.category.name in (CAT_MAIN, CAT_EXTRA):
            await ch.delete(reason="remove custom bot tickets - use Ticket Tool")
            print(f"  удалён тикет-канал: {ch.name}")

    # Архив — Ticket Tool сам ведёт, пустую категорию убрать
    archive = discord.utils.get(guild.categories, name=CAT_ARCHIVE)
    if archive and not archive.channels:
        await archive.delete(reason="Ticket Tool has own archive")
        print("  удалена пустая [ 📦 ] Архив")

    # Ticket Tool → роль Сотрудники
    staff = guild.get_role(STAFF_ROLE_ID)
    tt = guild.get_member(TICKET_TOOL_ID)
    if staff and tt and staff not in tt.roles:
        # поднять роль Сотрудники выше роли Ticket Tool
        tt_top = max((r.position for r in tt.roles if r != guild.default_role), default=0)
        if staff.position <= tt_top:
            try:
                await staff.edit(position=tt_top + 1, reason="above Ticket Tool bot role")
                print("  роль Сотрудники поднята")
            except discord.Forbidden:
                print("  ⚠ подними роль Сотрудники выше Ticket Tool вручную")
        try:
            await tt.add_roles(staff, reason="staff role for Ticket Tool")
            print("  Ticket Tool получил роль Сотрудники")
        except discord.Forbidden:
            print("  ⚠ выдай Ticket Tool роль Сотрудники вручную")

    # Панель ставит только Ticket Tool через /setup-panel — Настроебань ничего не пишет
    if panel:
        async for msg in panel.history(limit=30):
            if msg.author.id == OUR_BOT_ID:
                await msg.delete()
                print("  удалено сообщение Настроебань в панели")

    print("✅ Одна категория «экстренная-связь», наш бот тикеты не создаёт")


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
        await fix(guild)
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
