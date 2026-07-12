#!/usr/bin/env python3
"""Применяет права на сервер ⚡DW Moderation."""

from __future__ import annotations

import asyncio
import os

import discord
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT, ".env"))

PRESETS: dict[str, dict[str, bool | None]] = {
    "full": {
        "view_channel": True,
        "send_messages": True,
        "read_message_history": True,
        "attach_files": True,
        "embed_links": True,
        "connect": True,
        "speak": True,
        "stream": True,
        "manage_channels": True,
        "manage_messages": True,
        "move_members": True,
    },
    "view": {
        "view_channel": True,
        "read_message_history": True,
        "connect": True,
        "speak": True,
        "stream": True,
    },
    "view_no_manage": {
        "view_channel": True,
        "read_message_history": True,
        "connect": True,
        "speak": True,
        "stream": True,
        "manage_channels": False,
        "manage_messages": False,
        "manage_roles": False,
    },
    "manage_category_reports": {
        "view_channel": True,
        "read_message_history": True,
        "manage_channels": True,
        "send_messages": True,
        "attach_files": True,
    },
    "report_view": {
        "view_channel": True,
        "read_message_history": True,
    },
    "report_post": {
        "view_channel": True,
        "send_messages": True,
        "read_message_history": True,
        "attach_files": True,
        "embed_links": True,
        "add_reactions": True,
    },
    "voice_staff": {
        "view_channel": True,
        "connect": True,
        "speak": True,
        "stream": True,
        "use_voice_activation": True,
    },
    "staff_full": {
        "view_channel": True,
        "send_messages": True,
        "read_message_history": True,
        "attach_files": True,
        "embed_links": True,
        "connect": True,
        "speak": True,
        "stream": True,
        "add_reactions": True,
    },
    "deny": {
        "view_channel": False,
        "connect": False,
    },
}

R_STAR = "⭐"
R_LEAD = "• Руководство"
R_HIGH_ADMIN = "• Высшая Администрация"
R_ADMIN = "• Администрация"
R_HIGH_MOD = "• Высшая Модерация"
R_SS = "• Отдел SS"
R_MOD_PLUS = "• Модерация+"
R_MOD = "• Модерация"
R_PASS = "• Проходка"
R_DEPUTY = "•  Депутат"
R_PRIVATE = "•  Приват"
R_REPORTS = "•  Доступ к отчётам"

# Роли выше обычной модерации + сами модераторы — одни и те же войсы
VOICE_STAFF = [
    R_STAR,
    R_LEAD,
    R_HIGH_ADMIN,
    R_ADMIN,
    R_HIGH_MOD,
    R_SS,
    R_MOD_PLUS,
    R_MOD,
    R_PASS,
]

STAFF_ALL = VOICE_STAFF

VOICE_CATEGORIES = {"[ 🔊 ] Голосовые", "[ 🔊 ] Войсы", "[ 📞 ] 1x1"}
LOCKED_VOICE_CATEGORY = "[ 🔒 ] Закрытые"

CAT_ARCHIVE_LEGACY = "[ 📦 ] Архив"

SPECIAL_VOICE = {
    "🍷 • алкоголики",
    "🧢 • оперативный штаб",
    "💢 • приватка",
    "🔰 • госдума",
    # legacy
    "🍷・алкоголики",
    "🧢・оперативный штаб",
    "💢・приватка",
    "🔰・госдума",
    "〈 🍷 〉алкоголики",
    "〈 🧢 〉оперативный штаб",
    "〈 💢 〉приватка",
    "〈 🔰 〉госдума",
}

# Руководство (+ ⭐) — во все войсы
_LEAD_ACCESS = {R_STAR: "voice_staff", R_LEAD: "voice_staff"}

_CHANNEL_ADMIN = {
    R_ADMIN: "full",
    R_HIGH_ADMIN: "full",
    R_HIGH_MOD: "view_no_manage",
    R_STAR: "view_no_manage",
    R_LEAD: "view_no_manage",
    "@everyone": "deny",
}

