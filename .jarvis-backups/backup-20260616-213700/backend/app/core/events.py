"""Redis-backed event bus powering the live dashboard feed."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("events")
CHANNEL = "jarvis.events"


class EventBus:
    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    async def publish(self, kind: str, payload: dict[str, Any]) -> None:
        event = {
            "kind": kind,
            "payload": payload,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if self._redis:
            try:
                await self._redis.publish(CHANNEL, json.dumps(event))
            except Exception as exc:  # noqa: BLE001 - never let telemetry break a request
                log.warning("event_publish_failed", error=str(exc))
        log.info("event", **event)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        if not self._redis:
            return
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(CHANNEL)


event_bus = EventBus()
