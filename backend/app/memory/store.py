"""In-memory vector index over memory entries, hydrated from the Obsidian vault.

The vault (markdown files) is the durable source of truth; this store is the
queryable semantic index built from it plus runtime entries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.enums import AgentRole  # noqa: F401 (re-exported convenience)
from app.infrastructure.obsidian.vault import ObsidianVault
from app.memory.embeddings import EmbeddingProvider, cosine

# Memory layers (rolling window). Lower number = closer to the model.
LAYER_ACTIVE = "active"
LAYER_WORKING = "working"
LAYER_LONG_TERM = "long_term"
LAYER_ARCHIVE = "archive"
_LAYER_PRIORITY = {LAYER_ACTIVE: 0, LAYER_WORKING: 1, LAYER_LONG_TERM: 2, LAYER_ARCHIVE: 3}


@dataclass
class MemoryRecord:
    content: str
    layer: str
    vector: list[float] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    vault_path: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryStore:
    def __init__(self, embedder: EmbeddingProvider) -> None:
        self._embedder = embedder
        self._items: list[MemoryRecord] = []

    async def add(self, content: str, layer: str = LAYER_WORKING,
                  meta: dict | None = None, vault_path: str | None = None) -> MemoryRecord:
        (vec,) = await self._embedder.embed([content], input_type="passage")
        rec = MemoryRecord(content=content, layer=layer, vector=vec,
                           meta=meta or {}, vault_path=vault_path)
        self._items.append(rec)
        return rec

    async def hydrate_from_vault(self, vault: ObsidianVault) -> int:
        notes = vault.all_notes()
        if not notes:
            return 0
        texts = [f"{n.title}\n{n.body}" for n in notes]
        vectors = await self._embedder.embed(texts, input_type="passage")
        for note, text, vec in zip(notes, texts, vectors):
            layer = LAYER_ARCHIVE if note.folder == "Journal" else LAYER_LONG_TERM
            self._items.append(MemoryRecord(
                content=text, layer=layer, vector=vec,
                meta={"title": note.title, "folder": note.folder, "tags": sorted(note.tags)},
                vault_path=str(note.path),
            ))
        return len(notes)

    async def search(self, query: str, k: int = 8,
                     layers: set[str] | None = None) -> list[tuple[MemoryRecord, float]]:
        if not self._items:
            return []
        (q,) = await self._embedder.embed([query], input_type="query")
        pool = [r for r in self._items if layers is None or r.layer in layers]
        scored = [(r, cosine(q, r.vector)) for r in pool if r.vector]
        scored.sort(key=lambda x: (-x[1], _LAYER_PRIORITY.get(x[0].layer, 9)))
        return scored[:k]

    def counts(self) -> dict[str, int]:
        out = {LAYER_ACTIVE: 0, LAYER_WORKING: 0, LAYER_LONG_TERM: 0, LAYER_ARCHIVE: 0}
        for r in self._items:
            out[r.layer] = out.get(r.layer, 0) + 1
        return out

    def recent(self, n: int = 10) -> list[MemoryRecord]:
        return sorted(self._items, key=lambda r: r.created_at, reverse=True)[:n]
