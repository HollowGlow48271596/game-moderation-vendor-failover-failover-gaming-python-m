from __future__ import annotations

import asyncio

import httpx

from src.infrai_gateway import InfraiGateway


def test_routing_uses_put_and_exact_control_plane_fields() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True, "data": {"updated": True}})

    async def exercise() -> dict[str, object]:
        gateway = InfraiGateway(__name__, transport=httpx.MockTransport(handler))
        try:
            return await gateway.set_chat_routing(["vendor-a"])
        finally:
            await gateway.close()

    result = asyncio.run(exercise())

    assert result == {"updated": True}
    assert seen == {
        "method": "PUT",
        "path": "/v1/account/routing/set",
        "body": b'{"capability":"chat.completions","exclude":["vendor-a"]}',
    }


def test_routing_omits_empty_optional_exclusion() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True, "data": {"updated": True}})

    async def exercise() -> None:
        gateway = InfraiGateway(__name__, transport=httpx.MockTransport(handler))
        try:
            await gateway.set_chat_routing([])
        finally:
            await gateway.close()

    asyncio.run(exercise())

    assert seen["body"] == b'{"capability":"chat.completions"}'
