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
        "send_messages": False,
        "read_message_history": True,
        "connect": True,
        "speak": True,
        "stream": True,
    },
    "view_no_manage": {
        "view_channel": True,
        "send_messages": False,
        "read_message_history": True,
        "connect": True,
        "speak": True,
        "stream": True,
        "manage_channels": False,
        "manage_messages": False,
        "manage_roles": False,
    },
    "panel_click": {
        "view_channel": True,
        "send_messages": False,
        "read_message_history": True,
        "add_reactions": False,
        "attach_files": False,
        "embed_links": False,
    },
    "panel_bot": {
        "view_channel": True,
        "send_messages": True,
        "read_message_history": True,
        "manage_messages": True,
        "embed_links": True,
        "mention_everyone": True,
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
R_JUNIOR_ADMIN = "• Младшая Администрация"
R_HIGH_MOD = "• Высшая Модерация"
R_SS = "• Отдел SS"
R_MOD_PLUS = "• Модерация+"
R_MOD = "• Модерация"
R_PASS = "• Проходка"
R_DEPUTY = "•  Депутат"
R_PRIVATE = "•  Приват"
R_REPORTS = "•  Доступ к отчётам"

# Права Discord-роли для Младшая Администрация (= набор Модерация+)
MOD_PLUS_ROLE_PERMISSIONS = discord.Permissions(
    view_channel=True,
    send_messages=True,
    send_messages_in_threads=True,
    create_public_threads=True,
    create_private_threads=True,
    embed_links=True,
    attach_files=True,
    add_reactions=True,
    use_external_emojis=True,
    use_external_stickers=True,
    mention_everyone=False,
    manage_messages=True,
    read_message_history=True,
    use_application_commands=True,
    change_nickname=True,
    manage_nicknames=True,
    connect=True,
    speak=True,
    stream=True,
    use_voice_activation=True,
    priority_speaker=True,
    mute_members=True,
    deafen_members=True,
    move_members=True,
    moderate_members=True,
    bypass_slowmode=True,
)

# Роли выше обычной модерации + сами модераторы — одни и те же войсы
VOICE_STAFF = [
    R_STAR,
    R_LEAD,
    R_HIGH_ADMIN,
    R_ADMIN,
    R_JUNIOR_ADMIN,
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

# [ 📚 ] Основное — пишет только Администрация и выше, остальные только читают
MAIN_CATEGORY_KEYS = ("основное",)
_CHANNEL_MAIN = {
    R_STAR: "full",
    R_LEAD: "full",
    R_HIGH_ADMIN: "full",
    R_ADMIN: "full",
    R_JUNIOR_ADMIN: "view_no_manage",
    R_HIGH_MOD: "view_no_manage",
    R_SS: "view_no_manage",
    R_MOD_PLUS: "view_no_manage",
    R_MOD: "view_no_manage",
    R_PASS: "view",
    "@everyone": "view",
}

# Панели (вызовы / отчёты / зарплата) — только смотреть и жать кнопки
PANEL_CHANNEL_NAMES = {
    "〈📞〉・панель",
    "〈📞〉-панель",
    "〈📋〉・создание",
    "〈📋〉-создание",
    "📋・создание",
    "создание-отчёта",
    "〈💵〉・зарплата",
    "〈💰〉・зарплата",
    "〈💰〉-зарплата",
    "💰・зарплата",
    "💵・зарплата",
    "получение-зарплаты",
}
_CHANNEL_PANEL = {
    R_STAR: "panel_click",
    R_LEAD: "panel_click",
    R_HIGH_ADMIN: "panel_click",
    R_ADMIN: "panel_click",
    R_JUNIOR_ADMIN: "panel_click",
    R_HIGH_MOD: "panel_click",
    R_SS: "panel_click",
    R_MOD_PLUS: "panel_click",
    R_MOD: "panel_click",
    R_PASS: "panel_click",
    "@everyone": "panel_click",
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
    "🍷・алкоголики": {
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
        R_JUNIOR_ADMIN: "report_view",
        R_HIGH_MOD: "report_view",
        R_SS: "report_view",
        R_MOD_PLUS: "report_view",
        R_MOD: "report_view",
        "@everyone": "deny",
    },
}


def is_main_category(name: str | None) -> bool:
    if not name:
        return False
    low = name.lower()
    return any(key in low for key in MAIN_CATEGORY_KEYS)


def is_main_category_channel(channel: discord.abc.GuildChannel) -> bool:
    if not isinstance(channel, discord.TextChannel):
        return False
    return is_main_category(channel.category.name if channel.category else None)


def is_panel_channel(channel: discord.abc.GuildChannel) -> bool:
    return isinstance(channel, discord.TextChannel) and channel.name in PANEL_CHANNEL_NAMES

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
        if isinstance(key, discord.abc.Snowflake) and not isinstance(key, discord.Role):
            overwrites[key] = ow(preset)
            continue
        target = roles.get(key) if isinstance(key, str) else key
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
        for role_name in [R_MOD, R_MOD_PLUS, R_JUNIOR_ADMIN, R_HIGH_MOD, R_SS, R_REPORTS]:
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

    print("\n=== Основное (только Администрация пишет) ===")
    for cat in guild.categories:
        if not is_main_category(cat.name):
            continue
        await apply_rules(cat, _CHANNEL_MAIN, roles, keep_members=False)
        applied += 1
        await asyncio.sleep(0.35)
        for ch in cat.text_channels:
            await apply_rules(ch, _CHANNEL_MAIN, roles, keep_members=False)
            applied += 1
            await asyncio.sleep(0.35)

    print("\n=== Панели (только кнопки, без сообщений) ===")
    for ch in guild.text_channels:
        if not is_panel_channel(ch):
            continue
        rules = dict(_CHANNEL_PANEL)
        me = guild.me
        if me:
            rules[me] = "panel_bot"
        await apply_rules(ch, rules, roles, keep_members=False)
        applied += 1
        await asyncio.sleep(0.35)

    print("\n=== Доступ персонала ко всем чатам ===")
    skip_names = set(CHANNEL_RULES.keys()) | PANEL_CHANNEL_NAMES
    for ch in guild.channels:
        if ch.name in skip_names or is_main_category_channel(ch) or is_panel_channel(ch):
            continue
        if ch.type == discord.ChannelType.category and is_main_category(ch.name):
            continue
        if ch.type == discord.ChannelType.category and ch.name in SKIP_CATEGORIES | {LOCKED_VOICE_CATEGORY}:
            continue
        if ch.category and ch.category.name in SKIP_CATEGORIES | {LOCKED_VOICE_CATEGORY}:
            continue
        if ch.category and is_main_category(ch.category.name):
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

    print("\n=== Младшая Администрация = Модерация+ ===")
    applied += await sync_junior_admin_like_mod_plus(guild, roles)

    print(f"\n✅ Обновлено: {applied}")


async def sync_junior_admin_like_mod_plus(
    guild: discord.Guild,
    roles: dict[str, discord.Role],
) -> int:
    """Права роли + каналы: Младшая Администрация = точная копия Модерация+."""
    modp = roles.get(R_MOD_PLUS)
    junior = roles.get(R_JUNIOR_ADMIN)
    if modp is None or junior is None:
        print("  ⚠ нет роли Модерация+ или Младшая Администрация")
        return 0

    fixed = 0
    try:
        await junior.edit(
            permissions=MOD_PLUS_ROLE_PERMISSIONS,
            colour=modp.colour,
            hoist=True,
            mentionable=modp.mentionable,
            reason="Младшая Адм: права роли (текст/войс/мод)",
        )
        print(f"  ✓ права роли Младшая Администрация value={MOD_PLUS_ROLE_PERMISSIONS.value}")
        fixed += 1
    except discord.HTTPException as exc:
        print(f"  ⚠ sync role junior: {exc}")

    try:
        await modp.edit(
            permissions=MOD_PLUS_ROLE_PERMISSIONS,
            reason="Модерация+: тот же набор прав роли",
        )
        print("  ✓ права роли Модерация+")
        fixed += 1
    except discord.HTTPException as exc:
        print(f"  ⚠ Модерация+ не обновлена (роль бота ниже): {exc}")

    for ch in guild.channels:
        ow_m = ch.overwrites_for(modp)
        has_mod = any(v is not None for _, v in ow_m)
        ow_j = ch.overwrites_for(junior)
        has_jr = any(v is not None for _, v in ow_j)
        if not has_mod:
            if has_jr:
                await ch.set_permissions(junior, overwrite=None, reason="Младшая Адм = Модерация+")
                fixed += 1
                await asyncio.sleep(0.2)
            continue
        m_pairs = sorted((k, v) for k, v in ow_m if v is not None)
        j_pairs = sorted((k, v) for k, v in ow_j if v is not None)
        if m_pairs == j_pairs:
            continue
        await ch.set_permissions(junior, overwrite=ow_m, reason="Младшая Адм = Модерация+")
        print(f"  ✓ sync {ch.name}")
        fixed += 1
        await asyncio.sleep(0.25)
    return fixed


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
