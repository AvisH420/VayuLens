"""Vector store abstraction.

A single VectorStore interface with three interchangeable backends:
  - faiss   : FAISS flat index (cosine via normalized inner product)
  - chroma  : ChromaDB persistent collection
  - memory  : pure-Python brute force (always available; correct cosine search)

Chunks and their metadata are persisted alongside vectors so retrieval can
reconstruct full citations.
"""
from __future__ import annotations

import json
import math
import pickle
from abc import ABC, abstractmethod
from pathlib import Path

from rag.config import VectorStoreCfg
from rag.logging_utils import get_logger
from rag.types import Chunk, ScoredChunk

log = get_logger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...

    @abstractmethod
    def search(self, query_vector: list[float], top_k: int) -> list[ScoredChunk]: ...

    @abstractmethod
    def all_chunks(self) -> list[Chunk]: ...

    @abstractmethod
    def persist(self) -> None: ...

    @abstractmethod
    def load(self) -> bool: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def clear(self) -> None: ...


class MemoryVectorStore(VectorStore):
    def __init__(self, path: Path, index_name: str):
        self._dir = path
        self._name = index_name
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        self._chunks.extend(chunks)
        self._vectors.extend(vectors)

    def search(self, query_vector: list[float], top_k: int) -> list[ScoredChunk]:
        scored = [
            ScoredChunk(chunk=c, score=_cosine(query_vector, v), retrieval_method="dense")
            for c, v in zip(self._chunks, self._vectors)
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def vectors_for(self, chunk_ids: list[str]) -> dict[str, list[float]]:
        index = {c.chunk_id: v for c, v in zip(self._chunks, self._vectors)}
        return {cid: index[cid] for cid in chunk_ids if cid in index}

    def persist(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._dir / f"{self._name}.pkl", "wb") as f:
            pickle.dump(
                {"chunks": [c.model_dump() for c in self._chunks],
                 "vectors": self._vectors},
                f,
            )

    def load(self) -> bool:
        p = self._dir / f"{self._name}.pkl"
        if not p.exists():
            return False
        with open(p, "rb") as f:
            data = pickle.load(f)
        self._chunks = [Chunk(**c) for c in data["chunks"]]
        self._vectors = data["vectors"]
        return True

    def count(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._chunks = []
        self._vectors = []


class FaissVectorStore(VectorStore):
    def __init__(self, path: Path, index_name: str, metric: str = "cosine"):
        import faiss  # type: ignore

        self._faiss = faiss
        self._dir = path
        self._name = index_name
        self._metric = metric
        self._index = None
        self._chunks: list[Chunk] = []
        self._dim: int | None = None

    def _ensure_index(self, dim: int) -> None:
        if self._index is None:
            self._dim = dim
            self._index = self._faiss.IndexFlatIP(dim)  # cosine via normalized IP

    def _normalize(self, vectors: list[list[float]]):
        import numpy as np

        arr = np.array(vectors, dtype="float32")
        if self._metric == "cosine":
            self._faiss.normalize_L2(arr)
        return arr

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if not vectors:
            return
        self._ensure_index(len(vectors[0]))
        self._index.add(self._normalize(vectors))
        self._chunks.extend(chunks)

    def search(self, query_vector: list[float], top_k: int) -> list[ScoredChunk]:
        if self._index is None or not self._chunks:
            return []
        arr = self._normalize([query_vector])
        k = min(top_k, len(self._chunks))
        scores, idxs = self._index.search(arr, k)
        out: list[ScoredChunk] = []
        for score, idx in zip(scores[0], idxs[0]):
            if 0 <= idx < len(self._chunks):
                out.append(
                    ScoredChunk(chunk=self._chunks[idx], score=float(score),
                                retrieval_method="dense")
                )
        return out

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def persist(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        if self._index is not None:
            self._faiss.write_index(self._index, str(self._dir / f"{self._name}.faiss"))
        meta = {"chunks": [c.model_dump() for c in self._chunks], "dim": self._dim}
        (self._dir / f"{self._name}.meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )

    def load(self) -> bool:
        idx_path = self._dir / f"{self._name}.faiss"
        meta_path = self._dir / f"{self._name}.meta.json"
        if not idx_path.exists() or not meta_path.exists():
            return False
        self._index = self._faiss.read_index(str(idx_path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self._chunks = [Chunk(**c) for c in meta["chunks"]]
        self._dim = meta.get("dim")
        return True

    def count(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._index = None
        self._chunks = []
        self._dim = None


class ChromaVectorStore(VectorStore):
    def __init__(self, path: Path, index_name: str):
        import chromadb  # type: ignore

        self._dir = path
        self._name = index_name
        self._dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path / "chroma"))
        self._collection = self._client.get_or_create_collection(
            name=index_name, metadata={"hnsw:space": "cosine"}
        )

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors,
            documents=[c.text for c in chunks],
            metadatas=[self._meta(c) for c in chunks],
        )

    @staticmethod
    def _meta(c: Chunk) -> dict:
        return {
            "doc_id": c.doc_id, "source": c.source, "title": c.title or "",
            "doc_type": c.doc_type or "", "page": c.page or -1,
            "section": c.section or "",
        }

    def search(self, query_vector: list[float], top_k: int) -> list[ScoredChunk]:
        res = self._collection.query(
            query_embeddings=[query_vector], n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        out: list[ScoredChunk] = []
        if not res["ids"] or not res["ids"][0]:
            return out
        for cid, doc, meta, dist in zip(
            res["ids"][0], res["documents"][0],
            res["metadatas"][0], res["distances"][0],
        ):
            chunk = Chunk(
                chunk_id=cid, text=doc, doc_id=meta["doc_id"], source=meta["source"],
                title=meta["title"] or None, doc_type=meta["doc_type"] or None,
                page=None if meta["page"] == -1 else meta["page"],
                section=meta["section"] or None,
            )
            out.append(
                ScoredChunk(chunk=chunk, score=1.0 - float(dist),
                            retrieval_method="dense")
            )
        return out

    def all_chunks(self) -> list[Chunk]:
        res = self._collection.get(include=["documents", "metadatas"])
        chunks: list[Chunk] = []
        for cid, doc, meta in zip(res["ids"], res["documents"], res["metadatas"]):
            chunks.append(
                Chunk(
                    chunk_id=cid, text=doc, doc_id=meta["doc_id"],
                    source=meta["source"], title=meta["title"] or None,
                    doc_type=meta["doc_type"] or None,
                    page=None if meta["page"] == -1 else meta["page"],
                    section=meta["section"] or None,
                )
            )
        return chunks

    def persist(self) -> None:  # Chroma persists automatically
        pass

    def load(self) -> bool:
        return self._collection.count() > 0

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        self._client.delete_collection(self._name)
        self._collection = self._client.get_or_create_collection(
            name=self._name, metadata={"hnsw:space": "cosine"}
        )


def build_vector_store(
    cfg: VectorStoreCfg, store_dir: str, index_name: str
) -> VectorStore:
    path = Path(store_dir)
    if cfg.backend == "faiss":
        try:
            return FaissVectorStore(path, index_name, cfg.metric)
        except ImportError:
            log.warning("faiss not installed; using in-memory vector store.")
            return MemoryVectorStore(path, index_name)
    if cfg.backend == "chroma":
        try:
            return ChromaVectorStore(path, index_name)
        except ImportError:
            log.warning("chromadb not installed; using in-memory vector store.")
            return MemoryVectorStore(path, index_name)
    if cfg.backend == "memory":
        return MemoryVectorStore(path, index_name)
    raise ValueError(f"Unknown vector store backend: {cfg.backend}")
