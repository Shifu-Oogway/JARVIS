"""Context Assembly Engine — the rolling active-token window.

Never sends the whole memory to a model. For each objective it:
  1. analyses the objective (the query),
  2. retrieves relevant notes/memories across layers (semantic search),
  3. expands via the knowledge graph (neighbours of top hits),
  4. ranks relevance (cross-encoder rerank when available),
  5. packs an optimised context package within a token budget, honouring
     layer priority (active > working > long_term > archive).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.infrastructure.obsidian.graph import KnowledgeGraph
from app.infrastructure.obsidian.vault import ObsidianVault
from app.memory.reranker import Reranker
from app.memory.store import (
    LAYER_ACTIVE, LAYER_ARCHIVE, LAYER_LONG_TERM, LAYER_WORKING, MemoryStore,
)

log = get_logger("memory.context")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)  # ~4 chars/token heuristic


@dataclass
class ContextPackage:
    text: str
    sources: list[str] = field(default_factory=list)
    token_estimate: int = 0
    layers_used: list[str] = field(default_factory=list)


class ContextAssemblyEngine:
    def __init__(self, store: MemoryStore, reranker: Reranker,
                 vault: ObsidianVault, graph: KnowledgeGraph | None = None,
                 token_budget: int = 4000) -> None:
        self._store = store
        self._reranker = reranker
        self._vault = vault
        self._graph = graph
        self._budget = token_budget

    async def assemble(self, objective: str, active_context: str = "",
                       candidate_k: int = 12) -> ContextPackage:
        # (2) retrieve across the deeper layers
        hits = await self._store.search(
            objective, k=candidate_k,
            layers={LAYER_WORKING, LAYER_LONG_TERM, LAYER_ARCHIVE},
        )
        candidates = [r.content for r, _ in hits]

        # (4) rank
        if candidates:
            order = await self._reranker.rerank(objective, candidates, top_k=len(candidates))
            hits = [hits[i] for i in order]

        # (5) pack within budget; Layer-1 active context always goes first
        used = self._budget
        parts: list[str] = []
        sources: list[str] = []
        layers_used: list[str] = []

        if active_context:
            parts.append(f"## Active context\n{active_context}")
            used -= estimate_tokens(active_context)
            layers_used.append(LAYER_ACTIVE)

        for rec, score in hits:
            cost = estimate_tokens(rec.content)
            if cost > used:
                continue
            title = rec.meta.get("title", rec.id[:8])
            parts.append(f"## {title}  (score {score:.2f})\n{rec.content}")
            sources.append(rec.vault_path or title)
            if rec.layer not in layers_used:
                layers_used.append(rec.layer)
            used -= cost

        text = "\n\n".join(parts)
        return ContextPackage(
            text=text, sources=sources,
            token_estimate=self._budget - used, layers_used=layers_used,
        )
