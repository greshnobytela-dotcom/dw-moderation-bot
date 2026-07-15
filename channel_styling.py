#!/usr/bin/env python3
"""Оформление: текст — DuckWorld 〈emoji〉-slug, войс — HIMORY emoji • name."""

from __future__ import annotations

import asyncio
import re

import discord

_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

# Категории: старое → DuckWorld [ emoji ] Название
CATEGORY_RENAMES: dict[str, str] = {
    "заработок": "[ 💸 ] Заработок",
    "[ 💰 ] Заработок": "[ 💸 ] Заработок",
    "экстренная-связь": "[ 📞 ] Экстренная связь",
    "[ 🔊 ] Голосовые": "[ 🔊 ] Войсы",
    "📚 | оᴄноʙноᴇ": "[ 📚 ] Основное",
    "📩 | чᴀᴛы": "[ 💬 ] Чаты",
    "🎤 | ʙойᴄы": "[ 🔊 ] Войсы",
    "📞 | 1x1": "[ 📞 ] 1x1",
    "отчёты": "[ 📋 ] Отчёты",
}

DELETE_CHANNELS: set[str] = set()

# Панель заявок и таблица выплат — только бот, стилизация не трогает.
BOT_MANAGED_TEXT = {
    "〈💵〉・зарплата",
    "〈💰〉・зарплата",
    "〈📊〉・выплаты",
    "💰・зарплата",
    "💵・зарплата",
    "〈💰〉-зарплата",
    "получение-зарплаты",
}

LEGACY_LEDGER_RE = re.compile(
    r"^(?:〈-🪙-〉(?:╭・|├・|└・)зарплата|╠『🪙』зарплата)$"
)

# Парсинг любых старых имён → slug
TEXT_PARSE = re.compile(
    r"^(?:"
    r"〈(?P<t1>[^〉-]+)〉[-・](?P<s1>.+)"
    r"|〈-(?P<t2>[^-]+)-〉(?:╭・|├・|└・)(?P<s2>.+)"
    r"|〈-(?P<t4>[^-]+)-〉(?P<s4>.+)"
    r"|(?P<t3>[^\s〈〉・]+)・(?P<s3>.+)"
    r")$"
)
VOICE_PARSE = re.compile(
    r"^(?:"
    r"(?P<v1>[^\s•]+) • (?P<r1>.+)"
    r"|〈\s*(?P<v2>[^\s〉]+)\s*〉(?:╭・|├・|└・)?(?P<s4>.+)"
    r"|(?P<v3>[^\s〈〉・]+)・(?P<s5>.+)"
    r")$"
)
DYNAMIC_SKIP = re.compile(
    r"^(?:"
    r"🚨・\d+"
    r"|🗄️・"
    r"|📝・"
    r"|💵・\d+・"
    r"|💰・\d+・"
    r")"
)

# slug → (emoji, category | None, voice_number | None)
TEXT_TARGETS: dict[str, tuple[str, str | None]] = {
    "кто-есть-кто": ("💎", "[ 📚 ] Основное"),
    "новости": ("🗞️", "[ 📚 ] Основное"),
    "информация": ("🆕", "[ 📚 ] Основное"),
    "уход-и-приход": ("🕛", "[ 📚 ] Основное"),
    "общий": ("🛡️", "[ 💬 ] Чаты"),
    "отпуск": ("🪪", "[ 💬 ] Чаты"),
    "администрация": ("🧧", "[ 💬 ] Чаты"),
    "музло": ("🎵", "[ 💬 ] Чаты"),
    "выплаты": ("📊", "[ 💸 ] Заработок"),
    "создание": ("📋", "[ 📋 ] Отчёты"),
    "панель": ("📞", "[ 📞 ] Экстренная связь"),
    "все-проверки": ("📂", "[ 📋 ] Отчёты"),
}

