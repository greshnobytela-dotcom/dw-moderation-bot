#!/usr/bin/env python3
"""Тикеты на зарплату — панель в категории отчётов."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from ticket_bot import DWBot

ROOT = Path(__file__).parent
DATA = ROOT / "data"
SALARY_COUNTER_FILE = DATA / "salary_counter.json"

SALARY_CATEGORY = "заработок"
SALARY_CATEGORY_STYLED = "[ 💸 ] Заработок"
SALARY_CATEGORY_LEGACY = "[ 💰 ] Заработок"
SALARY_PANEL_OLD = "получение-зарплаты"
SALARY_PANEL = "〈💵〉・зарплата"
SALARY_LEDGER = "〈📊〉・выплаты"
# Только имена панели бота — не трогать старые 🪙-каналы (там таблица выплат вручную).
SALARY_PANEL_LEGACY_NAMES = (
    "〈💰〉・зарплата",
    "💰・зарплата",
    "〈💰〉-зарплата",
    "〈🏦〉・зарплата",
    "получение-зарплаты",
)
SALARY_LEDGER_LEGACY_NAMES = (
    "〈-🪙-〉├・зарплата",
    "〈-🪙-〉╭・зарплата",
    "〈-🪙-〉└・зарплата",
    "╠『🪙』зарплата",
)
CAT_ARCHIVE_SALARY = "[ 📦 ] Архив ・ Зарплата"
CAT_ARCHIVE_LEGACY = "[ 📦 ] Архив"

R_HIGH_ADMIN = "• Высшая Администрация"
R_ADMIN = "• Администрация"
R_JUNIOR_ADMIN = "• Младшая Администрация"
R_LEAD = "• Руководство"
R_STAR = "⭐"
R_HIGH_MOD = "• Высшая Модерация"
R_SS = "• Отдел SS"
R_MOD_PLUS = "• Модерация+"
R_MOD = "• Модерация"

STAFF_ROLES = {
    R_MOD,
    R_MOD_PLUS,
    R_HIGH_MOD,
    R_SS,
    R_JUNIOR_ADMIN,
    R_ADMIN,
    R_HIGH_ADMIN,
    R_LEAD,
    R_STAR,
}
SALARY_ADMIN_ROLES = {R_ADMIN, R_HIGH_ADMIN, R_LEAD, R_STAR}

ARCHIVE_VIEW_ROLES = [
    R_HIGH_MOD,
    R_SS,
    R_ADMIN,
    R_HIGH_ADMIN,
    R_LEAD,
    R_STAR,
]

OPEN_SALARY_RE = re.compile(r"^[💵💰]・(\d+)・(.+)$")
ARCHIVE_SALARY_RE = re.compile(r"^🗄️・зп-(\d+)(?:・(.+))?$")
USER_MENTION_RE = re.compile(r"<@!?(\d+)>")
TOPIC_RE = re.compile(
    r"creator:(?P<creator>\d+)(?:\|nick:(?P<nick>[^|]+))?(?:\|mode:(?P<mode>[^|]+))?",
    re.IGNORECASE,
)

SALARY_MODES = ["Гриф", "Анархия", "ФФА"]
MODE_EMOJI = {
    "Гриф": "⚔️",
    "Анархия": "💀",
    "ФФА": "🎯",
}

COLOR_PANEL = 0xF1C40F
COLOR_FORM = 0xF39C12
COLOR_TICKET = 0xE67E22
COLOR_ARCHIVE = 0x95A5A6
COLOR_SUCCESS = 0x2ECC71
COLOR_DANGER = 0xE74C3C

PANEL_EMBED_TITLE = "ПОЛУЧЕНИЕ ЗАРПЛАТЫ"

_salary_locks: dict[int, asyncio.Lock] = {}


def _salary_lock(guild_id: int) -> asyncio.Lock:
    if guild_id not in _salary_locks:
        _salary_locks[guild_id] = asyncio.Lock()
    return _salary_locks[guild_id]


def is_staff(member: discord.Member) -> bool:
    return any(r.name in STAFF_ROLES for r in member.roles)


def is_salary_admin(member: discord.Member) -> bool:
    return any(r.name in SALARY_ADMIN_ROLES for r in member.roles)


def scan_max_salary_num(guild: discord.Guild) -> int:
    max_num = -1
    for ch in guild.channels:
        if not isinstance(ch, discord.TextChannel):
            continue
        m = OPEN_SALARY_RE.match(ch.name) or ARCHIVE_SALARY_RE.match(ch.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num


def save_salary_counter(next_id: int) -> None:
    DATA.mkdir(exist_ok=True)
    SALARY_COUNTER_FILE.write_text(json.dumps({"next_id": next_id}))


def payment_nick_from_member(member: discord.Member) -> str:
    """Ник для выплаты — часть после | в серверном нике."""
    display = member.display_name
    if "|" in display:
        tail = display.split("|", 1)[1].strip()
        if tail:
            return tail
    return member.name


def nick_slug(nick: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in nick.lower())[:20]


def salary_topic(creator_id: int, nick: str, mode: str) -> str:
    return f"creator:{creator_id}|nick:{nick}|mode:{mode}"


def parse_salary_topic(topic: str | None) -> tuple[int | None, str | None, str | None]:
    if not topic:
        return None, None, None
    m = TOPIC_RE.match(topic.strip())
    if not m:
        legacy = re.match(r"creator:(\d+)", topic.strip())
        if legacy:
            return int(legacy.group(1)), None, None
        return None, None, None
    creator_id = int(m.group("creator"))
    nick = m.group("nick")
    mode = m.group("mode")
    return creator_id, nick, mode


def field_plain(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            return parts[1].strip()
    return text.strip("`").strip()


async def reserve_salary_id(guild: discord.Guild) -> int:
    async with _salary_lock(guild.id):
        num = scan_max_salary_num(guild) + 1
        save_salary_counter(num + 1)
        return num


def open_channel_name(num: int, nick: str) -> str:
    return f"💰・{num}・{nick_slug(nick)}"


def archive_channel_name(num: int, nick: str) -> str:
    return f"🗄️・зп-{num}・{nick_slug(nick)}"


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
    me = guild.me
    if me:
        ows[me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
        )
    return ows


def ledger_overwrites(guild: discord.Guild) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    """Таблица выплат: пишет руководство, смотрят модерация и выше."""
    ows: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    for role in guild.roles:
        if role.name == R_LEAD:
            ows[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )
        elif role.name in STAFF_ROLES:
            ows[role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
            )
    me = guild.me
    if me:
        ows[me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
        )
    return ows


async def apply_ledger_permissions(guild: discord.Guild, ledger: discord.TextChannel) -> None:
    await ledger.edit(
        overwrites=ledger_overwrites(guild),
        sync_permissions=False,
        reason="Таблица выплат: только руководство",
    )


def find_salary_category(guild: discord.Guild) -> discord.CategoryChannel | None:
    for cat in guild.categories:
        if "заработ" in cat.name.lower():
            return cat
    return discord.utils.get(guild.categories, name=SALARY_CATEGORY)


def salary_panel_channels(guild: discord.Guild) -> list[discord.TextChannel]:
    return [ch for ch in guild.text_channels if ch.name == SALARY_PANEL]


async def channel_has_salary_panel(
    channel: discord.TextChannel,
    bot_id: int,
) -> bool:
    async for msg in channel.history(limit=15):
        if msg.author.id != bot_id:
            continue
        for embed in msg.embeds:
            if embed.title and PANEL_EMBED_TITLE in embed.title.upper():
                return True
    return False


async def find_salary_panel_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Панель «Подать заявку» — всегда канал зарплата, даже если имя сбилось."""
    panel = discord.utils.get(guild.text_channels, name=SALARY_PANEL)
    if panel is not None:
        return panel

    for legacy in SALARY_PANEL_LEGACY_NAMES:
        panel = discord.utils.get(guild.text_channels, name=legacy)
        if panel is not None:
            return panel

    me = guild.me
    bot_id = me.id if me else 0
    salary_cat = find_salary_category(guild)
    search = salary_cat.text_channels if salary_cat else guild.text_channels

    for ch in search:
        if ch.name == SALARY_LEDGER or "выплат" in ch.name.lower():
            continue
        if await channel_has_salary_panel(ch, bot_id):
            return ch

    for ch in guild.text_channels:
        if ch.name == SALARY_LEDGER or "выплат" in ch.name.lower():
            continue
        if "зарплат" in ch.name.lower():
            return ch

    return None