CHANNEL_RULES: dict[str, dict[str, str]] = {
    "🍷 • алкоголики": {
        **_LEAD_ACCESS,
        R_HIGH_ADMIN: "voice_staff",
        R_ADMIN: "voice_staff",
        "@everyone": "deny",
    },
    "🧢 • оперативный штаб": {**_LEAD_ACCESS, "@everyone": "deny"},
    "💢 • приватка": {**_LEAD_ACCESS, R_PRIVATE: "voice_staff", "@everyone": "deny"},
    "🔰 • госдума": {**_LEAD_ACCESS, R_DEPUTY: "voice_staff", "@everyone": "deny"},
    "〈🧧〉-администрация": _CHANNEL_ADMIN,
    "〈🧧〉・администрация": _CHANNEL_ADMIN,
    "〈🧧〉-администрация": _CHANNEL_ADMIN,
    # legacy
        **_LEAD_ACCESS,
        R_HIGH_ADMIN: "voice_staff",
        R_ADMIN: "voice_staff",
        "@everyone": "deny",
    },
    "🧢・оперативный штаб": {**_LEAD_ACCESS, "@everyone": "deny"},
    "💢・приватка": {**_LEAD_ACCESS, R_PRIVATE: "voice_staff", "@everyone": "deny"},
    "🔰・госдума": {**_LEAD_ACCESS, R_DEPUTY: "voice_staff", "@everyone": "deny"},
    "〈 🍷 〉алкоголики": {
        **_LEAD_ACCESS,
        R_HIGH_ADMIN: "voice_staff",
        R_ADMIN: "voice_staff",
        "@everyone": "deny",
    },
    "〈 🧢 〉оперативный штаб": {**_LEAD_ACCESS, "@everyone": "deny"},
    "〈 💢 〉приватка": {**_LEAD_ACCESS, R_PRIVATE: "voice_staff", "@everyone": "deny"},
    "〈 🔰 〉госдума": {**_LEAD_ACCESS, R_DEPUTY: "voice_staff", "@everyone": "deny"},
    "〈-🧧-〉├・администрация": _CHANNEL_ADMIN,
    "〈📊〉・выплаты": {
        R_LEAD: "report_post",
        R_STAR: "report_view",
        R_HIGH_ADMIN: "report_view",
        R_ADMIN: "report_view",
        R_HIGH_MOD: "report_view",
        R_SS: "report_view",
        R_MOD_PLUS: "report_view",
        R_MOD: "report_view",
        "@everyone": "deny",
    },
}

REPORT_CATEGORY = "[ 📋 ] Отчёты"
REPORT_VIEWERS = [R_ADMIN, R_HIGH_ADMIN, R_HIGH_MOD, R_SS, R_REPORTS, R_LEAD, R_STAR]
REPORT_ALL_MODS = "〈📂〉・все-проверки"
REPORT_SKIP_CHANNELS = {
    REPORT_ALL_MODS,
    "〈📋〉・создание",
    "〈💵〉・зарплата",
    "〈💰〉・зарплата",
    "〈📊〉・выплаты",
    "〈📞〉・панель",
    "〈🎵〉・музло",
    "〈📋〉-создание",
    "〈💰〉-зарплата",
    "〈📞〉-панель",
    "〈🎵〉-музло",
    "〈📂〉-все-проверки",
    "создание-отчёта",
    "📋・создание",
    "📋・панель",
    "получение-зарплаты",
    "💰・зарплата",
    "📂・все-проверки",
}

SKIP_CATEGORIES = {
    REPORT_CATEGORY,
    CAT_ARCHIVE_LEGACY,
    "[ 📦 ] Архив ・ Вызовы",
    "[ 📦 ] Архив ・ Зарплата",
    "заработок",
    "[ 💸 ] Заработок",
    "[ 💰 ] Заработок",
    "экстренная-связь",
    "[ 📞 ] Экстренная связь",
    "архив",
}


def ow(preset_name: str) -> discord.PermissionOverwrite:
    data = PRESETS[preset_name]
    return discord.PermissionOverwrite(**{k: v for k, v in data.items() if v is not None})


def role_map(guild: discord.Guild) -> dict[str, discord.Role]:
    m: dict[str, discord.Role] = {"@everyone": guild.default_role}
    for r in guild.roles:
        m[r.name] = r
    return m


async def apply_rules(
    channel: discord.abc.GuildChannel,
    rules: dict,
    roles: dict[str, discord.Role],
    *,
    keep_members: bool = True,
    upgrade_members_to: str | None = None,
) -> None:
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}

    if keep_members:
        for target, existing in channel.overwrites.items():
            # Сохраняем персональные права (Member или Object с id пользователя)
            if isinstance(target, discord.Role):
                continue
            if upgrade_members_to:
                overwrites[target] = ow(upgrade_members_to)
            else:
                overwrites[target] = existing

    for key, preset in rules.items():
        if isinstance(key, discord.Member):
            overwrites[key] = ow(preset)
            continue
        target = roles.get(key)
        if target is None:
            print(f"    ⚠ роль не найдена: {key}")
            continue
        overwrites[target] = ow(preset)

    await channel.edit(overwrites=overwrites, reason="DW Moderation: permissions update")
    print(f"  ✓ {channel.name}")


