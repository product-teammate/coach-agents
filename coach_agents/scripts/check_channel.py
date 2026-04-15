"""Validate that the agent's Slack bot is a member of a target channel/DM.

Usage:
    python -m coach_agents.scripts.check_channel --agent english-coach --target dm
    python -m coach_agents.scripts.check_channel --agent english-coach --target channel:general
    python -m coach_agents.scripts.check_channel --agent english-coach --target thread

Exits 0 when ``ok=true``, 1 otherwise. Always prints a JSON object to stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import yaml

from ._common import agent_dir


async def check(agent_id: str, target: str) -> dict:
    try:
        adir = agent_dir(agent_id)
    except FileNotFoundError:
        return {"ok": False, "reason": "agent_not_found", "channel_id": None}

    cfg_path = adir / "agent.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    slack_channel = next(
        (
            c
            for c in (cfg.get("channels") or [])
            if c.get("type") == "slack" and c.get("enabled")
        ),
        None,
    )
    if not slack_channel:
        return {
            "ok": False,
            "reason": "slack_channel_not_configured",
            "channel_id": None,
        }

    env_prefix = slack_channel.get("env_prefix", "")
    bot_token = os.environ.get(f"{env_prefix}BOT_TOKEN")
    if not bot_token:
        return {
            "ok": False,
            "reason": "missing_bot_token",
            "channel_id": None,
        }

    # Lazy import keeps the module importable for tests that monkey-patch.
    from slack_sdk.web.async_client import AsyncWebClient  # type: ignore

    client = AsyncWebClient(token=bot_token)
    auth = await client.auth_test()
    bot_user_id = auth["user_id"]

    if target in ("dm", "thread"):
        return {
            "ok": True,
            "reason": "always_ok",
            "channel_id": None,
            "bot_user_id": bot_user_id,
        }

    if target.startswith("channel:"):
        name = target.split(":", 1)[1].lstrip("#")
        cursor: str | None = None
        while True:
            resp = await client.conversations_list(
                limit=200,
                types="public_channel,private_channel",
                cursor=cursor,
            )
            for ch in resp["channels"]:
                if ch["name"] != name:
                    continue
                # Walk membership with pagination — large channels exceed defaults.
                m_cursor: str | None = None
                members: list[str] = []
                while True:
                    m_resp = await client.conversations_members(
                        channel=ch["id"], cursor=m_cursor, limit=200
                    )
                    members.extend(m_resp.get("members", []))
                    m_cursor = (m_resp.get("response_metadata") or {}).get(
                        "next_cursor"
                    )
                    if not m_cursor:
                        break
                if bot_user_id in members:
                    return {
                        "ok": True,
                        "reason": "member",
                        "channel_id": ch["id"],
                        "channel_name": name,
                        "bot_user_id": bot_user_id,
                    }
                return {
                    "ok": False,
                    "reason": "not_in_channel",
                    "channel_id": ch["id"],
                    "channel_name": name,
                    "bot_user_id": bot_user_id,
                }
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
        return {
            "ok": False,
            "reason": "channel_not_found",
            "channel_id": None,
            "channel_name": name,
            "bot_user_id": bot_user_id,
        }

    return {"ok": False, "reason": "unknown_target_format", "channel_id": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True)
    parser.add_argument(
        "--target",
        required=True,
        help="dm | thread | channel:<name>",
    )
    args = parser.parse_args()

    result = asyncio.run(check(args.agent, args.target))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
