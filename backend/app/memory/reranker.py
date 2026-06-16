"""Cross-encoder reranking via NeMo Retriever Reranking NIM (/v1/ranking).

Disabled (identity ordering) when no rerank URL is configured.
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("memory.reranker")


class Reranker:
    def __init__(self) -> None:
        s = get_settings()
        self._url = s.nim_rerank_url
        self._model = s.nim_rerank_model
        headers = {"Content-Type": "application/json"}
        if s.nim_api_key:
            headers["Authorization"] = f"Bearer {s.nim_api_key}"
        self._http = httpx.AsyncClient(headers=headers, timeout=30.0) if self._url else None

    @property
    def enabled(self) -> bool:
        return self._http is not None

    async def rerank(self, query: str, passages: list[str], top_k: int) -> list[int]:
        """Return passage indices ordered most→least relevant."""
        if not self._http or not passages:
            return list(range(min(top_k, len(passages))))
        try:
            resp = await self._http.post(
                self._url,
                json={"model": self._model, "query": {"text": query},
                      "passages": [{"text": p} for p in passages]},
            )
            resp.raise_for_status()
            rankings = resp.json()["rankings"]
            order = [r["index"] for r in sorted(rankings, key=lambda r: -r["logit"])]
            return order[:top_k]
        except (httpx.HTTPError, KeyError) as exc:
            log.warning("rerank_fallback", error=str(exc))
            return list(range(min(top_k, len(passages))))
