from __future__ import annotations

import asyncio

from src.game_backend import LiveEvent, ModerationRequest, PlayerAsset, moderate_asset


class FixedClassifier:
    def __init__(self, decision: str) -> None:
        self.decision = decision
        self.prompt = ""

    async def classify_asset(self, prompt: str) -> str:
        self.prompt = prompt
        return self.decision


def test_blocked_featured_asset_enters_critical_live_queue() -> None:
    classifier = FixedClassifier("block")
    request = ModerationRequest(
        asset=PlayerAsset(
            asset_id="asset-9",
            player_id="player-2",
            kind="level_thumbnail",
            description="A player-authored arena poster.",
        ),
        event=LiveEvent(
            event_id="final-1", state="live", featured_asset_ids=["asset-9"]
        ),
    )

    result = asyncio.run(moderate_asset(request, classifier))

    assert result.model_dump() == {
        "asset_id": "asset-9",
        "event_id": "final-1",
        "decision": "block",
        "priority": "critical",
    }
    assert "final-1" in classifier.prompt
