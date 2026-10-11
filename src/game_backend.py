"""Typed game workflow: asset intake, live-event context, and moderation priority."""

from __future__ import annotations

from typing import Literal, Protocol

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_gateway import InfraiError, InfraiGateway


AssetKind = Literal["avatar", "guild_emblem", "level_thumbnail"]
EventState = Literal["scheduled", "live", "ended"]
ModerationDecision = Literal["allow", "review", "block"]
QueuePriority = Literal["normal", "high", "critical"]


class PlayerAsset(BaseModel):
    asset_id: str = Field(min_length=1)
    player_id: str = Field(min_length=1)
    kind: AssetKind
    description: str = Field(min_length=1, max_length=2000)


class LiveEvent(BaseModel):
    event_id: str = Field(min_length=1)
    state: EventState
    featured_asset_ids: list[str] = Field(default_factory=list)


class ModerationRequest(BaseModel):
    asset: PlayerAsset
    event: LiveEvent | None = None


class ModerationQueueItem(BaseModel):
    asset_id: str
    event_id: str | None
    decision: ModerationDecision
    priority: QueuePriority


class AssetClassifier(Protocol):
    async def classify_asset(self, prompt: str) -> str:
        raise AssertionError("Protocol method")


def queue_priority(request: ModerationRequest, decision: ModerationDecision) -> QueuePriority:
    is_featured_live = bool(
        request.event
        and request.event.state == "live"
        and request.asset.asset_id in request.event.featured_asset_ids
    )
    if decision == "block" and is_featured_live:
        return "critical"
    if decision != "allow" or is_featured_live:
        return "high"
    return "normal"


async def moderate_asset(
    request: ModerationRequest, classifier: AssetClassifier
) -> ModerationQueueItem:
    event_context = (
        f"Event {request.event.event_id} is {request.event.state}."
        if request.event
        else "This asset is not attached to an event."
    )
    prompt = (
        f"Asset {request.asset.asset_id} is a {request.asset.kind}. "
        f"Player description: {request.asset.description}\n{event_context}"
    )
    raw_decision = await classifier.classify_asset(prompt)
    decision: ModerationDecision = (
        raw_decision if raw_decision in {"allow", "review", "block"} else "review"
    )
    return ModerationQueueItem(
        asset_id=request.asset.asset_id,
        event_id=request.event.event_id if request.event else None,
        decision=decision,
        priority=queue_priority(request, decision),
    )


def create_app(gateway: InfraiGateway) -> FastAPI:
    app = FastAPI(title="Game asset moderation")

    @app.post("/assets/moderate", response_model=ModerationQueueItem)
    async def submit_asset(request: ModerationRequest) -> ModerationQueueItem:
        try:
            return await moderate_asset(request, gateway)
        except InfraiError as exc:
            client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(
                status_code=client_status,
                detail={"code": exc.code, "message": exc.detail.get("message", exc.code)},
            ) from exc

    return app
