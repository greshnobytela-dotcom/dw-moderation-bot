#!/usr/bin/env python3
"""Экстренные тикеты через Настроебань."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from report_bot import (
    deploy_report_panel,
    register_report_commands,
    register_report_views,
)
from channel_styling import apply_server_styling
from salary_bot import (
    deploy_salary_panel,
    register_salary_commands,
    register_salary_views,
    save_salary_counter,
    scan_max_salary_num,
)

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

ROOT = Path(__file__).parent
DATA = ROOT / "data"
COUNTER_FILE = DATA / "ticket_counter.json"

CAT_EMERGENCY = "экстренная-связь"
CAT_EMERGENCY_ALT = "[ 📞 ] Экстренная связь"
CAT_ARCHIVE_CALLS = "[ 📦 ] Архив ・ Вызовы"
CAT_ARCHIVE_LEGACY = "[ 📦 ] Архив"
PANEL_CHANNEL = "〈📞〉・панель"
PANEL_LEGACY = ("〈-📞-〉панель", "〈-📞-〉╭・панель", "〈-📞-〉├・панель", "〈📞〉-панель")
MUSIC_CHANNEL = "〈🎵〉・музло"
MUSIC_LEGACY = ("🎵・музло", "〈-🎵-〉└・музло", "〈-🎵-〉├・музло", "『🎵』музло", "〈🎵〉-музло")

TICKET_TYPES = ["Проверка", "Бан", "Мут", "Спек", "Разбан", "Размут"]
TICKET_MODES = ["Гриф", "Анархия", "ФФА"]
MODE_NONE = "_none"

COLOR_EMERGENCY = 0xE74C3C
COLOR_FORM = 0xF39C12
COLOR_TICKET = 0xE67E22
COLOR_ARCHIVE = 0x95A5A6
COLOR_SUCCESS = 0x2ECC71

TYPE_EMOJI = {
    "Проверка": "🔍",
    "Бан": "🔨",
    "Мут": "🔇",
    "Спек": "👁️",
    "Разбан": "✅",
    "Размут": "🔊",
}

MODE_EMOJI = {
    "Гриф": "⚔️",
    "Анархия": "💀",
    "ФФА": "🎯",
}

STAFF_ROLE_NAMES = {
    "• Модерация",
    "• Модерация+",
    "• Высшая Модерация",
    "• Отдел SS",
    "• Администрация",
    "• Высшая Администрация",
    "• Руководство",
    "⭐",
}

PING_EVERYONE = "||@everyone||"

ARCHIVE_VIEW_ROLES = [
    "• Высшая Модерация",
    "• Отдел SS",
    "• Администрация",
    "• Высшая Администрация",
    "• Руководство",
    "⭐",
]

OPEN_TICKET_RE = re.compile(r"^🚨・(\d+)[-・](.+)$")
ARCHIVE_TICKET_RE = re.compile(r"^🗄️・(\d+)(?:・(.+))?$")
USER_MENTION_RE = re.compile(r"<@!?(\d+)>")
TICKET_TOPIC_RE = re.compile(
    r"num:(?P<num>\d+)\|nick:(?P<nick>[^|]+)\|type:(?P<type>[^|]+)"
    r"(?:\|mode:(?P<mode>[^|]+))?\|creator:(?P<creator>\d+)"
)

_ticket_locks: dict[int, asyncio.Lock] = {}


def _ticket_lock(guild_id: int) -> asyncio.Lock:
    if guild_id not in _ticket_locks:
        _ticket_locks[guild_id] = asyncio.Lock()
    return _ticket_locks[guild_id]


def nick_slug(nick: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in nick.lower())[:20]


def archive_channel_name(num: int, nick: str) -> str:
    return f"🗄️・{num}・{nick_slug(nick)}"


    for cat in guild.categories:
        if "экстрен" in cat.name.lower():
            return cat
    return discord.utils.get(guild.categories, name=CAT_EMERGENCY)


def scan_max_ticket_num(guild: discord.Guild) -> int:
    max_num = -1
    for ch in guild.channels:
        if not isinstance(ch, discord.TextChannel):
            continue
        m = OPEN_TICKET_RE.match(ch.name) or ARCHIVE_TICKET_RE.match(ch.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num


def save_counter(next_id: int) -> None:
    DATA.mkdir(exist_ok=True)
    COUNTER_FILE.write_text(json.dumps({"next_id": next_id}))


async def sync_ticket_counter(guild: discord.Guild) -> int:
    """Синхронизирует счётчик с реальными каналами (после удаления — снова с 0000)."""
    next_id = scan_max_ticket_num(guild) + 1
    save_counter(next_id)
    return next_id


async def reserve_ticket_id(guild: discord.Guild) -> int:
    async with _ticket_lock(guild.id):
        num = scan_max_ticket_num(guild) + 1
        save_counter(num + 1)
        return num


def open_channel_name(num: int, nick: str) -> str:
    return f"🚨・{num}・{nick_slug(nick)}"


def ticket_topic(
    num: int,
    nick: str,
    ticket_type: str,
    creator_id: int,
    mode: str | None = None,
) -> str:
    mode_part = f"|mode:{mode}" if mode else ""
    return f"num:{num}|nick:{nick}|type:{ticket_type}{mode_part}|creator:{creator_id}"


def parse_ticket_topic(topic: str | None) -> tuple[int, str, str, str | None] | None:
    if not topic:
        return None
    m = TICKET_TOPIC_RE.match(topic.strip())
    if not m:
        return None
    return (
        int(m.group("num")),
        m.group("nick"),
        m.group("type"),
        m.group("mode"),
    )


def field_plain(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            return parts[1].strip()
    return text.strip("`").strip()


def is_staff(member: discord.Member) -> bool:
    return any(r.name in STAFF_ROLE_NAMES for r in member.roles)


def build_panel_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(color=COLOR_EMERGENCY)
    embed.title = "🚨  ЭКСТРЕННАЯ СВЯЗЬ"
    embed.description = (
        "# Нажми **«Создать вызов»**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.add_field(
        name="📋  Появится форма",
        value=(
            "**Выбери тип**\n"
            "🔍 Проверка  ·  🔨 Бан  ·  🔇 Мут\n"
            "👁️ Спек  ·  ✅ Разбан  ·  🔊 Размут\n\n"
            "**Введи ник**\n"
            "Ник игрока, на которого вызов\n\n"
            "**Режим** — *по желанию*\n"
            "⚔️ Гриф  ·  💀 Анархия  ·  🎯 ФФА"
        ),
        inline=False,
    )
    embed.set_footer(text="⚡ DW Moderation  •  Экстренная связь")
    return embed


def build_form_embed() -> discord.Embed:
    types = "\n".join(f"{TYPE_EMOJI[t]}  **{t}**" for t in TICKET_TYPES)
    modes = "\n".join(f"{MODE_EMOJI[m]}  **{m}**" for m in TICKET_MODES)
    embed = discord.Embed(
        title="📝  ФОРМА ВЫЗОВА",
        description="Заполни поля ниже и нажми **Продолжить**",
        color=COLOR_FORM,
    )
    embed.add_field(name="1️⃣  Тип", value=types, inline=False)
    embed.add_field(name="2️⃣  Ник", value="Введёшь после **Продолжить**", inline=False)
    embed.add_field(name="3️⃣  Режим", value=f"{modes}\n\n*можно не выбирать*", inline=False)
    return embed


def build_ticket_embed(
    num: int,
    nick: str,
    ticket_type: str,
    creator: discord.abc.User,
    mode: str | None = None,
) -> discord.Embed:
    embed = discord.Embed(color=COLOR_EMERGENCY)
    embed.title = "🚨  ЭКСТРЕННЫЙ ВЫЗОВ"
    embed.description = (
        f"{PING_EVERYONE}\n"
        f"Номер: `#{num}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    embed.add_field(
        name="👤  НИК",
        value=f"```\n{nick}\n```",
        inline=True,
    )
    embed.add_field(
        name=f"{TYPE_EMOJI.get(ticket_type, '📋')}  ТИП",
        value=f"```\n{ticket_type}\n```",
        inline=True,
    )
    if mode:
        embed.add_field(
            name=f"{MODE_EMOJI.get(mode, '🎮')}  РЕЖИМ",
            value=f"```\n{mode}\n```",
            inline=True,
        )
    embed.add_field(name="📨  СОЗДАЛ", value=creator.mention, inline=False)
    return embed


def archive_overwrites(guild: discord.Guild) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    ows: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    for role in guild.roles:
        if role.name in ARCHIVE_VIEW_ROLES:
            ows[role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
            )
    return ows


async def ensure_archive_category(guild: discord.Guild) -> discord.CategoryChannel:
    cat = discord.utils.get(guild.categories, name=CAT_ARCHIVE_CALLS)
    ows = archive_overwrites(guild)
    if cat is None:
        legacy = discord.utils.get(guild.categories, name=CAT_ARCHIVE_LEGACY)
        if legacy is not None:
            has_salary = any(
                ch.name.startswith("🗄️・зп-")
                for ch in legacy.text_channels
                if isinstance(ch, discord.TextChannel)
            )
            has_calls = any(
                ARCHIVE_TICKET_RE.match(ch.name)
                for ch in legacy.text_channels
                if isinstance(ch, discord.TextChannel)
            )
            if has_calls and not has_salary:
                await legacy.edit(name=CAT_ARCHIVE_CALLS, overwrites=ows, reason="Архив вызовов")
                return legacy
        return await guild.create_category(
            CAT_ARCHIVE_CALLS,
            overwrites=ows,
            reason="Архив экстренных вызовов",
        )
    await cat.edit(overwrites=ows, reason="Архив вызовов: права")
    return cat


async def migrate_calls_archive(guild: discord.Guild) -> None:
    calls_arch = await ensure_archive_category(guild)
    moved = 0

    for ch in guild.text_channels:
        if ARCHIVE_TICKET_RE.match(ch.name) and not ch.name.startswith("🗄️・зп-"):
            if ch.category_id != calls_arch.id:
                await ch.edit(
                    category=calls_arch,
                    overwrites=archive_overwrites(guild),
                    reason="Архив вызовов → отдельная категория",
                )
                moved += 1

    legacy = discord.utils.get(guild.categories, name=CAT_ARCHIVE_LEGACY)
    if legacy:
        for ch in list(legacy.text_channels):
            if ARCHIVE_TICKET_RE.match(ch.name) and not ch.name.startswith("🗄️・зп-"):
                await ch.edit(
                    category=calls_arch,
                    overwrites=archive_overwrites(guild),
                    reason="Перенос вызовов из общего архива",
                )
                moved += 1

    if moved:
        print(f"  ✓ вызовы: перенесено в архив — {moved}")

    renamed = await fix_legacy_calls_archive_channels(guild)
    if renamed:
        print(f"  ✓ вызовы: архив с ником — {renamed}")


async def fix_legacy_calls_archive_channels(guild: discord.Guild) -> int:
    """Старые 🗄️・N → 🗄️・N・ник."""
    fixed = 0
    calls_arch = discord.utils.get(guild.categories, name=CAT_ARCHIVE_CALLS)
    for ch in guild.text_channels:
        if ch.name.startswith("🗄️・зп-"):
            continue
        m = ARCHIVE_TICKET_RE.match(ch.name)
        if not m or m.group(2):
            continue
        if calls_arch and ch.category_id != calls_arch.id:
            legacy_cat = discord.utils.get(guild.categories, name=CAT_ARCHIVE_LEGACY)
            if not legacy_cat or ch.category_id != legacy_cat.id:
                continue
        meta = await read_ticket_meta(ch)
        if meta is None:
            print(f"  ⚠ архив {ch.name}: мета не прочитана")
            continue
        num, nick, _, _ = meta
        if nick in ("?", ""):
            print(f"  ⚠ архив {ch.name}: ник пустой")
            continue
        new_name = archive_channel_name(num, nick)
        if ch.name != new_name:
            await ch.edit(name=new_name, reason="Архив вызовов: добавить ник в название")
            print(f"  ✓ {ch.name} → {new_name}")
            fixed += 1
    return fixed


async def read_ticket_meta(channel: discord.TextChannel) -> tuple[int, str, str, str | None] | None:
    from_topic = parse_ticket_topic(channel.topic)
    if from_topic is not None:
        return from_topic

    m = OPEN_TICKET_RE.match(channel.name)
    if m:
        num = int(m.group(1))
        nick = m.group(2).replace("-", " ")
    else:
        m2 = ARCHIVE_TICKET_RE.match(channel.name)
        if not m2:
            return None
        num = int(m2.group(1))
        nick = (m2.group(2) or "?").replace("-", " ")

    ticket_type, mode = "?", None
    async for msg in channel.history(limit=30, oldest_first=True):
        if not msg.embeds:
            continue
        for emb in msg.embeds:
            title = emb.title or ""
            if "вызов" not in title.lower() and "архив" not in title.lower():
                continue

            for field in emb.fields:
                name = field.name
                val = field_plain(field.value)
                if "НИК" in name.upper() or name.endswith("Ник"):
                    nick = val
                elif "ТИП" in name.upper() or name.endswith("Тип"):
                    ticket_type = val
                elif "РЕЖИМ" in name.upper() or name.endswith("Режим"):
                    mode = val
                elif "Ник" in name:
                    nick = val
                elif "Тип" in name:
                    ticket_type = val
                elif "Режим" in name:
                    mode = val

            if emb.description:
                for line in emb.description.splitlines():
                    if "Номер:" in line and "·" in line:
                        nick_m = re.search(r"·\s*\*\*(.+?)\*\*", line)
                        if nick_m:
                            nick = nick_m.group(1)
                    if "**Ник:**" in line:
                        nick = line.split("**Ник:**", 1)[1].strip()
                    elif "**Тип:**" in line:
                        raw = line.split("**Тип:**", 1)[1].strip()
                        for t in TICKET_TYPES:
                            if t in raw:
                                ticket_type = t
                                break
                    elif "**Режим:**" in line:
                        raw = line.split("**Режим:**", 1)[1].strip()
                        for m in TICKET_MODES:
                            if m in raw:
                                mode = m
                                break
    return num, nick, ticket_type, mode


async def read_ticket_creator_id(channel: discord.TextChannel) -> int | None:
    async for msg in channel.history(limit=20, oldest_first=True):
        if not msg.embeds:
            continue
        emb = msg.embeds[0]
        if "вызов" not in (emb.title or "").lower():
            continue
        for field in emb.fields:
            if "СОЗДАЛ" in field.name.upper():
                m = USER_MENTION_RE.search(field.value)
                if m:
                    return int(m.group(1))
    return None


async def disable_ticket_controls(channel: discord.TextChannel) -> None:
    guild = channel.guild
    me = guild.me
    if me is None:
        return
    view = TicketControlView()
    for item in view.children:
        item.disabled = True
    async for msg in channel.history(limit=25):
        if msg.author.id == me.id and msg.components:
            try:
                await msg.edit(view=view)
            except discord.HTTPException:
                pass
            return


def is_open_ticket_channel(channel: discord.TextChannel) -> bool:
    return bool(OPEN_TICKET_RE.match(channel.name))


async def cancel_ticket_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    ticket_num: int,
    nick: str,
    ticket_type: str,
    mode: str | None = None,
) -> None:
    guild = channel.guild
    archive_cat = await ensure_archive_category(guild)
    archive_name = archive_channel_name(ticket_num, nick)
    ows = archive_overwrites(guild)

    embed = discord.Embed(color=COLOR_ARCHIVE)
    embed.title = f"📦  АРХИВ  #{ticket_num}"
    embed.description = (
        f"**На кого вызов:** `{nick}`\n"
        f"Отменён: {interaction.user.mention}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.add_field(
        name="👤  НИК",
        value=f"```\n{nick}\n```",
        inline=True,
    )
    embed.add_field(
        name=f"{TYPE_EMOJI.get(ticket_type, '📋')}  ТИП",
        value=f"```\n{ticket_type}\n```",
        inline=True,
    )
    if mode:
        embed.add_field(
            name=f"{MODE_EMOJI.get(mode, '🎮')}  РЕЖИМ",
            value=f"```\n{mode}\n```",
            inline=True,
        )

    await channel.send(embed=embed)
    try:
        await channel.edit(
            name=archive_name,
            category=archive_cat,
            overwrites=ows,
            topic=ticket_topic(ticket_num, nick, ticket_type, interaction.user.id, mode),
            reason=f"Cancel ticket {ticket_num}",
        )
        await disable_ticket_controls(channel)
    except discord.HTTPException as exc:
        print(f"  ⚠ архив вызова #{ticket_num}: {exc}")


async def close_ticket_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    ticket_num: int,
    nick: str,
    ticket_type: str,
    mode: str | None = None,
    moderator: discord.abc.User | None = None,
    creator: discord.abc.User | None = None,
) -> None:
    guild = channel.guild
    archive_cat = await ensure_archive_category(guild)
    archive_name = archive_channel_name(ticket_num, nick)
    ows = archive_overwrites(guild)

    mod = moderator or interaction.user
    who = creator or interaction.user
    embed = discord.Embed(color=COLOR_ARCHIVE)
    embed.title = f"📦  АРХИВ  #{ticket_num}"
    if mod.id == who.id:
        embed.description = (
            f"**На кого вызов:** `{nick}`\n"
            f"Закрыл: {mod.mention}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        embed.description = (
            f"**На кого вызов:** `{nick}`\n"
            f"Модератор: {mod.mention}\n"
            f"Подтвердил: {who.mention}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    embed.add_field(
        name="👤  НИК",
        value=f"```\n{nick}\n```",
        inline=True,
    )
    embed.add_field(
        name=f"{TYPE_EMOJI.get(ticket_type, '📋')}  ТИП",
        value=f"```\n{ticket_type}\n```",
        inline=True,
    )
    if mode:
        embed.add_field(
            name=f"{MODE_EMOJI.get(mode, '🎮')}  РЕЖИМ",
            value=f"```\n{mode}\n```",
            inline=True,
        )

    await channel.send(embed=embed)
    creator_id = creator.id if creator else interaction.user.id
    try:
        await channel.edit(
            name=archive_name,
            category=archive_cat,
            overwrites=ows,
            topic=ticket_topic(ticket_num, nick, ticket_type, creator_id, mode),
            reason=f"Archive ticket {ticket_num}",
        )
        await disable_ticket_controls(channel)
    except discord.HTTPException as exc:
        print(f"  ⚠ архив вызова #{ticket_num}: {exc}")


class TypeSelect(discord.ui.Select):
    def __init__(self, form: TicketFormView) -> None:
        self.form = form
        options = [
            discord.SelectOption(
                label=t,
                value=t,
                emoji=TYPE_EMOJI.get(t),
            )
            for t in TICKET_TYPES
        ]
        super().__init__(
            placeholder="📌  Выбери тип вызова",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.form.ticket_type = self.values[0]
        await interaction.response.defer()


class ModeSelect(discord.ui.Select):
    def __init__(self, form: TicketFormView) -> None:
        self.form = form
        options = [
            discord.SelectOption(
                label="Не указан",
                value=MODE_NONE,
                emoji="➖",
            )
        ]
        options.extend(
            discord.SelectOption(
                label=m,
                value=m,
                emoji=MODE_EMOJI.get(m),
            )
            for m in TICKET_MODES
        )
        super().__init__(
            placeholder="🎮  Режим (необязательно)",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.form.mode = None if self.values[0] == MODE_NONE else self.values[0]
        await interaction.response.defer()


class TicketFormView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.ticket_type: str | None = None
        self.mode: str | None = None
        self.add_item(TypeSelect(self))
        self.add_item(ModeSelect(self))

    @discord.ui.button(label="Продолжить", style=discord.ButtonStyle.success, emoji="✏️", row=2)
    async def continue_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.ticket_type:
            await interaction.response.send_message("⚠️ Сначала выбери **тип**.", ephemeral=True)
            return
        await interaction.response.send_modal(NickModal(self.ticket_type, self.mode))


class NickModal(discord.ui.Modal, title="👤  Введи ник"):
    def __init__(self, ticket_type: str, mode: str | None = None) -> None:
        super().__init__()
        self.ticket_type = ticket_type
        self.mode = mode
        self.nick = discord.ui.TextInput(
            label="Ник игрока",
            placeholder="Введите никнейм",
            required=True,
            max_length=64,
            style=discord.TextStyle.short,
        )
        self.add_item(self.nick)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return

        em_cat = find_emergency_category(guild)
        if em_cat is None:
            await interaction.followup.send(
                "Категория экстренной связи не найдена.",
                ephemeral=True,
            )
            return

        num = await reserve_ticket_id(guild)
        nick_str = str(self.nick.value)
        channel_name = open_channel_name(num, nick_str)

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            ),
        }
        for role in guild.roles:
            if role.name in STAFF_ROLE_NAMES:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )
        me = guild.me
        if me:
            overwrites[me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                mention_everyone=True,
            )

        channel = await guild.create_text_channel(
            channel_name,
            category=em_cat,
            overwrites=overwrites,
            topic=ticket_topic(num, nick_str, self.ticket_type, interaction.user.id, self.mode),
            reason=f"Emergency #{num}",
        )

        embed = build_ticket_embed(
            num, nick_str, self.ticket_type, interaction.user, self.mode
        )

        await channel.send(
            embed=embed,
            view=TicketControlView(),
            allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=False),
        )
        done = discord.Embed(
            description=f"✅ Вызов создан: {channel.mention}",
            color=COLOR_SUCCESS,
        )
        await interaction.followup.send(embed=done, ephemeral=True)


class EmergencyPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Создать вызов",
        style=discord.ButtonStyle.danger,
        emoji="🚨",
        custom_id="emergency_create_btn",
    )
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_message(
            embed=build_form_embed(),
            view=TicketFormView(),
            ephemeral=True,
        )


class CreatorConfirmView(discord.ui.View):
    def __init__(self, creator_id: int, moderator_id: int) -> None:
        super().__init__(timeout=86400)
        self.creator_id = creator_id
        self.moderator_id = moderator_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                "Подтвердить может только **создатель вызова**.",
                ephemeral=True,
            )
            return False
        return True

    async def _disable(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Да, выполнено", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_yes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return

        meta = await read_ticket_meta(channel)
        if meta is None:
            await interaction.followup.send("Не удалось прочитать данные вызова.", ephemeral=True)
            return

        ticket_num, nick, ticket_type, mode = meta
        guild = channel.guild
        moderator = guild.get_member(self.moderator_id) if guild else None

        await close_ticket_channel(
            interaction,
            channel,
            ticket_num,
            nick,
            ticket_type,
            mode,
            moderator=moderator,
            creator=interaction.user,
        )
        await self._disable(interaction)
        await interaction.followup.send(f"✅ Вызов #{ticket_num} подтверждён и перенесён в архив.")

    @discord.ui.button(label="Нет, не выполнено", style=discord.ButtonStyle.danger, emoji="❌")
    async def confirm_no(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return

        guild = channel.guild
        moderator = guild.get_member(self.moderator_id) if guild else None
        mod_mention = moderator.mention if moderator else "модератор"

        await channel.send(
            embed=discord.Embed(
                title="❌  Вызов не выполнен",
                description=(
                    f"{interaction.user.mention} сообщил, что вызов **ещё не выполнен**.\n"
                    f"{mod_mention}, продолжи работу."
                ),
                color=COLOR_EMERGENCY,
            )
        )
        await self._disable(interaction)
        await interaction.followup.send("Ответ отправлен. Модератор продолжит работу.")


class TicketControlView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Принял вызов",
        style=discord.ButtonStyle.primary,
        emoji="✋",
        custom_id="emergency_claim_btn",
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("Только модерация.", ephemeral=True)
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return
        if not is_open_ticket_channel(channel):
            await interaction.response.send_message("Вызов уже закрыт.", ephemeral=True)
            return

        creator_id = await read_ticket_creator_id(channel)
        if creator_id and interaction.user.id == creator_id:
            await interaction.response.send_message(
                "Нельзя принять **свой** вызов.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="✋  Принялся за вызов",
                description=interaction.user.mention,
                color=COLOR_FORM,
            )
        )

    @discord.ui.button(
        label="Отменить",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="emergency_cancel_btn",
        row=1,
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return
        if not is_open_ticket_channel(channel):
            await interaction.response.send_message("Вызов уже закрыт.", ephemeral=True)
            return

        creator_id = await read_ticket_creator_id(channel)
        is_creator = creator_id == interaction.user.id
        is_mod = isinstance(interaction.user, discord.Member) and is_staff(interaction.user)

        if not is_creator and not is_mod:
            await interaction.response.send_message(
                "Отменить может **создатель** или **модерация**.",
                ephemeral=True,
            )
            return

        meta = await read_ticket_meta(channel)
        if meta is None:
            await interaction.response.send_message("Не удалось прочитать вызов.", ephemeral=True)
            return

        ticket_num, nick, ticket_type, mode = meta
        await interaction.response.defer()
        await cancel_ticket_channel(interaction, channel, ticket_num, nick, ticket_type, mode)
        await interaction.followup.send(f"Вызов #{ticket_num} отменён и перенесён в архив.")

    @discord.ui.button(
        label="Готово — закрыть",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="emergency_close_btn",
        row=0,
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("Только модерация.", ephemeral=True)
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return
        if not is_open_ticket_channel(channel):
            await interaction.response.send_message("Вызов уже закрыт.", ephemeral=True)
            return

        creator_id = await read_ticket_creator_id(channel)
        if creator_id is None:
            await interaction.response.send_message("Не найден создатель вызова.", ephemeral=True)
            return

        creator = channel.guild.get_member(creator_id)
        creator_mention = creator.mention if creator else f"<@{creator_id}>"

        await interaction.response.send_message(
            embed=discord.Embed(
                title="📨  Запрос подтверждения",
                description=(
                    f"{creator_mention}, модератор {interaction.user.mention} завершил работу.\n\n"
                    "**Вызов был выполнен?**"
                ),
                color=COLOR_FORM,
            ),
            view=CreatorConfirmView(creator_id, interaction.user.id),
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        await interaction.followup.send(
            f"Ожидаем подтверждение от {creator_mention}.",
            ephemeral=True,
        )


async def deploy_panel(guild: discord.Guild) -> None:
    panel = discord.utils.get(guild.text_channels, name=PANEL_CHANNEL)
    if panel is None:
        for legacy in PANEL_LEGACY:
            panel = discord.utils.get(guild.text_channels, name=legacy)
            if panel:
                await panel.edit(name=PANEL_CHANNEL, reason="DW: DuckWorld panel style")
                print(f"  ✓ панель: {legacy} → {PANEL_CHANNEL}")
                break
    if panel is None:
        print(f"  ⚠ канал {PANEL_CHANNEL} не найден")
        return

    me = guild.me
    if me is None:
        return

    async for msg in panel.history(limit=15):
        if msg.author.id == me.id:
            await msg.delete()

    embed = build_panel_embed(guild)
    await panel.send(embed=embed, view=EmergencyPanelView())
    print(f"  ✓ панель в #{PANEL_CHANNEL}")


class DWBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self.add_view(EmergencyPanelView())
        self.add_view(TicketControlView())
        register_report_views(self)
        register_report_commands(self.tree)
        register_salary_views(self)
        register_salary_commands(self.tree)
        guild_id = int(os.getenv("DISCORD_GUILD_ID", "0"))
        self.tree.copy_global_to(guild=discord.Object(id=guild_id))
        await self.tree.sync(guild=discord.Object(id=guild_id))

    async def on_ready(self) -> None:
        print(f"Бот запущен: {self.user}")
        guild_id = int(os.getenv("DISCORD_GUILD_ID", "0"))
        guild = self.get_guild(guild_id)
        if guild:
            await guild.fetch_channels()
            try:
                await guild.chunk()
            except discord.HTTPException:
                pass
            if os.getenv("BOT_LITE_STARTUP") == "1":
                print("  lite startup: только панели")
                await migrate_calls_archive(guild)
                await deploy_panel(guild)
                await deploy_report_panel(guild)
                await deploy_salary_panel(guild)
                return
            await apply_server_styling(guild)
            await sync_ticket_counter(guild)
            save_salary_counter(scan_max_salary_num(guild) + 1)
            await migrate_calls_archive(guild)
            await deploy_panel(guild)
            await deploy_report_panel(guild)
            await deploy_salary_panel(guild)


bot = DWBot()


@bot.tree.command(name="music-here", description="Напоминание: музыка только в канале музло")
async def music_here(interaction: discord.Interaction) -> None:
    ch_name = getattr(interaction.channel, "name", "")
    if ch_name != MUSIC_CHANNEL and ch_name not in MUSIC_LEGACY:
        ch = None
        if interaction.guild:
            for name in (MUSIC_CHANNEL, *MUSIC_LEGACY):
                ch = discord.utils.get(interaction.guild.text_channels, name=name)
                if ch:
                    break
        ref = ch.mention if ch else MUSIC_CHANNEL
        await interaction.response.send_message(
            f"Музыка только в {ref}. VK Music Bot: `/play`, `/queue`.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message("Здесь можно `/play` (VK Music Bot).", ephemeral=True)


def main() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    bot.run(token)


if __name__ == "__main__":
    main()
