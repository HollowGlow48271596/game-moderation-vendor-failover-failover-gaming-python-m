"""Configure vendor eligibility, then run one visible game moderation decision."""

from __future__ import annotations

import argparse
import asyncio
import json
import os

from src.game_backend import LiveEvent, ModerationRequest, PlayerAsset, moderate_asset
from src.infrai_gateway import InfraiGateway


async def run(excluded_vendors: list[str]) -> None:
    gateway = InfraiGateway(api_key=os.environ["INFRAI_API_KEY"])
    try:
        await gateway.set_chat_routing(excluded_vendors)
        request = ModerationRequest(
            asset=PlayerAsset(
                asset_id="asset-guild-42",
                player_id="player-7",
                kind="guild_emblem",
                description="A red dragon crest for the championship broadcast.",
            ),
            event=LiveEvent(
                event_id="world-final",
                state="live",
                featured_asset_ids=["asset-guild-42"],
            ),
        )
        item = await moderate_asset(request, gateway)
        print(item.model_dump_json(indent=2))
    finally:
        await gateway.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Vendor to exclude from chat routing; repeat for more than one.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.exclude))


if __name__ == "__main__":
    main()
