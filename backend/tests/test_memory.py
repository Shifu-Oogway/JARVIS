"""Phase 2: vault round-trip, semantic store, context assembly, graph."""
import tempfile
from pathlib import Path

import pytest

from app.infrastructure.obsidian.graph import KnowledgeGraph
from app.infrastructure.obsidian.vault import ObsidianVault
from app.memory.context_engine import ContextAssemblyEngine
from app.memory.embeddings import HashingEmbedding
from app.memory.reranker import Reranker
from app.memory.store import LAYER_LONG_TERM, MemoryStore


def _vault() -> ObsidianVault:
    v = ObsidianVault(Path(tempfile.mkdtemp()))
    v.ensure_structure()
    return v


def test_vault_roundtrip_and_extraction():
    v = _vault()
    path = v.write_note(
        "Research", "NVIDIA Q1",
        "Strong datacenter growth. See [[Jensen Huang]]. #ai #earnings",
        frontmatter={"type": "research", "agent": "research_agent", "tags": ["nvidia"]},
    )
    note = v.read_note(path)
    assert note.frontmatter["type"] == "research"
    assert "Jensen Huang" in note.links
    assert {"ai", "earnings", "nvidia"} <= note.tags


@pytest.mark.asyncio
async def test_semantic_search_ranks_relevant_first():
    store = MemoryStore(HashingEmbedding())
    await store.add("NVIDIA datacenter GPU revenue grew sharply", LAYER_LONG_TERM)
    await store.add("A recipe for sourdough bread with rye flour", LAYER_LONG_TERM)
    results = await store.search("nvidia gpu revenue", k=2)
    assert results and "NVIDIA" in results[0][0].content


@pytest.mark.asyncio
async def test_context_engine_respects_budget_and_active_first():
    v = _vault()
    v.write_note("Research", "GPU Note", "NVIDIA GPU revenue and datacenter demand.")
    store = MemoryStore(HashingEmbedding())
    await store.hydrate_from_vault(v)
    engine = ContextAssemblyEngine(store, Reranker(), v, KnowledgeGraph.build(v), token_budget=500)
    pkg = await engine.assemble("nvidia gpu", active_context="Current goal: brief the board.")
    assert pkg.token_estimate <= 500
    assert pkg.text.startswith("## Active context")
    assert "active" in pkg.layers_used


def test_graph_builds_link_and_tag_edges():
    v = _vault()
    v.write_note("Projects", "Apollo", "Depends on [[Mercury]] #priority")
    g = KnowledgeGraph.build(v)
    kinds = {k for _, _, k in g.edges}
    assert "link" in kinds and "tag" in kinds
    assert "Mercury" in g.neighbors("Apollo")
