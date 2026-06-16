"""Knowledge graph derived from vault links, tags and metadata references."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.infrastructure.obsidian.vault import ObsidianVault


@dataclass
class KnowledgeGraph:
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[tuple[str, str, str]] = field(default_factory=list)  # (src, dst, kind)

    @classmethod
    def build(cls, vault: ObsidianVault) -> "KnowledgeGraph":
        g = cls()
        for note in vault.all_notes():
            g.nodes[note.title] = {"folder": note.folder, "tags": sorted(note.tags)}
            for link in note.links:
                g.edges.append((note.title, link, "link"))
            for tag in note.tags:
                tag_node = f"#{tag}"
                g.nodes.setdefault(tag_node, {"folder": "_tags", "tags": []})
                g.edges.append((note.title, tag_node, "tag"))
        return g

    def neighbors(self, title: str) -> list[str]:
        out = {d for s, d, _ in self.edges if s == title}
        out |= {s for s, d, _ in self.edges if d == title}
        return sorted(out)

    def to_dict(self) -> dict:
        return {
            "nodes": [{"id": k, **v} for k, v in self.nodes.items()],
            "edges": [{"source": s, "target": d, "kind": k} for s, d, k in self.edges],
        }
