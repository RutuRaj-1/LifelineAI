from __future__ import annotations

from .chunking import chunk_text
from .vectorstore import VectorStore


class RagPipeline:
    """documents -> chunks -> embeddings -> FAISS -> top-k chunks (with source metadata)."""

    def __init__(self, embedder):
        self.embedder = embedder

    def build_index(self, docs: list[dict]) -> VectorStore:
        chunks, metas = [], []
        for d in docs:
            for i, c in enumerate(chunk_text(d["text"])):
                chunks.append(c)
                metas.append({"report_id": d["id"], "title": d["title"], "date": d.get("date"),
                              "chunk": i, "text": c})
        vecs = self.embedder.embed(chunks) if chunks else None
        store = VectorStore(vecs.shape[1] if vecs is not None else 384)
        if vecs is not None:
            store.add(vecs, metas)
        return store

    def retrieve(self, store: VectorStore, query: str, k: int = 6) -> list[dict]:
        return store.search(self.embedder.embed([query])[0], k)
