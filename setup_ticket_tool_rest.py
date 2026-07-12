#!/usr/bin/env python3
"""Ticket Tool setup через Discord REST API (без gateway — не конфликтует с другими скриптами)."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import aiohttp
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

GUILD_ID = os.getenv("DISCORD_GUILD_ID", "1500480346540474490")
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

CAT_EMERGENCY = "экстренная-связь"
PANEL = "〈-📞-〉панель"
TICKET_TOOL_APP_ID = "557628352828014614"
OUR_BOT_ID = "1525811629537624154"
STAFF_ROLE_ID = "1525820362254713063"

STAFF_ROLE_NAMES = [
    "• Модерация",
    "• Модерация+",
    "• Высшая Модерация",
    "• Отдел SS",
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


def deny_view() -> dict[str, int]:
    return {"id": GUILD_ID, "type": 0, "deny": str(PERM_VIEW), "allow": "0"}


def ow_role(role_id: str, *, allow_bits: int, deny_bits: int = 0) -> dict[str, Any]:
    return {
        "id": role_id,
        "type": 0,
        "allow": str(allow_bits),
        "deny": str(deny_bits),
    }


class DiscordRest:
    def __init__(self, token: str) -> None:
        self.base = "https://discord.com/api/v10"
        self.headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}

    async def get(self, session: aiohttp.ClientSession, path: str) -> Any:
        async with session.get(f"{self.base}{path}", headers=self.headers) as r:
            r.raise_for_status()
            return await r.json()

    async def post(self, session: aiohttp.ClientSession, path: str, data: dict) -> Any:
        async with session.post(f"{self.base}{path}", headers=self.headers, json=data) as r:
            if r.status >= 400:
                text = await r.text()
                raise RuntimeError(f"POST {path} -> {r.status}: {text[:400]}")
            return await r.json()

    async def patch(self, session: aiohttp.ClientSession, path: str, data: dict) -> Any:
        async with session.patch(f"{self.base}{path}", headers=self.headers, json=data) as r:
            if r.status >= 400:
                text = await r.text()
                raise RuntimeError(f"PATCH {path} -> {r.status}: {text[:400]}")
            return await r.json()

    async def delete(self, session: aiohttp.ClientSession, path: str) -> None:
        async with session.delete(f"{self.base}{path}", headers=self.headers) as r:
            if r.status not in (200, 204):
                text = await r.text()
                raise RuntimeError(f"DELETE {path} -> {r.status}: {text[:400]}")


async def main() -> None:
    if not TOKEN:
        raise SystemExit("Нет DISCORD_BOT_TOKEN")

    api = DiscordRest(TOKEN)
    async with aiohttp.ClientSession() as session:
        guild = await api.get(session, f"/guilds/{GUILD_ID}")
        print(f"Сервер: {guild['name']}")

        roles = await api.get(session, f"/guilds/{GUILD_ID}/roles")
        role_by_name = {r["name"]: r for r in roles}
        tt_role = role_by_name.get("Ticket Tool")
        staff_role = next((r for r in roles if r["id"] == STAFF_ROLE_ID), None)

        channels = await api.get(session, f"/guilds/{GUILD_ID}/channels")
        cat = next((c for c in channels if c["type"] == 4 and c["name"] == CAT_EMERGENCY), None)
        if cat is None:
            cat = await api.post(
                session,
                f"/guilds/{GUILD_ID}/channels",
                {"name": CAT_EMERGENCY, "type": 4},
            )
            print(f"  + категория {CAT_EMERGENCY}")

        panel = next((c for c in channels if c["type"] == 0 and c["name"] == PANEL), None)
        if panel is None:
            panel = await api.post(
                session,
                f"/guilds/{GUILD_ID}/channels",
                {"name": PANEL, "type": 0, "parent_id": cat["id"]},
            )
            print(f"  + канал {PANEL}")
        elif panel.get("parent_id") != cat["id"]:
            panel = await api.patch(
                session,
                f"/channels/{panel['id']}",
                {"parent_id": cat["id"]},
            )
            print("  → панель перенесена")

        staff_allow = allow(
            PERM_VIEW, PERM_SEND, PERM_HISTORY, PERM_ATTACH, PERM_EMBED, PERM_MANAGE_CH
        )
        everyone_panel = allow(PERM_VIEW, PERM_HISTORY)
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

        cat_ows = [
            ow_role(GUILD_ID, allow_bits=everyone_panel),
        ]
        for name in STAFF_ROLE_NAMES:
            r = role_by_name.get(name)
            if r:
                cat_ows.append(ow_role(r["id"], allow_bits=staff_allow))
        if tt_role:
            cat_ows.append(ow_role(tt_role["id"], allow_bits=tt_allow))

        await api.patch(session, f"/channels/{cat['id']}", {"permission_overwrites": cat_ows})
        print("  ✓ права категории")

        panel_ows = [ow_role(GUILD_ID, allow_bits=everyone_panel)]
        for name in STAFF_ROLE_NAMES:
            r = role_by_name.get(name)
            if r:
                panel_ows.append(
                    ow_role(
                        r["id"],
                        allow_bits=allow(
                            PERM_VIEW, PERM_SEND, PERM_HISTORY, PERM_MANAGE_MSG
                        ),
                    )
                )
        if tt_role:
            panel_ows.append(ow_role(tt_role["id"], allow_bits=tt_allow))

        await api.patch(session, f"/channels/{panel['id']}", {"permission_overwrites": panel_ows})
        print("  ✓ права панели")

        # Ticket Tool → Сотрудники
        if staff_role:
            async with session.put(
                f"{api.base}/guilds/{GUILD_ID}/members/{TICKET_TOOL_APP_ID}/roles/{STAFF_ROLE_ID}",
                headers=api.headers,
            ) as r:
                if r.status == 204:
                    print("  ✓ Ticket Tool получил роль Сотрудники")
                elif r.status == 404:
                    print("  ⚠ Ticket Tool не на сервере")
                elif r.status == 403:
                    # уже есть роль или нет прав — проверим
                    tt = await api.get(session, f"/guilds/{GUILD_ID}/members/{TICKET_TOOL_APP_ID}")
                    if STAFF_ROLE_ID in tt.get("roles", []):
                        print("  ✓ Ticket Tool уже имеет роль Сотрудники")
                    else:
                        print("  ⚠ выдай Ticket Tool роль Сотрудники вручную")
                else:
                    print(f"  ⚠ роль Сотрудники: {r.status} {await r.text()}")

        # Удалить наши тикеты и кнопки
        channels = await api.get(session, f"/guilds/{GUILD_ID}/channels")
        for ch in channels:
            if ch["type"] == 0 and ch["name"].startswith("🚨・"):
                parent = ch.get("parent_id")
                if parent == cat["id"]:
                    await api.delete(session, f"/channels/{ch['id']}")
                    print(f"  удалён {ch['name']}")

        msgs = await api.get(session, f"/channels/{panel['id']}/messages?limit=20")
        has_tt_panel = any(
            m["author"]["id"] == TICKET_TOOL_APP_ID and (m.get("components") or m.get("embeds"))
            for m in msgs
        )
        for msg in msgs:
            if msg["author"]["id"] == OUR_BOT_ID:
                await api.delete(session, f"/channels/{panel['id']}/messages/{msg['id']}")
                print("  удалено сообщение Настроебань в панели")

        if has_tt_panel:
            print("  ✓ панель Ticket Tool уже стоит")
        else:
            print("  → панель пустая — админ: /setup-panel в этом канале")

        print(f"\n✅ Готово: категория «{CAT_EMERGENCY}», канал «{PANEL}»")


if __name__ == "__main__":
    asyncio.run(main())
