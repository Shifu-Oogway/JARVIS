"""Async NVIDIA NIM client (OpenAI-compatible /chat/completions, incl. streaming)."""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from app.core.config import get_settings


class NIMError(RuntimeError):
    pass


class NIMClient:
    """One client per NIM endpoint/gateway URL."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=timeout)

    async def chat(self, model: str, messages: list[dict], **kwargs) -> str:
        payload = {"model": model, "messages": messages, "stream": False, **kwargs}
        resp = await self._http.post("/chat/completions", json=payload)
        if resp.status_code >= 400:
            raise NIMError(f"NIM {resp.status_code}: {resp.text[:200]}")
        return resp.json()["choices"][0]["message"]["content"]

    async def stream_chat(self, model: str, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        payload = {"model": model, "messages": messages, "stream": True, **kwargs}
        async with self._http.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise NIMError(f"NIM {resp.status_code}: {body[:200]!r}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
                if delta:
                    yield delta

    async def ping(self) -> bool:
        try:
            resp = await self._http.get("/models")
            return resp.status_code < 500
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._http.aclose()
