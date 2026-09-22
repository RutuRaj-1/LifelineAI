from __future__ import annotations

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover
    faiss = None


class VectorStore:
    """Inner-product store over L2-normalised vectors (== cosine). FAISS when installed, numpy otherwise."""

    def __init__(self, dim: int):
        self.dim, self.metas, self._vecs = dim, [], np.zeros((0, dim), dtype="float32")
        self._index = faiss.IndexFlatIP(dim) if faiss else None

    def add(self, vectors: np.ndarray, metas: list[dict]) -> None:
        if not len(metas):
            return
        self.metas.extend(metas)
        if self._index is not None:
            self._index.add(vectors)
        else:
            self._vecs = np.vstack([self._vecs, vectors])

    def search(self, qvec: np.ndarray, k: int = 5) -> list[dict]:
        if not self.metas:
            return []
        k = min(k, len(self.metas))
        if self._index is not None:
            scores, ids = self._index.search(qvec.reshape(1, -1), k)
            pairs = zip(ids[0], scores[0])
        else:
            s = self._vecs @ qvec.reshape(-1)
            top = np.argsort(-s)[:k]
            pairs = zip(top, s[top])
        return [{**self.metas[int(i)], "score": round(float(s), 4)} for i, s in pairs if i >= 0]
