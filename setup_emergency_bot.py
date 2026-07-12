#!/usr/bin/env python3
"""Структура экстренной связи под Настроебань (REST, без gateway)."""

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
CAT_ARCHIVE = "[ 📦 ] Архив"
PANEL = "〈-📞-〉панель"

STAFF = [
    "• Модерация",
    "• Модерация+",
    "• Высшая Модерация",
    "• Отдел SS",
    "• Администрация",
    "• Высшая Администрация",
    "• Руководство",
    "⭐",
]

ARCHIVE_ROLES = [
    "• Высшая Модерация",
    "• Отдел SS",
    "• Администрация",
    "• Высшая Администрация",
    "• Руководство",
    "⭐",
]

P_VIEW, P_SEND, P_HIST = 1 << 10, 1 << 11, 1 << 16
P_MANAGE_CH, P_ATTACH = 1 << 4, 1 << 15


def ow(role_id: str, allow: int) -> dict[str, Any]:
    return {"id": role_id, "type": 0, "allow": str(allow), "deny": "0"}


class Api:
    def __init__(self) -> None:
        self.h = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
        self.base = "https://discord.com/api/v10"

    async def get(self, s: aiohttp.ClientSession, path: str) -> Any:
        async with s.get(f"{self.base}{path}", headers=self.h) as r:
            r.raise_for_status()
            return await r.json()

    async def post(self, s: aiohttp.ClientSession, path: str, data: dict) -> Any:
        async with s.post(f"{self.base}{path}", headers=self.h, json=data) as r:
            if r.status >= 400:
                raise RuntimeError(f"POST {path}: {(await r.text())[:300]}")
            return await r.json()

    async def patch(self, s: aiohttp.ClientSession, path: str, data: dict) -> Any:
        async with s.patch(f"{self.base}{path}", headers=self.h, json=data) as r:
            if r.status >= 400:
                raise RuntimeError(f"PATCH {path}: {(await r.text())[:300]}")
            return await r.json()

    async def delete(self, s: aiohttp.ClientSession, path: str) -> None:
        async with s.delete(f"{self.base}{path}", headers=self.h) as r:
            if r.status not in (200, 204):
                raise RuntimeError(f"DELETE {path}: {(await r.text())[:300]}")


async def main() -> None:
    api = Api()
    async with aiohttp.ClientSession() as s:
        roles = {r["name"]: r for r in await api.get(s, f"/guilds/{GUILD_ID}/roles")}
        channels = await api.get(s, f"/guilds/{GUILD_ID}/channels")

        em = next((c for c in channels if c["type"] == 4 and c["name"] == CAT_EMERGENCY), None)
        if em is None:
            em = await api.post(s, f"/guilds/{GUILD_ID}/channels", {"name": CAT_EMERGENCY, "type": 4})
            print(f"  + {CAT_EMERGENCY}")

        arch = next((c for c in channels if c["type"] == 4 and c["name"] == CAT_ARCHIVE), None)
        if arch is None:
            arch = await api.post(s, f"/guilds/{GUILD_ID}/channels", {"name": CAT_ARCHIVE, "type": 4})
            print(f"  + {CAT_ARCHIVE}")

        panel = next((c for c in channels if c["type"] == 0 and c["name"] == PANEL), None)
        if panel is None:
            panel = await api.post(
                s, f"/guilds/{GUILD_ID}/channels", {"name": PANEL, "type": 0, "parent_id": em["id"]}
            )
            print(f"  + {PANEL}")
        elif panel.get("parent_id") != em["id"]:
            panel = await api.patch(s, f"/channels/{panel['id']}", {"parent_id": em["id"]})

        staff_allow = P_VIEW | P_SEND | P_HIST | P_ATTACH | P_MANAGE_CH
        em_ows = [ow(GUILD_ID, P_VIEW | P_HIST)]
        for name in STAFF:
            r = roles.get(name)
            if r:
                em_ows.append(ow(r["id"], staff_allow))
        await api.patch(s, f"/channels/{em['id']}", {"permission_overwrites": em_ows})

        panel_ows = [ow(GUILD_ID, P_VIEW | P_HIST)]
        for name in STAFF:
            r = roles.get(name)
            if r:
                panel_ows.append(ow(r["id"], staff_allow))
        await api.patch(s, f"/channels/{panel['id']}", {"permission_overwrites": panel_ows})

        arch_ows = [ow(GUILD_ID, 0)]
        for name in ARCHIVE_ROLES:
            r = roles.get(name)
            if r:
                arch_ows.append(ow(r["id"], P_VIEW | P_HIST))
        await api.patch(s, f"/channels/{arch['id']}", {"permission_overwrites": arch_ows})

        print("✅ Структура готова. Запусти: python3 ticket_bot.py")


if __name__ == "__main__":
    asyncio.run(main())
