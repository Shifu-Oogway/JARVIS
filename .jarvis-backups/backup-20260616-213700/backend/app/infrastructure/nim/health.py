"""Background health monitor for NIM endpoints."""
from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.infrastructure.nim.client import NIMClient

log = get_logger("nim.health")


class HealthMonitor:
    def __init__(self, clients: list[NIMClient], interval: float = 30.0) -> None:
        self._clients = clients
        self._interval = interval
        self._healthy: dict[str, bool] = {c.base_url: True for c in clients}
        self._task: asyncio.Task | None = None

    def is_healthy(self, base_url: str) -> bool:
        return self._healthy.get(base_url, False)

    def healthy_clients(self) -> list[NIMClient]:
        return [c for c in self._clients if self._healthy.get(c.base_url, False)]

    async def _check_once(self) -> None:
        results = await asyncio.gather(*(c.ping() for c in self._clients), return_exceptions=True)
        for client, ok in zip(self._clients, results):
            healthy = ok is True
            if self._healthy.get(client.base_url) != healthy:
                log.info("nim_health_change", endpoint=client.base_url, healthy=healthy)
            self._healthy[client.base_url] = healthy

    async def _loop(self) -> None:
        while True:
            await self._check_once()
            await asyncio.sleep(self._interval)

    async def start(self) -> None:
        await self._check_once()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
