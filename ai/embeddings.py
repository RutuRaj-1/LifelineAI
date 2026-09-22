"""Embedders. OpenAI when a key is configured, otherwise a deterministic hashing embedder (offline)."""
from __future__ import annotations

import hashlib
import re
from typing import Callable, Optional

import numpy as np

CacheGet = Callable[[str], Optional[list]]
CacheSet = Callable[[str, list], None]


def _norm(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1
    return (m / n).astype("float32")


class HashingEmbedder:
    """Feature-hashing over unigrams+bigrams. Lexical, but stable, free and offline."""

    name = "hashing-384"

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for i, t in enumerate(texts):
            toks = re.findall(r"[a-z0-9]+", t.lower())
            for gram in toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]:
                h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0 if (h >> 64) % 2 == 0 else -1.0
        return _norm(out)


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small",
                 cache_get: CacheGet | None = None, cache_set: CacheSet | None = None):
        from langchain_openai import OpenAIEmbeddings

        self.name, self._emb = model, OpenAIEmbeddings(model=model, api_key=api_key)
        self._get, self._set = cache_get, cache_set

    def embed(self, texts: list[str]) -> np.ndarray:
        keys = [f"emb:{self.name}:{hashlib.sha1(t.encode()).hexdigest()}" for t in texts]
        vecs: list = [self._get(k) if self._get else None for k in keys]
        missing = [i for i, v in enumerate(vecs) if v is None]
        if missing:
            fresh = self._emb.embed_documents([texts[i] for i in missing])
            for i, v in zip(missing, fresh):
                vecs[i] = v
                if self._set:
                    self._set(keys[i], v)
        return _norm(np.array(vecs, dtype="float32"))


def get_embedder(api_key: str = "", model: str = "text-embedding-3-small", cache_get=None, cache_set=None):
    if api_key:
        try:
            return OpenAIEmbedder(api_key, model, cache_get, cache_set)
        except Exception:  # noqa: BLE001
            pass
    return HashingEmbedder()