async def dedupe_salary_panel_channels(guild: discord.Guild) -> discord.TextChannel | None:
    """Оставить одну панель; дубли — удалить (оставляем канал с сообщениями людей)."""
    panels = salary_panel_channels(guild)
    if not panels:
        return None
    if len(panels) == 1:
        return panels[0]

    me = guild.me

    async def human_messages(ch: discord.TextChannel) -> int:
        count = 0
        async for msg in ch.history(limit=50):
            if me and msg.author.id == me.id:
                continue
            count += 1
        return count

    scored: list[tuple[int, int, discord.TextChannel]] = []
    for ch in panels:
        humans = await human_messages(ch)
        scored.append((humans, -ch.created_at.timestamp(), ch))
    scored.sort(reverse=True)
    keep = scored[0][2]
    removed = 0
    for _, _, ch in scored[1:]:
        await ch.delete(reason="DW: дубликат панели зарплаты")
        removed += 1
    if removed:
        print(f"  ✓ зарплата: удалено дублей панели — {removed}, оставлен #{keep.name}")
    return keep


async def ensure_salary_ledger_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Канал для ручной таблицы «кто сколько получил» — отдельно от панели заявок."""
    salary_cat = await ensure_salary_category(guild)
    me = guild.me
    bot_id = me.id if me else 0

    panel = await find_salary_panel_channel(guild)
    ledger = discord.utils.get(guild.text_channels, name=SALARY_LEDGER)
    if ledger is not None and (
        ledger.id == (panel.id if panel else -1)
        or await channel_has_salary_panel(ledger, bot_id)
    ):
        ledger = None

    if ledger is None:
        for legacy in SALARY_LEDGER_LEGACY_NAMES:
            candidate = discord.utils.get(guild.text_channels, name=legacy)
            if candidate is None:
                continue
            if panel is not None and candidate.id == panel.id:
                continue
            if await channel_has_salary_panel(candidate, bot_id):
                continue
            ledger = candidate
            await ledger.edit(
                name=SALARY_LEDGER,
                category=salary_cat,
                reason="DW: таблица выплат (отдельно от панели заявок)",
            )
            print(f"  ✓ переименован #{legacy} → #{SALARY_LEDGER}")
            break
    if ledger is None:
        ledger = await guild.create_text_channel(
            SALARY_LEDGER,
            category=salary_cat,
            overwrites=ledger_overwrites(guild),
            reason="DW Moderation: таблица выплат",
        )
        print(f"  ✓ создан #{SALARY_LEDGER}")
    elif ledger.category_id != salary_cat.id:
        await ledger.edit(category=salary_cat, reason="Таблица выплат → заработок")
    await apply_ledger_permissions(guild, ledger)
    return ledger


async def ensure_salary_category(guild: discord.Guild) -> discord.CategoryChannel:
    cat = find_salary_category(guild)
    if cat is not None:
        if cat.name != SALARY_CATEGORY_STYLED:
            await cat.edit(name=SALARY_CATEGORY_STYLED, reason="Категория → 💸 Заработок")
            print(f"  ✓ категория: {cat.name} → {SALARY_CATEGORY_STYLED}")
        return cat
    legacy = discord.utils.get(guild.categories, name=SALARY_CATEGORY_LEGACY)
    if legacy is not None:
        await legacy.edit(name=SALARY_CATEGORY_STYLED, reason="Категория → 💸 Заработок")
        print(f"  ✓ категория: {SALARY_CATEGORY_LEGACY} → {SALARY_CATEGORY_STYLED}")
        return legacy
    return await guild.create_category(
        SALARY_CATEGORY_STYLED,
        reason="Категория заявок на зарплату",
    )


async def ensure_salary_archive_category(guild: discord.Guild) -> discord.CategoryChannel:
    cat = discord.utils.get(guild.categories, name=CAT_ARCHIVE_SALARY)
    ows = archive_overwrites(guild)
    if cat is None:
        return await guild.create_category(
            CAT_ARCHIVE_SALARY,
            overwrites=ows,
            reason="Архив заявок на зарплату",
        )
    await cat.edit(overwrites=ows, reason="Архив зарплаты: права")
    return cat


async def fix_legacy_archive_channels(guild: discord.Guild) -> int:
    """Старые 🗄️・зп-N → 🗄️・зп-N・ник."""
    fixed = 0
    legacy_re = re.compile(r"^🗄️・зп-(\d+)$")
    for ch in guild.text_channels:
        if not legacy_re.match(ch.name):
            continue
        meta = await read_salary_meta(ch)
        if meta is None:
            continue
        num, nick, mode, _, creator_id = meta
        if nick in ("?", ""):
            continue
        new_name = archive_channel_name(num, nick)
        new_topic = salary_topic(creator_id or 0, nick, mode)
        edits: dict = {}
        if ch.name != new_name:
            edits["name"] = new_name
        if ch.topic != new_topic:
            edits["topic"] = new_topic
        if edits:
            await ch.edit(**edits, reason="Архив ЗП: добавить ник в название")
            fixed += 1
    return fixed


async def migrate_salary_layout(guild: discord.Guild) -> None:
    """Открытые заявки → заработок, архив зп → отдельная категория."""
    salary_cat = await ensure_salary_category(guild)
    salary_arch = await ensure_salary_archive_category(guild)
    moved = 0

    for ch in guild.text_channels:
        m = OPEN_SALARY_RE.match(ch.name)
        if m:
            new_name = open_channel_name(int(m.group(1)), m.group(2))
            edits: dict = {}
            if ch.name != new_name:
                edits["name"] = new_name
            if ch.category_id != salary_cat.id:
                edits["category"] = salary_cat
            if edits:
                await ch.edit(**edits, reason="Заявки ЗП → заработок")
                moved += 1
        elif ARCHIVE_SALARY_RE.match(ch.name):
            if ch.category_id != salary_arch.id:
                await ch.edit(
                    category=salary_arch,
                    overwrites=archive_overwrites(guild),
                    reason="Архив ЗП → отдельная категория",
                )
                moved += 1

    legacy = discord.utils.get(guild.categories, name=CAT_ARCHIVE_LEGACY)
    if legacy:
        for ch in list(legacy.text_channels):
            if ARCHIVE_SALARY_RE.match(ch.name):
                await ch.edit(
                    category=salary_arch,
                    overwrites=archive_overwrites(guild),
                    reason="Перенос архива ЗП из общего архива",
                )
                moved += 1

    panel = discord.utils.get(guild.text_channels, name=SALARY_PANEL)
    if panel is None:
        panel = discord.utils.get(guild.text_channels, name=SALARY_PANEL_OLD)
    if panel and panel.category_id != salary_cat.id:
        await panel.edit(category=salary_cat, reason="Панель зарплаты → заработок")

    if moved:
        print(f"  ✓ зарплата: перенесено каналов — {moved}")

    renamed = await fix_legacy_archive_channels(guild)
    if renamed:
        print(f"  ✓ зарплата: архив с ником — {renamed}")


def ticket_overwrites(
    guild: discord.Guild,
    creator: discord.Member,
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    ows: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        creator: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
    }
    for role in guild.roles:
        if role.name in SALARY_ADMIN_ROLES:
            ows[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                attach_files=True,
            )
    me = guild.me
    if me:
        ows[me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
            manage_channels=True,
        )
    return ows


def build_panel_embed() -> discord.Embed:
    embed = discord.Embed(color=COLOR_PANEL)
    embed.title = "💵  ПОЛУЧЕНИЕ ЗАРПЛАТЫ"
    embed.description = (
        "# Нажми **«Подать заявку»**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.add_field(
        name="📋  Появится форма",
        value=(
            "**Выбери режим**\n"
            "⚔️ Гриф  ·  💀 Анархия  ·  🎯 ФФА\n\n"
            "**Введи ник**\n"
            "Игровой ник, на который выдать зарплату\n\n"
            "**Комментарий** — *по желанию*\n"
            "Реквизиты, уточнения, сумма"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔒  Доступ",
        value=(
            "Подать заявку — **сотрудники** (модерация и выше)\n"
            "Обработка — **администрация**"
        ),
        inline=False,
    )
    embed.set_footer(text="⚡ DW Moderation  •  Зарплата")
    return embed


def build_form_embed() -> discord.Embed:
    modes = "\n".join(f"{MODE_EMOJI[m]}  **{m}**" for m in SALARY_MODES)
    embed = discord.Embed(
        title="📝  ФОРМА ЗАЯВКИ",
        description="Заполни поля ниже и нажми **Продолжить**",
        color=COLOR_FORM,
    )
    embed.add_field(name="1️⃣  Режим", value=modes, inline=False)
    embed.add_field(name="2️⃣  Ник", value="Введёшь после **Продолжить**", inline=False)
    embed.add_field(
        name="3️⃣  Комментарий",
        value="*(необязательно)*",
        inline=False,
    )
    return embed


def build_ticket_embed(
    num: int,
    nick: str,
    mode: str,
    creator: discord.abc.User,
    comment: str | None = None,
) -> discord.Embed:
    requester = payment_nick_from_member(creator) if isinstance(creator, discord.Member) else creator.name
    embed = discord.Embed(color=COLOR_TICKET)
    embed.title = "💰  ЗАЯВКА НА ЗАРПЛАТУ"
    embed.description = (
        f"Номер: `#{num}`  ·  **{requester}**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.add_field(name="👤  НИК ДЛЯ ВЫПЛАТЫ", value=f"```\n{nick}\n```", inline=True)
    embed.add_field(
        name=f"{MODE_EMOJI.get(mode, '🎮')}  РЕЖИМ",
        value=f"```\n{mode}\n```",
        inline=True,
    )
    embed.add_field(name="📨  ЗАПРОСИЛ", value=creator.mention, inline=True)
    if comment:
        embed.add_field(name="💬  КОММЕНТАРИЙ", value=f"```\n{comment[:900]}\n```", inline=False)
    return embed


async def read_salary_meta(
    channel: discord.TextChannel,
) -> tuple[int, str, str, str | None, int | None] | None:
    m = OPEN_SALARY_RE.match(channel.name)
    if not m:
        m2 = ARCHIVE_SALARY_RE.match(channel.name)
        if not m2:
            return None
        num = int(m2.group(1))
        nick = m2.group(2).replace("-", " ") if m2.group(2) else "?"
    else:
        num = int(m.group(1))
        nick = m.group(2).replace("-", " ")

    mode = "?"
    comment = None
    creator_id, topic_nick, topic_mode = parse_salary_topic(channel.topic)
    if topic_nick:
        nick = topic_nick
    if topic_mode:
        mode = topic_mode

    async for msg in channel.history(limit=25, oldest_first=True):
        if not msg.embeds:
            continue
        emb = msg.embeds[0]
        title = (emb.title or "").lower()
        if "заявк" not in title:
            continue
        for field in emb.fields:
            name = field.name.upper()
            val = field_plain(field.value)
            if "ВЫПЛАТ" in name or name.endswith("НИК"):
                nick = val
            elif "РЕЖИМ" in name:
                mode = val
            elif "КОММЕНТАРИЙ" in name:
                comment = val
            elif "ЗАПРОСИЛ" in name or "СОЗДАЛ" in name:
                hit = USER_MENTION_RE.search(field.value)
                if hit:
                    creator_id = int(hit.group(1))
        break

    return num, nick, mode, comment, creator_id


async def archive_salary_ticket(
    channel: discord.TextChannel,
    actor: discord.abc.User,
    *,
    status: str,
    processor: discord.abc.User | None = None,
) -> bool:
    guild = channel.guild
    meta = await read_salary_meta(channel)
    if meta is None:
        return False
    num, nick, mode, comment, creator_id = meta

    archive_cat = await ensure_salary_archive_category(guild)

    embed = discord.Embed(color=COLOR_ARCHIVE)
    embed.title = f"📦  АРХИВ ЗП  #{num}"
    lines = [f"Статус: **{status}**", f"Обработал: {actor.mention}"]
    if processor and processor.id != actor.id:
        lines.append(f"Выплатил: {processor.mention}")
    embed.description = "\n".join(lines) + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    embed.add_field(name="👤  НИК ДЛЯ ВЫПЛАТЫ", value=f"```\n{nick}\n```", inline=True)
    embed.add_field(
        name=f"{MODE_EMOJI.get(mode, '🎮')}  РЕЖИМ",
        value=f"```\n{mode}\n```",
        inline=True,
    )
    if creator_id:
        embed.add_field(name="📨  ЗАПРОСИЛ", value=f"<@{creator_id}>", inline=True)
    if comment:
        embed.add_field(name="💬  КОММЕНТАРИЙ", value=f"```\n{comment[:900]}\n```", inline=False)

    try:
        await channel.send(embed=embed)
        await channel.edit(
            name=archive_channel_name(num, nick),
            topic=salary_topic(creator_id if creator_id is not None else actor.id, nick, mode),
            category=archive_cat,
            overwrites=archive_overwrites(guild),
            reason=f"Archive salary ticket {num}",
        )
        await disable_salary_controls(channel)
        return True
    except discord.HTTPException:
        return False


async def disable_salary_controls(channel: discord.TextChannel) -> None:
    guild = channel.guild
    me = guild.me
    if me is None:
        return
    view = SalaryControlView()
    for item in view.children:
        item.disabled = True
    async for msg in channel.history(limit=25):
        if msg.author.id == me.id and msg.components:
            try:
                await msg.edit(view=view)
            except discord.HTTPException:
                pass
            return


class ModeSelect(discord.ui.Select):
    def __init__(self, form: SalaryFormView) -> None:
        self.form = form
        options = [
            discord.SelectOption(label=m, value=m, emoji=MODE_EMOJI.get(m))
            for m in SALARY_MODES
        ]
        super().__init__(
            placeholder="🎮  Выбери режим",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.form.mode = self.values[0]
        await interaction.response.defer()


class SalaryFormView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.mode: str | None = None
        self.add_item(ModeSelect(self))

    @discord.ui.button(label="Продолжить", style=discord.ButtonStyle.success, emoji="✏️", row=1)
    async def continue_btn(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not self.mode:
            await interaction.response.send_message("⚠️ Сначала выбери **режим**.", ephemeral=True)
            return
        await interaction.response.send_modal(SalaryNickModal(self.mode))


class SalaryNickModal(discord.ui.Modal, title="💰  Заявка на зарплату"):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.nick = discord.ui.TextInput(
            label="Ник для выплаты",
            placeholder="Введите никнейм",
            required=True,
            max_length=64,
            style=discord.TextStyle.short,
        )
        self.comment = discord.ui.TextInput(
            label="Комментарий (необязательно)",
            placeholder="Реквизиты, сумма, уточнения…",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.nick)
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            return

        nick = str(self.nick.value).strip()
        comment = str(self.comment.value).strip() or None
        channel = await create_salary_ticket(
            guild,
            interaction.user,
            nick,
            self.mode,
            comment,
        )
        if channel is None:
            await interaction.followup.send(
                "⚠️ Не удалось создать заявку.",
                ephemeral=True,
            )
            return
        done = discord.Embed(
            description=f"✅ Заявка создана: {channel.mention}",
            color=COLOR_SUCCESS,
        )
        await interaction.followup.send(embed=done, ephemeral=True)


async def create_salary_ticket(
    guild: discord.Guild,
    creator: discord.Member,
    nick: str,
    mode: str,
    comment: str | None = None,
) -> discord.TextChannel | None:
    cat = await ensure_salary_category(guild)
    num = await reserve_salary_id(guild)
    ch_name = open_channel_name(num, nick)

    try:
        channel = await guild.create_text_channel(
            ch_name,
            category=cat,
            overwrites=ticket_overwrites(guild, creator),
            topic=salary_topic(creator.id, nick, mode),
            reason=f"Salary ticket #{num}",
        )
    except discord.HTTPException:
        return None

    embed = build_ticket_embed(num, nick, mode, creator, comment)
    await channel.send(
        embed=embed,
        view=SalaryControlView(),
        allowed_mentions=discord.AllowedMentions(users=True),
    )
    return channel


class SalaryControlView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Принял заявку",
        style=discord.ButtonStyle.primary,
        emoji="✋",
        custom_id="salary_claim_btn",
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_salary_admin(interaction.user):
            await interaction.response.send_message("Только **администрация**.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✋  Принял заявку",
                description=interaction.user.mention,
                color=COLOR_FORM,
            )
        )

    @discord.ui.button(
        label="Выплачено — закрыть",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="salary_close_btn",
        row=0,
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_salary_admin(interaction.user):
            await interaction.response.send_message("Только **администрация**.", ephemeral=True)
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return
        await interaction.response.defer()
        if ARCHIVE_SALARY_RE.match(channel.name):
            await interaction.followup.send("Заявка уже закрыта.", ephemeral=True)
            return
        ok = await archive_salary_ticket(channel, interaction.user, status="Выплачено")
        if ok:
            await interaction.followup.send("✅ Заявка закрыта и перенесена в архив.")
        else:
            await interaction.followup.send("⚠️ Не удалось закрыть заявку.", ephemeral=True)

    @discord.ui.button(
        label="Отклонить",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="salary_reject_btn",
        row=1,
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_salary_admin(interaction.user):
            await interaction.response.send_message("Только **администрация**.", ephemeral=True)
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return
        await interaction.response.defer()
        if ARCHIVE_SALARY_RE.match(channel.name):
            await interaction.followup.send("Заявка уже закрыта.", ephemeral=True)
            return
        ok = await archive_salary_ticket(channel, interaction.user, status="Отклонено")
        if ok:
            await interaction.followup.send("Заявка отклонена и перенесена в архив.")
        else:
            await interaction.followup.send("⚠️ Не удалось закрыть заявку.", ephemeral=True)

    @discord.ui.button(
        label="Отменить",
        style=discord.ButtonStyle.secondary,
        emoji="🗑️",
        custom_id="salary_cancel_btn",
        row=1,
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return

        meta = await read_salary_meta(channel)
        if meta is None:
            await interaction.response.send_message("Не удалось прочитать заявку.", ephemeral=True)
            return

        _, _, _, _, creator_id = meta
        is_creator = creator_id == interaction.user.id
        is_admin = isinstance(interaction.user, discord.Member) and is_salary_admin(interaction.user)
        if not is_creator and not is_admin:
            await interaction.response.send_message(
                "Отменить может **создатель** или **администрация**.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        if ARCHIVE_SALARY_RE.match(channel.name):
            await interaction.followup.send("Заявка уже закрыта.", ephemeral=True)
            return
        ok = await archive_salary_ticket(channel, interaction.user, status="Отменено")
        if ok:
            await interaction.followup.send("Заявка отменена и перенесена в архив.")
        else:
            await interaction.followup.send("⚠️ Не удалось закрыть заявку.", ephemeral=True)


class SalaryPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Подать заявку",
        style=discord.ButtonStyle.primary,
        emoji="💵",
        custom_id="salary_create_btn",
    )
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message(
                "Подать заявку могут только **сотрудники** (модерация и выше).",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=build_form_embed(),
            view=SalaryFormView(),
            ephemeral=True,
        )


async def ensure_salary_panel_channel(guild: discord.Guild) -> discord.TextChannel | None:
    salary_cat = await ensure_salary_category(guild)
    panel = await find_salary_panel_channel(guild)
    if panel is not None:
        edits: dict = {}
        if panel.name != SALARY_PANEL:
            edits["name"] = SALARY_PANEL
        if panel.category_id != salary_cat.id:
            edits["category"] = salary_cat
        if edits:
            old = panel.name
            await panel.edit(**edits, reason="Панель заявок → зарплата")
            print(f"  ✓ переименован #{old} → #{SALARY_PANEL}")
        panel = await dedupe_salary_panel_channels(guild) or panel
        return panel

    for legacy in SALARY_PANEL_LEGACY_NAMES:
        panel = discord.utils.get(guild.text_channels, name=legacy)
        if panel:
            await panel.edit(
                name=SALARY_PANEL,
                category=salary_cat,
                reason="DW: DuckWorld panel style",
            )
            print(f"  ✓ переименован #{legacy} → #{SALARY_PANEL}")
            return panel

    panel = await guild.create_text_channel(
        SALARY_PANEL,
        category=salary_cat,
        reason="DW Moderation: панель зарплаты",
    )
    print(f"  ✓ создан #{SALARY_PANEL}")
    return panel


async def deploy_salary_panel(guild: discord.Guild) -> None:
    await migrate_salary_layout(guild)
    panel = await ensure_salary_panel_channel(guild)
    await ensure_salary_ledger_channel(guild)
    if panel is None:
        print(f"  ⚠ канал зарплаты не найден ({SALARY_PANEL_OLD})")
        return

    me = guild.me
    if me is None:
        return

    async for msg in panel.history(limit=15):
        if msg.author.id == me.id:
            await msg.delete()

    await panel.send(embed=build_panel_embed(), view=SalaryPanelView())
    print(f"  ✓ панель зарплаты в #{panel.name}")


def register_salary_views(bot: DWBot) -> None:
    bot.add_view(SalaryPanelView())
    bot.add_view(SalaryControlView())


def register_salary_commands(tree: app_commands.CommandTree) -> None:
    @tree.command(name="зарплата", description="Создать заявку на зарплату")
    @app_commands.describe(
        ник="Игровой ник для выплаты",
        режим="Режим сервера",
        комментарий="Необязательно",
    )
    @app_commands.choices(
        режим=[
            app_commands.Choice(name="Гриф", value="Гриф"),
            app_commands.Choice(name="Анархия", value="Анархия"),
            app_commands.Choice(name="ФФА", value="ФФА"),
        ]
    )
    async def salary_cmd(
        interaction: discord.Interaction,
        ник: str,
        режим: app_commands.Choice[str],
        комментарий: str | None = None,
    ) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("Только для сотрудников.", ephemeral=True)
            return
        if interaction.guild is None:
            return
        await interaction.response.defer(ephemeral=True)
        channel = await create_salary_ticket(
            interaction.guild,
            interaction.user,
            ник.strip(),
            режим.value,
            комментарий.strip() if комментарий else None,
        )
        if channel is None:
            await interaction.followup.send("⚠️ Не удалось создать заявку.", ephemeral=True)
            return
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"✅ Заявка создана: {channel.mention}",
                color=COLOR_SUCCESS,
            ),
            ephemeral=True,
        )
