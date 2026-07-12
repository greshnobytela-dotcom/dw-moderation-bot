#!/usr/bin/env python3
"""Переименование категорий и каналов в гибридный стиль DuckWorld + HIMORY."""

from __future__ import annotations

import asyncio
import os
import re

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# tree: ╭・ первая, ├・ средние, └・ последняя
# формат канала: 〈 emoji 〉{tree}{slug}


def tree(i: int, total: int) -> str:
    if total <= 1:
        return "╭・"
    if i == 0:
        return "╭・"
    if i == total - 1:
        return "└・"
    return "├・"


def ch(emoji: str, slug: str, i: int, total: int, *, voice: bool = False) -> str:
    if voice:
        return f"{emoji}・{slug.replace('-', ' ')}"
    t = tree(i, total)
    return f"〈-{emoji}-〉{t}{slug}"


# Категории: старое имя → новое
CATEGORY_RENAMES: dict[str, str] = {
    "📚 | оᴄноʙноᴇ": "[ 📚 ] Основное",
    "📩 | чᴀᴛы": "[ 💬 ] Чаты",
    "🎤 | ʙойᴄы": "[ 🔊 ] Голосовые",
    "📞 | 1x1": "[ 📞 ] 1x1",
    "отчёты": "[ 📋 ] Отчёты",
}

# Каналы: старое имя → (emoji, slug) — tree вычисляется по позиции в категории
CHANNEL_LAYOUT: dict[str, list[tuple[str, str, str]]] = {
    "📚 | оᴄноʙноᴇ": [
        ("╔『💎』кто-есть-кто", "💎", "кто-есть-кто"),
        ("╠『🆕』информация", "🆕", "информация"),
        ("╠『🪙』зарплата", "🪙", "зарплата"),
        ("╚『🕛』уход-и-приход", "🕛", "уход-и-приход"),
    ],
    "📩 | чᴀᴛы": [
        ("『🛡️』общий", "🛡️", "общий"),
        ("『🪪』отпуск", "🪪", "отпуск"),
        ("『🧧』администрация", "🧧", "администрация"),
        ("『🎵』музло", "🎵", "музло"),
    ],
    "🎤 | ʙойᴄы": [
        ("『💼』Общий", "💼", "общий"),
        ("『🔊』Войс #1", "🔊", "войс-1"),
        ("『🔉』Войс #2", "🔉", "войс-2"),
        ("『🔉』Войс #3", "🔉", "войс-3"),
        ("『🔇』Афк", "🔇", "афк"),
        ("『🍷』Алкоголики", "🍷", "алкоголики"),
        ("『🔰』Госдума", "🔰", "госдума"),
        ("『💢』Приватка", "💢", "приватка"),
        ("『🧢』Оперативный штаб", "🧢", "оперативный-штаб"),
    ],
    "📞 | 1x1": [
        ("『🔈』Войс 1x1 #1", "🔈", "беседка-1"),
        ("『🔈』Войс 1x1 #2", "🔈", "беседка-2"),
    ],
}

REPORT_CATEGORY_OLD = "отчёты"
REPORT_ALL_OLD = "отчёты-всех-проверок"
REPORT_ALL_NEW = "〈-📂-〉╭・все-проверки"


def report_channel_name(old_name: str, index: int, total: int) -> str:
    if "все-проверки" in old_name or old_name == REPORT_ALL_OLD:
        return REPORT_ALL_NEW
    # извлечь ник из старого или нового имени
    nick = old_name
    for prefix in ("отчёты-", "〈-📝-〉├・", "〈-📝-〉└・", "〈-📝-〉╭・"):
        if nick.startswith(prefix) or prefix in nick:
            nick = nick.split("・")[-1]
            break
    if "・" in old_name and not old_name.startswith("отчёты"):
        nick = old_name.split("・")[-1]
    return ch("📝", nick, index, total, voice=False)


async def rename_all(guild: discord.Guild) -> None:
    await guild.fetch_channels()

    # 1. Категории
    print("=== Категории ===")
    cat_by_old: dict[str, discord.CategoryChannel] = {}
    for cat in guild.categories:
        if cat.name in CATEGORY_RENAMES:
            cat_by_old[cat.name] = cat

    for old, new in CATEGORY_RENAMES.items():
        cat = cat_by_old.get(old)
        if cat is None:
            print(f"  ⚠ нет категории: {old}")
            continue
        if cat.name != new:
            await cat.edit(name=new, reason="Hybrid channel styling")
            print(f"  {old} → {new}")
        await asyncio.sleep(0.5)

    # Обновить ссылки после переименования категорий
    await guild.fetch_channels()
    cats = {c.name: c for c in guild.categories}

    # 2. Каналы по layout
    print("\n=== Каналы ===")
    for old_cat, items in CHANNEL_LAYOUT.items():
        new_cat_name = CATEGORY_RENAMES.get(old_cat, old_cat)
        category = cats.get(new_cat_name)
        if category is None:
            print(f"  ⚠ категория не найдена: {new_cat_name}")
            continue

        total = len(items)
        for i, (old_ch, emoji, slug) in enumerate(items):
            is_voice = old_cat in ("🎤 | ʙойᴄы", "📞 | 1x1") or "Войс" in old_ch or "1x1" in old_ch
            new_name = ch(emoji, slug, i, total, voice=is_voice)
            channel = discord.utils.get(category.channels, name=old_ch)
            if channel is None:
                # уже переименован?
                channel = discord.utils.get(category.channels, name=new_name)
                if channel:
                    print(f"  ✓ уже: {new_name}")
                    continue
                print(f"  ⚠ нет канала: {old_ch}")
                continue
            if channel.name != new_name:
                await channel.edit(name=new_name, reason="Hybrid channel styling")
                print(f"  {old_ch} → {new_name}")
            else:
                print(f"  ✓ {new_name}")
            await asyncio.sleep(0.45)

    # 3. Отчёты
    print("\n=== Отчёты ===")
    report_cat = cats.get(CATEGORY_RENAMES[REPORT_CATEGORY_OLD])
    if report_cat:
        report_channels = sorted(
            [c for c in report_cat.channels if isinstance(c, discord.TextChannel)],
            key=lambda c: c.position,
        )
        total = len(report_channels)
        for i, channel in enumerate(report_channels):
            new_name = report_channel_name(channel.name, i, total)
            # если уже в новом формате, пропустить
            if channel.name.startswith("〈 "):
                if channel.name != new_name and not channel.name.endswith(
                    channel.name.split("・")[-1]
                ):
                    pass
                else:
                    # пересчитать только если старое имя отчёты-
                    if not channel.name.startswith("отчёты"):
                        print(f"  ✓ {channel.name}")
                        continue
            if channel.name.startswith("отчёты") or channel.name == REPORT_ALL_OLD:
                if channel.name != new_name:
                    await channel.edit(name=new_name, reason="Hybrid channel styling")
                    print(f"  {channel.name} → {new_name}")
                else:
                    print(f"  ✓ {new_name}")
                await asyncio.sleep(0.45)

    print("\n✅ Переименование завершено")


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
        await rename_all(guild)
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
