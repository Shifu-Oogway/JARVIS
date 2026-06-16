"""Embedding providers.

Hosted path: NVIDIA NeMo Retriever `nv-embedqa-e5-v5` (1024-dim, requires input_type).
Offline path: a deterministic hashing embedding so semantic memory runs with no network.
The provider is chosen by config; both satisfy the same interface.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("memory.embeddings")
_TOKEN = re.compile(r"[a-z0-9]+")


def _l2(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # vectors are L2-normalised


class EmbeddingProvider(Protocol):
    dim: int
    async def embed(self, texts: list[str], input_type: str = "passage") -> list[list[float]]: ...


class HashingEmbedding:
    """Dependency-free fallback: hashed bag-of-tokens, L2-normalised."""
    dim = 256

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        return _l2(vec)

    async def embed(self, texts: list[str], input_type: str = "passage") -> list[list[float]]:
        return [self._one(t) for t in texts]


class NIMEmbedding:
    """NVIDIA NeMo Retriever embedding NIM (OpenAI-compatible /embeddings)."""
    dim = 1024

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._model = model
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=30.0)
        self._fallback = HashingEmbedding()

    async def embed(self, texts: list[str], input_type: str = "passage") -> list[list[float]]:
        try:
            resp = await self._http.post(
                "/embeddings",
                json={"input": texts, "model": self._model, "input_type": input_type},
            )
            resp.raise_for_status()
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            return [_l2(d["embedding"]) for d in data]
        except (httpx.HTTPError, KeyError) as exc:
            log.warning("embed_fallback", error=str(exc))
            self.dim = self._fallback.dim
            return await self._fallback.embed(texts, input_type)


def get_embedding_provider() -> EmbeddingProvider:
    s = get_settings()
    if s.nim_api_key:
        return NIMEmbedding(s.nim_base_url, s.nim_api_key, s.nim_embed_model)
    log.info("embedding_offline_fallback")
    return HashingEmbedding()
