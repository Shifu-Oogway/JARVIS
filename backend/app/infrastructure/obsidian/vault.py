"""Obsidian vault adapter — JARVIS's persistent knowledge store.

Reads/writes plain markdown with YAML frontmatter, and extracts the structure
(tags, [[wikilinks]], metadata) the knowledge graph and memory layers depend on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

VAULT_DIRS = [
    "Projects", "People", "Meetings", "Research", "Reports", "Agents",
    "Tasks", "Journal", "Knowledge", "Workflows", "System",
]

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_TAG = re.compile(r"(?:^|\s)#([A-Za-z0-9_/-]+)")
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def _slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _-]", "", title).strip().replace(" ", "-")[:80] or "note"


@dataclass
class Note:
    title: str
    folder: str
    body: str
    frontmatter: dict = field(default_factory=dict)
    path: Path | None = None

    @property
    def tags(self) -> set[str]:
        fm = self.frontmatter.get("tags", [])
        fm = fm if isinstance(fm, list) else [fm]
        return {str(t) for t in fm} | {m for m in _TAG.findall(self.body)}

    @property
    def links(self) -> set[str]:
        return {m.split("|")[0].strip() for m in _WIKILINK.findall(self.body)}


class ObsidianVault:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def ensure_structure(self) -> None:
        for d in VAULT_DIRS:
            (self.root / d).mkdir(parents=True, exist_ok=True)

    # -- write -----------------------------------------------------------
    def write_note(self, folder: str, title: str, body: str,
                   frontmatter: dict | None = None) -> Path:
        fm = {"created": date.today().isoformat(), **(frontmatter or {})}
        path = self.root / folder / f"{_slug(title)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        front = yaml.safe_dump(fm, sort_keys=False).strip()
        path.write_text(f"---\n{front}\n---\n\n# {title}\n\n{body}\n", encoding="utf-8")
        return path

    # -- read ------------------------------------------------------------
    def read_note(self, path: str | Path) -> Note:
        path = Path(path)
        raw = path.read_text(encoding="utf-8")
        m = _FRONTMATTER.match(raw)
        if m:
            frontmatter = yaml.safe_load(m.group(1)) or {}
            body = m.group(2)
        else:
            frontmatter, body = {}, raw
        title = frontmatter.get("title") or path.stem.replace("-", " ")
        return Note(title=title, folder=path.parent.name, body=body,
                    frontmatter=frontmatter, path=path)

    def list_notes(self, folder: str | None = None) -> list[Path]:
        base = self.root / folder if folder else self.root
        return sorted(base.rglob("*.md"))

    def all_notes(self) -> list[Note]:
        return [self.read_note(p) for p in self.list_notes()]

    # -- query -----------------------------------------------------------
    def search_by_tag(self, tag: str) -> list[Note]:
        return [n for n in self.all_notes() if tag in n.tags]

    def search_by_meta(self, key: str, value) -> list[Note]:
        return [n for n in self.all_notes() if n.frontmatter.get(key) == value]

    def tree(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for d in VAULT_DIRS:
            folder = self.root / d
            out[d] = sorted(p.stem.replace("-", " ") for p in folder.glob("*.md")) if folder.exists() else []
        return out
