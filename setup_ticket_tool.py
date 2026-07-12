#!/usr/bin/env python3
"""Ticket Tool setup — запускает REST-версию (без конфликта gateway)."""

from setup_ticket_tool_rest import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
