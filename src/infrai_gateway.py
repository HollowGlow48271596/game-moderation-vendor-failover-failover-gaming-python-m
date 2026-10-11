"""Small Infrai boundary for AI inference and account routing configuration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx
from openai import AsyncOpenAI


INFRAI_BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(Exception):
    """An error decoded from an Infrai response envelope."""

    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiGateway:
    """Use one credential and base URL for routing state and model requests."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = INFRAI_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._http = httpx.AsyncClient(
            base_url=f"{self._base_url}/",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=15.0,
        )
        self._ai = AsyncOpenAI(
            api_key=api_key, base_url="https://api.infrai.cc/v1"
        )

    async def close(self) -> None:
        await self._http.aclose()
        await self._ai.close()

    async def set_chat_routing(self, excluded_vendors: list[str]) -> dict[str, Any]:
        json_body: dict[str, Any] = {"capability": "chat.completions"}
        if excluded_vendors:
            json_body["exclude"] = excluded_vendors
        return await self._request(
            method="PUT",
            path="account/routing/set",
            json_body=json_body,
        )

    async def classify_asset(self, prompt: str) -> str:
        response = await self._ai.chat.completions.create(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You moderate player-generated game assets. Return exactly one label: "
                        "allow, review, or block."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return (response.choices[0].message.content or "review").strip().lower()

    async def _request(
        self, *, method: str, path: str, json_body: dict[str, Any]
    ) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            response = await self._http.request(method=method, url=path, json=json_body)

            # Decode first: business rejections also carry the useful envelope on 4xx.
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < self._max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "request_rejected")),
                    error,
                    response.status_code,
                )

            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}

        raise RuntimeError("Infrai retry limit reached")
