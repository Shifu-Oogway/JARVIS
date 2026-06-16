"""Memory compression: Raw → Summary → Knowledge Entry → Vault."""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.enums import AgentRole
from app.infrastructure.nim.client import NIMError
from app.infrastructure.nim.router import NIMRouter
from app.infrastructure.obsidian.vault import ObsidianVault
from app.memory.store import LAYER_LONG_TERM, MemoryStore

log = get_logger("memory.compression")

_DISTILL = (
    "Distil the text into a concise knowledge entry: 3-6 bullet points capturing "
    "durable facts, decisions, and entities. No preamble."
)


class MemoryCompressor:
    def __init__(self, router: NIMRouter, vault: ObsidianVault, store: MemoryStore) -> None:
        self._router = router
        self._vault = vault
        self._store = store

    async def distill(self, raw: str) -> str:
        try:
            return await self._router.complete(
                AgentRole.MEMORY,
                [{"role": "system", "content": _DISTILL},
                 {"role": "user", "content": raw[:6000]}],
            )
        except NIMError:
            # Offline fallback: extractive — keep the first lines.
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            return "\n".join(f"- {l}" for l in lines[:6])

    async def to_knowledge(self, raw: str, title: str, *, folder: str = "Knowledge",
                           agent: str = "memory_agent", extra_meta: dict | None = None) -> str:
        summary = await self.distill(raw)
        meta = {"type": "knowledge", "agent": agent, **(extra_meta or {})}
        path = self._vault.write_note(folder, title, summary, frontmatter=meta)
        await self._store.add(f"{title}\n{summary}", layer=LAYER_LONG_TERM,
                              meta={"title": title, "folder": folder}, vault_path=str(path))
        log.info("knowledge_written", path=str(path))
        return str(path)
