"""Minimal check: Claude Agent SDK picks up the Claude Code Pro session
(without ANTHROPIC_API_KEY) and returns a response. Run: python scripts/sanity_check.py
"""

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, query


async def main() -> None:
    print("Asking Claude via claude-agent-sdk...")
    async for message in query(prompt="Say one word: 'working'."):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"  Response: {block.text.strip()!r}")
        if isinstance(message, ResultMessage):
            if message.is_error:
                print(f"  Error: {message.result}")
                sys.exit(1)
            print(f"  Cost: ${message.total_cost_usd or 0:.6f}")
            print(f"  Session: {message.session_id}")
    print("OK: SDK connected and responded.")


if __name__ == "__main__":
    asyncio.run(main())
