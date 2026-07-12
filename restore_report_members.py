#!/usr/bin/env python3
"""Восстанавливает доступ модераторов к личным каналам отчётов (REST)."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

ROOT = Path(__file__).parent
MAP_FILE = ROOT / "data" / "report_owners.json"

REPORT_CATEGORY = "[ 📋 ] Отчёты"
REPORT_CHANNEL_RE = re.compile(r"^📝・(.+)$")

R_ADMIN = "• Администрация"
R_HIGH_ADMIN = "• Высшая Администрация"
R_HIGH_MOD = "• Высшая Модерация"
R_SS = "• Отдел SS"
R_REPORTS = "•  Доступ к отчётам"
REPORT_VIEWER_ROLE_NAMES = {R_ADMIN, R_HIGH_ADMIN, R_HIGH_MOD, R_SS, R_REPORTS}

VIEW_ALLOW = 1024 | 65536
POST_ALLOW = VIEW_ALLOW | 2048 | 32768 | 16384 | 64


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


async def fetch_roles(session: aiohttp.ClientSession, guild_id: str) -> dict[str, str]:
    async with session.get(f"https://discord.com/api/v10/guilds/{guild_id}/roles") as resp:
        roles = await resp.json()
    return {r["name"]: r["id"] for r in roles}


def build_overwrites(
    guild_id: str,
    moderator_id: str,
    roles: dict[str, str],
) -> list[dict[str, Any]]:
    ows: list[dict[str, Any]] = [
        {"id": guild_id, "type": 0, "allow": "0", "deny": "1024"},
        {"id": moderator_id, "type": 1, "allow": str(POST_ALLOW), "deny": "0"},
    ]
    for name, rid in roles.items():
        if name in REPORT_VIEWER_ROLE_NAMES:
            ows.append({"id": rid, "type": 0, "allow": str(VIEW_ALLOW), "deny": "0"})
    return ows


async def owner_from_messages(
    session: aiohttp.ClientSession,
    channel_id: str,
) -> tuple[str, str] | None:
    async with session.get(
        f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50"
    ) as resp:
        if resp.status >= 400:
            return None
        msgs = await resp.json()
    if not isinstance(msgs, list) or not msgs:
        return None
    counts = Counter(
        m["author"]["id"]
        for m in msgs
        if not m.get("author", {}).get("bot")
    )
    if not counts:
        return None
    uid = counts.most_common(1)[0][0]
    username = next(m["author"]["username"] for m in msgs if m["author"]["id"] == uid)
    return uid, username


async def owner_from_search(
    session: aiohttp.ClientSession,
    guild_id: str,
    slug: str,
) -> tuple[str, str] | None:
    query = slug.replace("_", " ").replace("-", " ")
    url = (
        f"https://discord.com/api/v10/guilds/{guild_id}/members/search"
        f"?query={quote(query)}&limit=10"
    )
    async with session.get(url) as resp:
        if resp.status >= 400:
            return None
        members = await resp.json()
    target = normalize(slug)
    for m in members:
        user = m["user"]
        if normalize(user["username"]) == target:
            return user["id"], user["username"]
    if members:
        user = members[0]["user"]
        return user["id"], user["username"]
    return None


async def restore_reports() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.getenv("DISCORD_GUILD_ID", "0")
    headers = {"Authorization": f"Bot {token}"}
    owners: dict[str, dict[str, str]] = {}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f"https://discord.com/api/v10/guilds/{guild_id}/channels") as resp:
            channels = await resp.json()

        roles = await fetch_roles(session, guild_id)
        cat_id = next(
            (c["id"] for c in channels if c.get("type") == 4 and c.get("name") == REPORT_CATEGORY),
            None,
        )
        if cat_id is None:
            print("Категория отчётов не найдена")
            return

        restored = 0
        missing: list[str] = []

        for ch in channels:
            if ch.get("parent_id") != cat_id:
                continue
            name = ch.get("name", "")
            m = REPORT_CHANNEL_RE.match(name)
            if not m:
                continue

            slug = m.group(1)
            found = await owner_from_messages(session, ch["id"])
            if found is None:
                found = await owner_from_search(session, guild_id, slug)
            if found is None:
                missing.append(name)
                print(f"  ⚠ {name}: владелец не найден")
                continue

            mod_id, username = found
            owners[slug] = {"user_id": mod_id, "username": username}
            ows = build_overwrites(guild_id, mod_id, roles)
            async with session.patch(
                f"https://discord.com/api/v10/channels/{ch['id']}",
                json={"permission_overwrites": ows},
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    print(f"  ✗ {name}: {resp.status} {text}")
                    continue
            print(f"  ✓ {name} → {username}")
            restored += 1
            await asyncio.sleep(0.5)

        MAP_FILE.parent.mkdir(exist_ok=True)
        MAP_FILE.write_text(json.dumps(owners, ensure_ascii=False, indent=2))

        print(f"\nГотово: восстановлено {restored}, не найдено {len(missing)}")
        if missing:
            print("Не найдены:", ", ".join(missing))


if __name__ == "__main__":
    asyncio.run(restore_reports())