VOICE_TARGETS: dict[str, tuple[str, str, int | None]] = {
    "общий": ("💼", "[ 🔊 ] Войсы", None),
    "войс-1": ("🔊", "[ 🔊 ] Войсы", 1),
    "войс-2": ("🔉", "[ 🔊 ] Войсы", 2),
    "войс-3": ("🔉", "[ 🔊 ] Войсы", 3),
    "войс 1": ("🔊", "[ 🔊 ] Войсы", 1),
    "войс 2": ("🔉", "[ 🔊 ] Войсы", 2),
    "войс 3": ("🔉", "[ 🔊 ] Войсы", 3),
    "афк": ("🔇", "[ 🔊 ] Войсы", None),
    "алкоголики": ("🍷", "[ 🔒 ] Закрытые", None),
    "госдума": ("🔰", "[ 🔒 ] Закрытые", None),
    "приватка": ("💢", "[ 🔒 ] Закрытые", None),
    "оперативный-штаб": ("🧢", "[ 🔒 ] Закрытые", None),
    "оперативный штаб": ("🧢", "[ 🔒 ] Закрытые", None),
    "беседка-1": ("🔈", "[ 📞 ] 1x1", 1),
    "беседка-2": ("🔈", "[ 📞 ] 1x1", 2),
    "беседка 1": ("🔈", "[ 📞 ] 1x1", 1),
    "беседка 2": ("🔈", "[ 📞 ] 1x1", 2),
}

VOICE_CATEGORY_ORDER: dict[str, list[str]] = {
    "[ 🔊 ] Войсы": ["общий", "войс-1", "войс-2", "войс-3", "афк"],
    "[ 🔊 ] Голосовые": ["общий", "войс-1", "войс-2", "войс-3", "афк"],
    "[ 📞 ] 1x1": ["беседка-1", "беседка-2"],
}

VOICE_LABELS: dict[str, str] = {
    "войс-1": "Войс",
    "войс-2": "Войс",
    "войс-3": "Войс",
    "войс 1": "Войс",
    "войс 2": "Войс",
    "войс 3": "Войс",
    "беседка-1": "Беседка",
    "беседка-2": "Беседка",
    "беседка 1": "Беседка",
    "беседка 2": "Беседка",
}


def text_channel_name(emoji: str, slug: str) -> str:
    return f"〈{emoji}〉・{slug}"


def voice_title(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("-", " ").split())


def voice_channel_name(emoji: str, slug: str, number: int | None = None) -> str:
    key = slug.lower().replace(" ", "-")
    if number is not None:
        label = VOICE_LABELS.get(key, voice_title(slug))
        suffix = str(number).translate(_SUPERSCRIPT)
        return f"{emoji} • {label}{suffix}"
    return f"{emoji} • {voice_title(slug)}"


def normalize_slug(raw: str) -> str:
    s = raw.strip().lower().replace(" ", "-")
    # убрать суффикс ¹²³ из Himory-имён
    s = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+$", "", s)
    s = re.sub(r"[^\wа-яё-]", "", s, flags=re.IGNORECASE)
    return s


def parse_text_slug(name: str) -> str | None:
    m = TEXT_PARSE.match(name)
    if not m:
        return None
    slug = m.group("s1") or m.group("s2") or m.group("s3") or m.group("s4")
    return normalize_slug(slug)


def _superscript_to_digit(s: str) -> int | None:
    normal = s.translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))
    if normal.isdigit():
        return int(normal)
    return None


def parse_voice_slug(name: str) -> str | None:
    m = VOICE_PARSE.match(name)
    if not m:
        return None
    if m.group("r1"):
        rest = m.group("r1").strip()
        num_m = re.search(r"([⁰¹²³⁴⁵⁶⁷⁸⁹]+)$", rest)
        number = _superscript_to_digit(num_m.group(1)) if num_m else None
        label = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+$", "", rest).strip().lower()
        if label == "войс" and number is not None:
            return f"войс-{number}"
        if label == "беседка" and number is not None:
            return f"беседка-{number}"
        return normalize_slug(rest)
    slug = m.group("s4") or m.group("s5")
    return normalize_slug(slug)


def target_text_name(slug: str) -> str | None:
    key = normalize_slug(slug)
    if key in TEXT_TARGETS:
        emoji, _ = TEXT_TARGETS[key]
        return text_channel_name(emoji, key)
    return None


def target_text_category(slug: str) -> str | None:
    key = normalize_slug(slug)
    if key in TEXT_TARGETS:
        return TEXT_TARGETS[key][1]
    return None


def target_voice_name(slug: str) -> str | None:
    key = normalize_slug(slug)
    for variant in (key, key.replace("-", " ")):
        if variant in VOICE_TARGETS:
            emoji, _, num = VOICE_TARGETS[variant]
            return voice_channel_name(emoji, variant, num)
    return None


def target_voice_category(slug: str) -> str | None:
    key = normalize_slug(slug)
    for variant in (key, key.replace("-", " ")):
        if variant in VOICE_TARGETS:
            return VOICE_TARGETS[variant][1]
    return None


