#!/usr/bin/env python3
"""Панель отчётов: быстрое создание канала для модератора с правами."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote

import aiohttp
import discord
from discord import app_commands

if TYPE_CHECKING:
    from ticket_bot import DWBot

REPORT_CATEGORY = "[ 📋 ] Отчёты"
REPORT_PANEL_OLD = "создание-отчёта"
REPORT_PANEL = "〈📋〉・создание"
REPORT_PANEL_LEGACY = ("📋・создание", "〈-📋-〉╭・создание", "создание-отчёта", "〈📋〉-создание")
REPORT_LEGACY_PANEL = "📋・панель"
REPORT_ALL_MODS = "〈📂〉・все-проверки"
REPORT_ALL_LEGACY = ("📂・все-проверки", "〈-📂-〉╭・все-проверки", "отчёты-всех-проверок", "〈📂〉-все-проверки")
REPORT_CHANNEL_RE = re.compile(r"^📝・(.+)$")

R_HIGH_ADMIN = "• Высшая Администрация"
R_ADMIN = "• Администрация"
R_HIGH_MOD = "• Высшая Модерация"
R_SS = "• Отдел SS"
R_REPORTS = "•  Доступ к отчётам"
R_LEAD = "• Руководство"
R_STAR = "⭐"
R_MOD = "• Модерация"
R_MOD_PLUS = "• Модерация+"

REPORT_MOD_ROLES = (R_MOD, R_MOD_PLUS, R_HIGH_MOD)

REPORT_VIEWERS = [R_ADMIN, R_HIGH_ADMIN, R_HIGH_MOD, R_SS, R_REPORTS, R_LEAD, R_STAR]
REPORT_ADMIN_ROLES = {R_ADMIN, R_HIGH_ADMIN, R_LEAD, R_STAR}

COLOR_PANEL = 0x3498DB
COLOR_FORM = 0x5DADE2
COLOR_SUCCESS = 0x2ECC71
COLOR_INFO = 0x9B59B6
COLOR_DANGER = 0xE74C3C

ReportAction = Literal["create", "delete", "refresh"]


def is_report_admin(member: discord.Member) -> bool:
    return any(r.name in REPORT_ADMIN_ROLES for r in member.roles)


def is_report_moderator(member: discord.Member) -> bool:
    if member.bot:
        return False
    return any(r.name in REPORT_MOD_ROLES for r in member.roles)


async def resolve_member(guild: discord.Guild, user_id: int) -> discord.Member | discord.Object:
    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except discord.HTTPException:
        return discord.Object(id=user_id)


def slugify(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower())
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe[:32] or "mod"


def channel_nick_from_member(member: discord.Member) -> str:
    """Ник для канала — часть после | в серверном нике."""
    display = member.display_name
    if "|" in display:
        tail = display.split("|", 1)[1].strip()
        if tail:
            return tail
    return member.name


def member_search_keys(member: discord.Member) -> list[str]:
    keys = [
        channel_nick_from_member(member),
        member.name,
        member.display_name,
    ]
    if member.global_name:
        keys.append(member.global_name)
    return [k.lower() for k in keys if k]


def parse_nick_input(content: str) -> str:
    mention = re.search(r"<@!?(\d+)>", content)
    if mention:
        return f"uid:{mention.group(1)}"
    text = re.sub(r"<@!?\d+>", "", content).strip()
    if text.startswith("@"):
        text = text[1:].strip()
    return text


def member_matches_query(member: discord.Member, query: str) -> bool:
    q = query.lower().strip()
    q_slug = slugify(query)
    for key in member_search_keys(member):
        if key == q or slugify(key) == q_slug:
            return True
        if q in key or key in q:
            return True
    return False


async def _search_members_api(guild: discord.Guild, query: str) -> list[discord.Member]:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token or len(query) < 2:
        return []

    headers = {"Authorization": f"Bot {token}"}
    url = (
        f"https://discord.com/api/v10/guilds/{guild.id}/members/search"
        f"?query={quote(query)}&limit=25"
    )
    found: list[discord.Member] = []
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            batch = await resp.json()

    for raw in batch:
        if raw.get("user", {}).get("bot"):
            continue
        uid = int(raw["user"]["id"])
        member = guild.get_member(uid)
        if member is None:
            try:
                member = await guild.fetch_member(uid)
            except discord.HTTPException:
                continue
        found.append(member)
    return found


def moderator_from_report_channel(channel: discord.TextChannel) -> discord.Member | None:
    for target, ow in channel.overwrites.items():
        if isinstance(target, discord.Member) and not target.bot and ow.send_messages is True:
            return target
    return None


async def find_moderators_by_report_channels(
    guild: discord.Guild,
    query: str,
) -> list[discord.Member]:
    q = query.lower().strip()
    q_slug = slugify(query)
    found: dict[int, discord.Member] = {}

    for ch in list_personal_report_channels(guild):
        m = REPORT_CHANNEL_RE.match(ch.name)
        if not m:
            continue
        ch_nick = m.group(1).lower()
        ch_slug = slugify(m.group(1))
        if q_slug != ch_slug and q != ch_nick and q not in ch_nick and ch_nick not in q:
            continue
        mod = moderator_from_report_channel(ch)
        if mod is not None:
            found[mod.id] = mod

    direct = find_report_channel(guild, q_slug)
    if direct is not None:
        mod = moderator_from_report_channel(direct)
        if mod is not None:
            found[mod.id] = mod

    return list(found.values())


async def find_moderators_in_voice(
    guild: discord.Guild,
    query: str,
) -> list[discord.Member]:
    found: dict[int, discord.Member] = {}
    for vc in guild.voice_channels + guild.stage_channels:
        for member in vc.members:
            if is_report_moderator(member) and member_matches_query(member, query):
                found[member.id] = member
    return list(found.values())


async def find_moderators_by_nick(guild: discord.Guild, query: str) -> list[discord.Member]:
    query = parse_nick_input(query)
    if query.startswith("uid:"):
        uid = int(query[4:])
        try:
            member = await guild.fetch_member(uid)
            return [member]
        except discord.HTTPException:
            return []

    if len(query) < 2:
        return []

    matches: dict[int, discord.Member] = {}

    for member in await find_moderators_by_report_channels(guild, query):
        matches[member.id] = member
    if matches:
        return list(matches.values())

    for member in await _search_members_api(guild, query):
        if is_report_moderator(member) and member_matches_query(member, query):
            matches[member.id] = member
    if matches:
        return list(matches.values())

    for member in guild.members:
        if is_report_moderator(member) and member_matches_query(member, query):
            matches[member.id] = member
    if matches:
        return list(matches.values())

    for member in await _search_members_api(guild, query):
        if member.id in matches:
            continue
        if not is_report_moderator(member):
            continue
        if member_matches_query(member, query):
            matches[member.id] = member

    return list(matches.values())


def report_nick_for_channel(moderator: discord.abc.User) -> str:
    if isinstance(moderator, discord.Member):
        return channel_nick_from_member(moderator)
    return moderator.name


def default_slug(moderator: discord.abc.User) -> str:
    return slugify(report_nick_for_channel(moderator))


def report_channel_name(nick: str) -> str:
    return f"📝・{slugify(nick)}"


def find_report_channel(guild: discord.Guild, slug: str) -> discord.TextChannel | None:
    target = report_channel_name(slug)
    return discord.utils.get(guild.text_channels, name=target)


def is_personal_report_channel(channel: discord.abc.GuildChannel) -> bool:
    return isinstance(channel, discord.TextChannel) and bool(REPORT_CHANNEL_RE.match(channel.name))


def list_personal_report_channels(guild: discord.Guild) -> list[discord.TextChannel]:
    cat = discord.utils.get(guild.categories, name=REPORT_CATEGORY)
    if cat is None:
        return []
    return [
        ch
        for ch in cat.text_channels
        if is_personal_report_channel(ch)
    ]


def find_channel_for_member(
    guild: discord.Guild,
    member: discord.abc.User,
) -> discord.TextChannel | None:
    cat = discord.utils.get(guild.categories, name=REPORT_CATEGORY)
    if cat is None:
        return None

    for ch in cat.text_channels:
        if not is_personal_report_channel(ch):
            continue
        ow = ch.overwrites.get(member)
        if ow and ow.send_messages is True:
            return ch

    for candidate in (
        channel_nick_from_member(member) if isinstance(member, discord.Member) else None,
        member.name,
        getattr(member, "display_name", None),
        member.global_name if hasattr(member, "global_name") else None,
    ):
        if candidate:
            found = find_report_channel(guild, candidate)
            if found:
                return found
    return None


def build_report_overwrites(
    guild: discord.Guild,
    moderator: discord.abc.User,
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        moderator: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
        ),
    }
    for role in guild.roles:
        if role.name in REPORT_VIEWERS:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
            )
    me = guild.me
    if me:
        overwrites[me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
        )
    return overwrites


def build_panel_embed() -> discord.Embed:
    embed = discord.Embed(color=COLOR_PANEL)
    embed.title = "📋  УПРАВЛЕНИЕ ОТЧЁТАМИ"
    embed.description = (
        "# **Создать** или **удалить** канал модератора\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.add_field(
        name="➕  Создать",
        value=(
            "Нажми **Создать отчёт** → введи **ник** (без @).\n"
            "Бот найдёт человека на сервере и создаст `📝・ник`."
        ),
        inline=False,
    )
    embed.add_field(
        name="➖  Удалить",
        value="Нажми **Удалить отчёт** → введи **ник** модератора.",
        inline=False,
    )
    embed.add_field(
        name="🔒  Доступ",
        value="Только **администрация**.",
        inline=False,
    )
    embed.set_footer(text="⚡ DW Moderation  •  Отчёты")
    return embed


def build_report_welcome_embed(
    moderator: discord.abc.User,
    creator: discord.abc.User,
) -> discord.Embed:
    embed = discord.Embed(color=COLOR_INFO)
    embed.title = "📝  ЛИЧНЫЙ КАНАЛ ОТЧЁТОВ"
    embed.description = (
        "В этот канал **вы скидываете свои отчёты**.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.add_field(
        name="📋  Форма",
        value=(
            "```\n"
            "Режим:\n"
            "Ник нарушителя:\n"
            "Доказательства:\n"
            "```"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚠️  Важно",
        value=(
            "• На **муты** — доказательства **обязательны**\n"
            "• На **баны** — только по запросу администрации\n"
            "• За **отсутствие отчётов** следует **наказание**\n"
            "• Необходимо **поддерживать** и **выполнять** указания вышестоящих"
        ),
        inline=False,
    )
    embed.add_field(
        name="👤  Модератор",
        value=moderator.mention,
        inline=True,
    )
    embed.add_field(
        name="📨  Создал",
        value=creator.mention,
        inline=True,
    )
    embed.set_footer(text="⚡ DW Moderation  •  Отчёты")
    return embed


def member_owns_report_channel(channel: discord.TextChannel, member: discord.abc.User) -> bool:
    ow = channel.overwrites.get(member)
    return ow is not None and ow.send_messages is True


async def create_report_channel(
    guild: discord.Guild,
    moderator: discord.abc.User,
    creator: discord.abc.User,
    *,
    nick: str | None = None,
    refresh: bool = False,
) -> tuple[discord.TextChannel | None, str]:
    cat = discord.utils.get(guild.categories, name=REPORT_CATEGORY)
    if cat is None:
        return None, "Категория «[ 📋 ] Отчёты» не найдена."

    slug_source = nick or report_nick_for_channel(moderator)
    slug = slugify(slug_source)
    ch_name = report_channel_name(slug)
    overwrites = build_report_overwrites(guild, moderator)

    by_member = find_channel_for_member(guild, moderator)

    if refresh:
        target = by_member
        if target is None:
            existing = find_report_channel(guild, slug)
            if existing and member_owns_report_channel(existing, moderator):
                target = existing
        if target is None:
            return None, f"Канал для модератора не найден (`📝・{slug}`)."
        try:
            await target.edit(overwrites=overwrites, reason=f"Refresh report perms for {moderator}")
        except discord.HTTPException:
            return None, "Не удалось обновить права канала."
        return target, f"Права обновлены: {target.mention}"

    if by_member is not None:
        return (
            None,
            f"У модератора уже есть канал {by_member.mention}. "
            "Используй **Обновить права**, если нужно перепривязать.",
        )

    existing = find_report_channel(guild, slug)
    if existing:
        if member_owns_report_channel(existing, moderator):
            return (
                None,
                f"Канал {existing.mention} уже привязан к этому модератору.",
            )
        return (
            None,
            f"Канал `📝・{slug}` уже занят другим модератором ({existing.mention}).",
        )

    try:
        channel = await guild.create_text_channel(
            ch_name,
            category=cat,
            overwrites=overwrites,
            reason=f"Report channel for {moderator} by {creator}",
        )
    except discord.HTTPException:
        return None, "Не удалось создать канал."

    await channel.send(
        embed=build_report_welcome_embed(moderator, creator),
        allowed_mentions=discord.AllowedMentions(users=True),
    )
    return channel, f"Канал создан: {channel.mention}"


async def delete_report_channel(
    channel: discord.TextChannel,
    actor: discord.abc.User,
) -> tuple[bool, str]:
    if not is_personal_report_channel(channel):
        return False, "Можно удалять только личные каналы `📝・ник`."

    cat = channel.category
    if cat is None or cat.name != REPORT_CATEGORY:
        return False, "Канал не в категории отчётов."

    name = channel.name
    try:
        await channel.delete(reason=f"Report channel removed by {actor}")
    except discord.HTTPException:
        return False, "Не удалось удалить канал."
    return True, f"Канал **{name}** удалён."


class ReportNickModal(discord.ui.Modal):
    def __init__(self, action: ReportAction) -> None:
        titles = {
            "create": "📝  Создать отчёт",
            "delete": "🗑️  Удалить отчёт",
            "refresh": "🔁  Обновить права",
        }
        super().__init__(title=titles[action])
        self.action = action
        self.nick_input = discord.ui.TextInput(
            label="Ник модератора (без @)",
            placeholder="chocka1 или @упоминание",
            required=True,
            max_length=32,
        )
        self.add_item(self.nick_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            return

        await interaction.response.defer(ephemeral=True)
        query = parse_nick_input(str(self.nick_input.value))
        members = await find_moderators_by_nick(guild, query)

        if not members:
            await interaction.followup.send(
                f"⚠️ Модератор `{query}` не найден на сервере.",
                ephemeral=True,
            )
            return

        if len(members) > 1:
            listed = ", ".join(f"`{channel_nick_from_member(m)}`" for m in members[:5])
            await interaction.followup.send(
                f"⚠️ Найдено несколько: {listed}. Введи точнее.",
                ephemeral=True,
            )
            return

        member = members[0]
        nick = channel_nick_from_member(member)
        label = f"**{nick}** (`{member.display_name}`)"

        if self.action in ("create", "refresh") and not is_report_moderator(member):
            await interaction.followup.send(
                f"⚠️ {label} — нет роли **Модерация** / **Модерация+** / **Высшая Модерация**.",
                ephemeral=True,
            )
            return

        if self.action == "create":
            channel, text = await create_report_channel(
                guild, member, interaction.user, refresh=False,
            )
            if channel:
                await interaction.followup.send(
                    f"✅ {label} → {channel.mention} (`📝・{slugify(nick)}`)",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(f"⚠️ {text}", ephemeral=True)
            return

        if self.action == "refresh":
            channel, text = await create_report_channel(
                guild, member, interaction.user, refresh=True,
            )
            if channel:
                await interaction.followup.send(
                    f"✅ Права обновлены: {channel.mention}",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(f"⚠️ {text}", ephemeral=True)
            return

        target = find_channel_for_member(guild, member)
        if target is None:
            await interaction.followup.send(
                f"⚠️ Канал для {label} (`📝・{slugify(nick)}`) не найден.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🗑️  Удалить канал отчёта?",
            description=(
                f"Модератор: {label}\n"
                f"Канал: {target.mention}\n\n"
                "**Это действие нельзя отменить.**"
            ),
            color=COLOR_DANGER,
        )
        await interaction.followup.send(embed=embed, view=DeleteConfirmView(target), ephemeral=True)


class DeleteConfirmView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel) -> None:
        super().__init__(timeout=60)
        self.channel = channel

    @discord.ui.button(label="Да, удалить", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        ok, message = await delete_report_channel(self.channel, interaction.user)
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        color = COLOR_SUCCESS if ok else COLOR_DANGER
        await interaction.followup.send(embed=discord.Embed(description=message, color=color), ephemeral=True)

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="Удаление отменено.",
            embed=None,
            view=self,
        )


class ReportPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def _deny_unless_admin(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member) or not is_report_admin(interaction.user):
            await interaction.response.send_message(
                "Управлять отчётами может только **администрация**.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(
        label="Создать отчёт",
        style=discord.ButtonStyle.primary,
        emoji="📋",
        custom_id="report_create_btn",
    )
    async def create_report(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._deny_unless_admin(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        await interaction.response.send_modal(ReportNickModal("create"))

    @discord.ui.button(
        label="Удалить отчёт",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="report_delete_btn",
    )
    async def delete_report(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._deny_unless_admin(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        await interaction.response.send_modal(ReportNickModal("delete"))

    @discord.ui.button(
        label="Обновить права",
        style=discord.ButtonStyle.secondary,
        emoji="🔁",
        custom_id="report_refresh_btn",
        row=1,
    )
    async def refresh_report(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._deny_unless_admin(interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        await interaction.response.send_modal(ReportNickModal("refresh"))


async def remove_legacy_panel(guild: discord.Guild) -> None:
    legacy = discord.utils.get(guild.text_channels, name=REPORT_LEGACY_PANEL)
    if legacy is None:
        return
    await legacy.delete(reason="Дубль панели — используется 〈📋〉-создание")
    print(f"  ✓ удалён лишний #{REPORT_LEGACY_PANEL}")


def channel_has_moderator(guild: discord.Guild, channel: discord.TextChannel) -> bool:
    bot_id = guild.me.id if guild.me else 0
    for target, ow in channel.overwrites.items():
        if isinstance(target, discord.Role):
            continue
        if getattr(target, "id", None) == bot_id:
            continue
        if ow.send_messages is True:
            return True
    return False


async def deploy_report_panel(guild: discord.Guild) -> None:
    await remove_legacy_panel(guild)

    panel = discord.utils.get(guild.text_channels, name=REPORT_PANEL)
    if panel is None:
        for legacy in REPORT_PANEL_LEGACY + (REPORT_PANEL_OLD,):
            panel = discord.utils.get(guild.text_channels, name=legacy)
            if panel:
                await panel.edit(name=REPORT_PANEL, reason="DW: DuckWorld panel style")
                print(f"  ✓ переименован #{legacy} → #{REPORT_PANEL}")
                break

    if panel is None:
        cat = discord.utils.get(guild.categories, name=REPORT_CATEGORY)
        if cat is None:
            print(f"  ⚠ категория {REPORT_CATEGORY} не найдена")
            return
        panel = await guild.create_text_channel(
            REPORT_PANEL,
            category=cat,
            reason="DW Moderation: панель отчётов",
        )
        print(f"  ✓ создан #{REPORT_PANEL}")

    me = guild.me
    if me is None:
        return

    async for msg in panel.history(limit=15):
        if msg.author.id == me.id:
            await msg.delete()

    await panel.send(embed=build_panel_embed(), view=ReportPanelView())
    print(f"  ✓ панель отчётов в #{REPORT_PANEL}")


def register_report_commands(tree: app_commands.CommandTree) -> None:
    @tree.command(name="отчёт", description="Создать или обновить канал отчёта для модератора")
    @app_commands.describe(
        модератор="Упомяни модератора",
        ник="Переопределить ник канала (по умолчанию — часть после | на сервере)",
        обновить="Только обновить права, если канал уже есть",
    )
    async def report_cmd(
        interaction: discord.Interaction,
        модератор: discord.Member,
        ник: str | None = None,
        обновить: bool = False,
    ) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_report_admin(interaction.user):
            await interaction.response.send_message(
                "Команда только для **администрации**.",
                ephemeral=True,
            )
            return

        if not is_report_moderator(модератор):
            await interaction.response.send_message(
                "⚠️ Нужна роль **Модерация**, **Модерация+** или **Высшая Модерация**.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return

        channel, message = await create_report_channel(
            guild,
            модератор,
            interaction.user,
            nick=ник,
            refresh=обновить,
        )
        color = COLOR_SUCCESS if channel else 0xE74C3C
        embed = discord.Embed(description=message, color=color)
        if channel:
            embed.add_field(name="Канал", value=channel.mention, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @tree.command(name="отчёт-удалить", description="Удалить личный канал отчёта модератора")
    @app_commands.describe(
        канал="Канал отчёта для удаления",
        модератор="Или укажи модератора — бот найдёт его канал",
    )
    async def report_delete_cmd(
        interaction: discord.Interaction,
        канал: discord.TextChannel | None = None,
        модератор: discord.Member | None = None,
    ) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_report_admin(interaction.user):
            await interaction.response.send_message("Только для администрации.", ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            return

        target = канал
        if target is None and модератор is not None:
            target = find_channel_for_member(guild, модератор)

        if target is None:
            await interaction.response.send_message(
                "Укажи **канал** или **модератора**.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="🗑️  Удалить канал отчёта?",
                description=f"Канал: {target.mention}\n**Это действие нельзя отменить.**",
                color=COLOR_DANGER,
            ),
            view=DeleteConfirmView(target),
            ephemeral=True,
        )

    @tree.command(name="отчёт-список", description="Показать каналы отчётов без привязанного модератора")
    async def report_list_cmd(interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_report_admin(interaction.user):
            await interaction.response.send_message("Только для администрации.", ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            return

        cat = discord.utils.get(guild.categories, name=REPORT_CATEGORY)
        if cat is None:
            await interaction.response.send_message("Категория отчётов не найдена.", ephemeral=True)
            return

        missing: list[str] = []
        for ch in cat.text_channels:
            if ch.name in (REPORT_PANEL, REPORT_PANEL_OLD, REPORT_LEGACY_PANEL, REPORT_ALL_MODS, *REPORT_PANEL_LEGACY, *REPORT_ALL_LEGACY):
                continue
            if not REPORT_CHANNEL_RE.match(ch.name):
                continue
            if channel_has_moderator(guild, ch):
                continue
            missing.append(f"• {ch.mention}")

        if not missing:
            text = "У всех личных каналов есть привязанный модератор."
        else:
            text = "**Без модератора:**\n" + "\n".join(missing[:25])
        await interaction.response.send_message(text, ephemeral=True)


def register_report_views(bot: DWBot) -> None:
    bot.add_view(ReportPanelView())
