#!/usr/bin/env python3
"""Удалить каналы/сообщения Настроебань, пересоздать структуру под Ticket Tool (без сообщений)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import aiohttp
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

GUILD_ID = os.getenv("DISCORD_GUILD_ID", "1500480346540474490")
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

CAT_EMERGENCY = "экстренная-связь"
CAT_ARCHIVE_OURS = "[ 📦 ] Архив"
PANEL = "〈-📞-〉панель"
OUR_BOT_ID = "1525811629537624154"
TICKET_TOOL_APP_ID = "557628352828014614"
STAFF_ROLE_ID = "1525820362254713063"

DELETE_CATEGORIES = {CAT_EMERGENCY, CAT_ARCHIVE_OURS, "[ 🚨 ] Экстренная связь"}

STAFF_ROLE_NAMES = [
    "• Модерация",
    "• Модерация+",
    "• Высшая Модерация",
    "• Отдел SS",
    "• Младшая Администрация",
    "• Администрация",
    "• Высшая Администрация",
    "• Руководство",
    "⭐",
]

PERM_VIEW = 1 << 10
PERM_SEND = 1 << 11
PERM_EMBED = 1 << 14
PERM_ATTACH = 1 << 15
PERM_HISTORY = 1 << 16
PERM_MANAGE_CH = 1 << 4
PERM_MANAGE_MSG = 1 << 13
PERM_MANAGE_ROLES = 1 << 28


def allow(*bits: int) -> int:
    return sum(bits)


def ow_role(role_id: str, *, allow_bits: int) -> dict[str, Any]:
    return {"id": role_id, "type": 0, "allow": str(allow_bits), "deny": "0"}


class Api:
    def __init__(self, token: str) -> None:
        self.base = "https://discord.com/api/v10"
        self.headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}

    async def get(self, s: aiohttp.ClientSession, path: str) -> Any:
        async with s.get(f"{self.base}{path}", headers=self.headers) as r:
            r.raise_for_status()
            return await r.json()

    async def post(self, s: aiohttp.ClientSession, path: str, data: dict) -> Any:
        async with s.post(f"{self.base}{path}", headers=self.headers, json=data) as r:
            if r.status >= 400:
                raise RuntimeError(f"POST {path} {r.status}: {(await r.text())[:300]}")
            return await r.json()

    async def patch(self, s: aiohttp.ClientSession, path: str, data: dict) -> Any:
        async with s.patch(f"{self.base}{path}", headers=self.headers, json=data) as r:
            if r.status >= 400:
                raise RuntimeError(f"PATCH {path} {r.status}: {(await r.text())[:300]}")
            return await r.json()

    async def delete(self, s: aiohttp.ClientSession, path: str) -> None:
        async with s.delete(f"{self.base}{path}", headers=self.headers) as r:
            if r.status not in (200, 204):
                raise RuntimeError(f"DELETE {path} {r.status}: {(await r.text())[:300]}")


async def purge_our_messages(api: Api, s: aiohttp.ClientSession, channels: list[dict]) -> int:
    n = 0
    for ch in channels:
        if ch["type"] != 0:
            continue
        msgs = await api.get(s, f"/channels/{ch['id']}/messages?limit=100")
        if not isinstance(msgs, list):
            continue
        for msg in msgs:
            if msg.get("author", {}).get("id") == OUR_BOT_ID:
                await api.delete(s, f"/channels/{ch['id']}/messages/{msg['id']}")
                print(f"  удалено сообщение в #{ch['name']}")
                n += 1
                await asyncio.sleep(0.35)
    return n


async def delete_our_channels(api: Api, s: aiohttp.ClientSession, channels: list[dict]) -> None:
    # Сначала дочерние каналы в наших категориях и тикеты 🚨・ / 🗄️・ от нашего бота
    for ch in list(channels):
        name = ch["name"]
        parent = ch.get("parent_id")
        parent_name = next((c["name"] for c in channels if c["id"] == parent), "") if parent else ""

        delete = False
        if ch["type"] == 4 and name in DELETE_CATEGORIES:
            delete = True
        elif name.startswith("🚨・"):
            delete = True
        elif name.startswith("🗄️・") and parent_name == CAT_ARCHIVE_OURS:
            delete = True
        elif parent_name in DELETE_CATEGORIES:
            delete = True

        if delete and ch["type"] != 4:
            await api.delete(s, f"/channels/{ch['id']}")
            print(f"  удалён канал {name}")
            await asyncio.sleep(0.4)

    channels = await api.get(s, f"/guilds/{GUILD_ID}/channels")
    for ch in channels:
        if ch["type"] == 4 and ch["name"] in DELETE_CATEGORIES:
            await api.delete(s, f"/channels/{ch['id']}")
            print(f"  удалена категория {ch['name']}")
            await asyncio.sleep(0.4)


async def create_ticket_tool_structure(api: Api, s: aiohttp.ClientSession) -> tuple[dict, dict]:
    roles = await api.get(s, f"/guilds/{GUILD_ID}/roles")
    role_by_name = {r["name"]: r for r in roles}
    tt_role = role_by_name.get("Ticket Tool")

    cat = await api.post(s, f"/guilds/{GUILD_ID}/channels", {"name": CAT_EMERGENCY, "type": 4})
    print(f"  + категория {CAT_EMERGENCY}")

    panel = await api.post(
        s,
        f"/guilds/{GUILD_ID}/channels",
        {"name": PANEL, "type": 0, "parent_id": cat["id"]},
    )
    print(f"  + канал {PANEL}")

    staff_allow = allow(
        PERM_VIEW, PERM_SEND, PERM_HISTORY, PERM_ATTACH, PERM_EMBED, PERM_MANAGE_CH
    )
    everyone_view = allow(PERM_VIEW, PERM_HISTORY)
    tt_allow = allow(
        PERM_VIEW,
        PERM_SEND,
        PERM_HISTORY,
        PERM_EMBED,
        PERM_ATTACH,
        PERM_MANAGE_CH,
        PERM_MANAGE_MSG,
        PERM_MANAGE_ROLES,
    )

    cat_ows = [ow_role(GUILD_ID, allow_bits=everyone_view)]
    for rn in STAFF_ROLE_NAMES:
        r = role_by_name.get(rn)
        if r:
            cat_ows.append(ow_role(r["id"], allow_bits=staff_allow))
    if tt_role:
        cat_ows.append(ow_role(tt_role["id"], allow_bits=tt_allow))
    await api.patch(s, f"/channels/{cat['id']}", {"permission_overwrites": cat_ows})

    panel_ows = [ow_role(GUILD_ID, allow_bits=everyone_view)]
    for rn in STAFF_ROLE_NAMES:
        r = role_by_name.get(rn)
        if r:
            panel_ows.append(
                ow_role(
                    r["id"],
                    allow_bits=allow(PERM_VIEW, PERM_SEND, PERM_HISTORY, PERM_MANAGE_MSG),
                )
            )
    if tt_role:
        panel_ows.append(ow_role(tt_role["id"], allow_bits=tt_allow))
    await api.patch(s, f"/channels/{panel['id']}", {"permission_overwrites": panel_ows})
    print("  ✓ права для Ticket Tool")

    async with s.put(
        f"{api.base}/guilds/{GUILD_ID}/members/{TICKET_TOOL_APP_ID}/roles/{STAFF_ROLE_ID}",
        headers=api.headers,
    ) as r:
        if r.status == 204:
            print("  ✓ Ticket Tool → Сотрудники")
        elif r.status == 403:
            tt = await api.get(s, f"/guilds/{GUILD_ID}/members/{TICKET_TOOL_APP_ID}")
            if STAFF_ROLE_ID in tt.get("roles", []):
                print("  ✓ Ticket Tool уже имеет Сотрудники")

    return cat, panel


async def main() -> None:
    if not TOKEN:
        raise SystemExit("Нет DISCORD_BOT_TOKEN")

    api = Api(TOKEN)
    async with aiohttp.ClientSession() as s:
        guild = await api.get(s, f"/guilds/{GUILD_ID}")
        print(f"Сервер: {guild['name']}")

        channels = await api.get(s, f"/guilds/{GUILD_ID}/channels")

        print("\n=== Удаление сообщений Настроебань ===")
        n = await purge_our_messages(api, s, channels)
        print(f"  всего: {n}")

        print("\n=== Удаление наших каналов тикетов ===")
        await delete_our_channels(api, s, channels)

        print("\n=== Создание под Ticket Tool (без сообщений) ===")
        cat, panel = await create_ticket_tool_structure(api, s)

        print(
            f"\n✅ Готово.\n"
            f"   Категория: {CAT_EMERGENCY} ({cat['id']})\n"
            f"   Панель: {PANEL} ({panel['id']})\n"
            f"   Настроебань ничего не пишет.\n"
            f"   Админ в #{PANEL}: /setup-panel → панель → этот канал"
        )


if __name__ == "__main__":
    asyncio.run(main())