def should_skip_channel(name: str) -> bool:
    if name in BOT_MANAGED_TEXT:
        return True
    lower = name.lower()
    if "зарплат" in lower and "выплат" not in lower:
        return True
    slug = parse_text_slug(name)
    if slug == "зарплата" and not LEGACY_LEDGER_RE.match(name):
        return True
    return bool(DYNAMIC_SKIP.match(name))


async def apply_category_renames(guild: discord.Guild) -> int:
    changed = 0
    for old, new in CATEGORY_RENAMES.items():
        cat = discord.utils.get(guild.categories, name=old)
        if cat and cat.name != new:
            await cat.edit(name=new, reason="DW: DuckWorld categories")
            print(f"  категория: {old} → {new}")
            changed += 1
            await asyncio.sleep(0.4)
    return changed


async def remove_stale_channels(guild: discord.Guild) -> int:
    removed = 0
    for name in DELETE_CHANNELS:
        ch = discord.utils.get(guild.channels, name=name)
        if ch is None:
            continue
        await ch.delete(reason="DW: устаревший канал")
        print(f"  удалён: {name}")
        removed += 1
        await asyncio.sleep(0.4)
    return removed


async def style_text_channels(guild: discord.Guild) -> int:
    cats = {c.name: c for c in guild.categories}
    changed = 0
    print("=== Текст → 〈emoji〉・slug ===")

    for ch in guild.text_channels:
        if should_skip_channel(ch.name):
            print(f"  ⊘ бот: {ch.name}")
            continue

        slug = parse_text_slug(ch.name)
        if slug is None:
            print(f"  ⚠ пропуск: {ch.name}")
            continue

        new_name = target_text_name(slug)
        if new_name is None:
            print(f"  ⚠ нет в реестре: {ch.name}")
            continue

        cat_name = target_text_category(slug)
        target_cat = cats.get(cat_name) if cat_name else None

        edits: dict = {}
        if ch.name != new_name:
            edits["name"] = new_name
        if target_cat and ch.category_id != target_cat.id:
            edits["category"] = target_cat

        if edits:
            old = ch.name
            await ch.edit(**edits, reason="Text: DuckWorld style")
            print(f"  {old} → {edits.get('name', ch.name)}")
            changed += 1
        else:
            print(f"  ✓ {ch.name}")
        await asyncio.sleep(0.4)

    return changed


async def style_voice_channels(guild: discord.Guild) -> int:
    cats = {c.name: c for c in guild.categories}
    changed = 0
    styled_ids: set[int] = set()
    print("=== Войс → emoji • name ===")

    for cat_name, slug_order in VOICE_CATEGORY_ORDER.items():
        category = cats.get(cat_name)
        if category is None:
            continue
        channels = sorted(category.voice_channels, key=lambda c: c.position)
        for ch, slug in zip(channels, slug_order):
            styled_ids.add(ch.id)
            new_name = target_voice_name(slug)
            if new_name is None:
                print(f"  ⚠ нет цели: {ch.name} ({slug})")
                continue
            if ch.name != new_name:
                old = ch.name
                await ch.edit(name=new_name, reason="Voice: HIMORY style")
                print(f"  {old} → {new_name}")
                changed += 1
            else:
                print(f"  ✓ {ch.name}")
            await asyncio.sleep(0.4)

    for ch in guild.voice_channels:
        if ch.id in styled_ids:
            continue
        slug = parse_voice_slug(ch.name)
        if slug is None:
            print(f"  ⚠ пропуск: {ch.name}")
            continue

        new_name = target_voice_name(slug)
        if new_name is None:
            print(f"  ⚠ нет в реестре: {ch.name}")
            continue

        cat_name = target_voice_category(slug)
        target_cat = cats.get(cat_name) if cat_name else None

        edits: dict = {}
        if ch.name != new_name:
            edits["name"] = new_name
        if target_cat and ch.category_id != target_cat.id:
            edits["category"] = target_cat

        if edits:
            old = ch.name
            await ch.edit(**edits, reason="Voice: HIMORY style")
            print(f"  {old} → {edits.get('name', ch.name)}")
            changed += 1
        else:
            print(f"  ✓ {ch.name}")
        await asyncio.sleep(0.4)

    return changed


async def apply_server_styling(guild: discord.Guild) -> None:
    print("=== Оформление сервера ===")
    n = await apply_category_renames(guild)
    await guild.fetch_channels()
    n += await remove_stale_channels(guild)
    n += await style_text_channels(guild)
    n += await style_voice_channels(guild)
    print(f"  ✓ оформление: изменений {n}")