async def apply_voice_channels(guild: discord.Guild, roles: dict[str, discord.Role]) -> int:
    count = 0
    print("\n=== Голосовые (роли выше модерации) ===")

    for ch in guild.channels:
        if ch.type != discord.ChannelType.voice:
            continue
        if ch.name in SPECIAL_VOICE:
            continue

        in_staff_category = (
            ch.category is not None and ch.category.name in VOICE_CATEGORIES
        )
        if not in_staff_category:
            continue

        rules: dict = {"@everyone": "deny"}
        for role_name in VOICE_STAFF:
            rules[role_name] = "voice_staff"

        await apply_rules(ch, rules, roles, keep_members=False)
        count += 1
        await asyncio.sleep(0.4)

    for cat in guild.categories:
        if cat.name not in VOICE_CATEGORIES:
            continue
        rules = {"@everyone": "deny"}
        for role_name in VOICE_STAFF:
            rules[role_name] = "voice_staff"
        await apply_rules(cat, rules, roles, keep_members=False)
        count += 1
        await asyncio.sleep(0.4)

    return count


async def apply_report_channel(
    channel: discord.TextChannel,
    roles: dict[str, discord.Role],
) -> None:
    # На каналах отчётов высшая админка НЕ редактирует — только категория
    rules: dict = {
        "@everyone": "deny",
    }
    for role_name in REPORT_VIEWERS:
        rules[role_name] = "report_view"

    if channel.name == REPORT_ALL_MODS:
        for role_name in [R_MOD, R_MOD_PLUS, R_HIGH_MOD, R_SS, R_REPORTS]:
            rules[role_name] = "report_post"
    else:
        has_member = any(not isinstance(t, discord.Role) for t in channel.overwrites)
        if has_member:
            print(f"    → запись для добавленного модератора в {channel.name}")
        else:
            print(f"    ⚠ {channel.name}: добавь модератора (ПКМ → Права)")

    await apply_rules(
        channel, rules, roles, keep_members=True, upgrade_members_to="report_post"
    )


async def apply_reports(guild: discord.Guild, roles: dict[str, discord.Role]) -> int:
    count = 0
    print("\n=== Отчёты ===")

    for cat in guild.categories:
        if cat.name != REPORT_CATEGORY:
            continue

        cat_rules = {
            R_HIGH_ADMIN: "manage_category_reports",
            R_ADMIN: "report_view",
            R_HIGH_MOD: "report_view",
            R_SS: "report_view",
            R_REPORTS: "report_view",
            R_LEAD: "report_view",
            R_STAR: "report_view",
            "@everyone": "deny",
        }
        await apply_rules(cat, cat_rules, roles, keep_members=False)
        count += 1
        await asyncio.sleep(0.4)

        for ch in cat.channels:
            if not isinstance(ch, discord.TextChannel):
                continue
            if ch.name in REPORT_SKIP_CHANNELS:
                continue
            if ch.name == REPORT_ALL_MODS or ch.name.startswith("📝・") or ch.name.startswith("📂・"):
                await apply_report_channel(ch, roles)
            count += 1
            await asyncio.sleep(0.45)

    return count


async def run(guild: discord.Guild) -> None:
    roles = role_map(guild)
    await guild.fetch_channels()
    applied = 0

    print("=== Специальные каналы ===")
    for ch in guild.channels:
        if ch.name in CHANNEL_RULES:
            await apply_rules(ch, CHANNEL_RULES[ch.name], roles, keep_members=False)
            applied += 1
            await asyncio.sleep(0.4)

    applied += await apply_voice_channels(guild, roles)

    locked = discord.utils.get(guild.categories, name=LOCKED_VOICE_CATEGORY)
    if locked:
        print("\n=== Закрытые войсы (категория) ===")
        await apply_rules(locked, {"@everyone": "deny"}, roles, keep_members=False)
        applied += 1

    applied += await apply_reports(guild, roles)

    print("\n=== Доступ персонала ко всем чатам ===")
    skip_names = set(CHANNEL_RULES.keys())
    for ch in guild.channels:
        if ch.name in skip_names:
            continue
        if ch.type == discord.ChannelType.category and ch.name in SKIP_CATEGORIES | {LOCKED_VOICE_CATEGORY}:
            continue
        if ch.category and ch.category.name in SKIP_CATEGORIES | {LOCKED_VOICE_CATEGORY}:
            continue

        existing = dict(ch.overwrites)
        for role_name in STAFF_ALL:
            target = roles.get(role_name)
            if target is None:
                continue
            existing[target] = ow("staff_full")

        await ch.edit(overwrites=existing, reason="DW Moderation: staff access all chats")
        applied += 1
        await asyncio.sleep(0.25)

    print(f"\n✅ Обновлено: {applied}")


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
        await run(guild)
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
