"""Routes a role's request to a healthy NIM endpoint with load balancing + failover."""
from __future__ import annotations

import itertools

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.enums import AgentRole
from app.infrastructure.nim.client import NIMClient, NIMError
from app.infrastructure.nim.health import HealthMonitor
from app.infrastructure.nim.registry import ModelRegistry, model_registry

log = get_logger("nim.router")


class NIMRouter:
    """Owns the pool of endpoint clients and dispatches by agent role."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        settings = get_settings()
        self._registry = registry or model_registry
        self._clients = [NIMClient(url, settings.nim_api_key) for url in settings.nim_endpoints]
        self._rr = itertools.cycle(self._clients) if self._clients else None
        self.health = HealthMonitor(self._clients)

    async def start(self) -> None:
        await self.health.start()

    async def stop(self) -> None:
        await self.health.stop()
        for c in self._clients:
            await c.aclose()

    def _pick(self) -> NIMClient:
        pool = self.health.healthy_clients() or self._clients
        if not pool:
            raise NIMError("No NIM endpoints configured")
        # round-robin across the *healthy* pool
        for _ in range(len(self._clients)):
            client = next(self._rr)
            if client in pool:
                return client
        return pool[0]

    async def complete(self, role: AgentRole, messages: list[dict], **kwargs) -> str:
        spec = self._registry.for_role(role)
        last: Exception | None = None
        for attempt in range(max(1, len(self._clients))):
            client = self._pick()
            try:
                return await client.chat(spec.name, messages, **kwargs)
            except NIMError as exc:
                last = exc
                self.health._healthy[client.base_url] = False  # demote on failure
                log.warning("nim_failover", endpoint=client.base_url, attempt=attempt, error=str(exc))
        raise NIMError(f"All NIM endpoints failed for role={role}: {last}")

    async def stream(self, role: AgentRole, messages: list[dict], **kwargs):
        spec = self._registry.for_role(role)
        client = self._pick()
        async for chunk in client.stream_chat(spec.name, messages, **kwargs):
            yield chunk
