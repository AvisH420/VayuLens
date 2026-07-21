"""Vector store: dense similarity search over indexed chunks.

Follows the same philosophy as the rest of the RAG stack — a correct,
zero-dependency default that always runs, with optional acceleration when a
heavier library is present:

  * Persistence is plain JSON (chunk + vector), so an index survives restarts
    with no binary format and no extra deps.
  * Search uses numpy when available (vectorised cosine) and falls back to a
    pure-Python cosine otherwise. Both return identical rankings.

``build_vector_store`` accepts the configured backend name ("faiss", "chroma",
"memory") but returns this store for all of them: it is the reliable path that
guarantees the pipeline runs offline. The backend name is logged so a heavier
index can be slotted in later without changing any call site.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from rag.config import VectorStoreCfg
from rag.logging_utils import get_logger
from rag.types import Chunk, ScoredChunk

log = get_logger(__name__)

try:  # optional acceleration only
    import numpy as _np  # type: ignore
except Exception:  # noqa: BLE001
    _np = None


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Used by the retriever's MMR too."""
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    return dot / denom if denom else 0.0


class VectorStore:
    """In-memory dense index with JSON persistence.

    Holds chunk/vector pairs, searches by cosine similarity, and mirrors itself
    to ``{dir}/{index_name}.json`` so re-ingestion is not required every run.
    """

    def __init__(self, directory: str | Path, index_name: str, metric: str = "cosine"):
        self._dir = Path(directory)
        self._index_name = index_name
        self._metric = metric
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []
        self._matrix = None  # cached numpy matrix, invalidated on write

    # ---------------------------- persistence ----------------------------
    @property
    def _path(self) -> Path:
        return self._dir / f"{self._index_name}.json"

    def load(self) -> None:
        """Load a persisted index if one exists; otherwise start empty."""
        if not self._path.is_file():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            self._chunks = [Chunk.model_validate(c) for c in payload.get("chunks", [])]
            self._vectors = [list(v) for v in payload.get("vectors", [])]
            self._matrix = None
            log.info("Loaded vector index %s (%d chunks)", self._path, len(self._chunks))
        except Exception as exc:  # noqa: BLE001 — a corrupt cache must not brick startup
            log.warning("Could not load vector index %s (%s); starting empty.",
                        self._path, exc)
            self._chunks, self._vectors, self._matrix = [], [], None

    def persist(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "index_name": self._index_name,
            "metric": self._metric,
            "chunks": [c.model_dump() for c in self._chunks],
            "vectors": self._vectors,
        }
        self._path.write_text(json.dumps(payload), encoding="utf-8")
        log.info("Persisted vector index %s (%d chunks)", self._path, len(self._chunks))

    # ---------------------------- mutation ----------------------------
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"add() got {len(chunks)} chunks but {len(vectors)} vectors"
            )
        self._chunks.extend(chunks)
        self._vectors.extend([list(v) for v in vectors])
        self._matrix = None

    def clear(self) -> None:
        self._chunks, self._vectors, self._matrix = [], [], None

    # ---------------------------- access ----------------------------
    def count(self) -> int:
        return len(self._chunks)

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks)

    # ---------------------------- search ----------------------------
    def search(self, query_vector: list[float], k: int) -> list[ScoredChunk]:
        if not self._chunks or not query_vector:
            return []
        k = max(1, min(k, len(self._chunks)))

        if _np is not None:
            scored = self._search_numpy(query_vector, k)
        else:
            scores = [(_cosine(query_vector, v), i) for i, v in enumerate(self._vectors)]
            scores.sort(key=lambda x: x[0], reverse=True)
            scored = scores[:k]

        return [
            ScoredChunk(chunk=self._chunks[i], score=float(s), retrieval_method="dense")
            for s, i in scored
        ]

    def _search_numpy(self, query_vector: list[float], k: int) -> list[tuple[float, int]]:
        if self._matrix is None:
            self._matrix = _np.asarray(self._vectors, dtype="float32")
        q = _np.asarray(query_vector, dtype="float32")
        mat = self._matrix
        denom = (_np.linalg.norm(mat, axis=1) * (_np.linalg.norm(q) or 1.0))
        denom[denom == 0] = 1.0
        sims = (mat @ q) / denom
        top = _np.argsort(-sims)[:k]
        return [(float(sims[i]), int(i)) for i in top]


def build_vector_store(
    cfg: VectorStoreCfg, directory: str | Path, index_name: str
) -> VectorStore:
    """Construct the vector store for the configured backend.

    All backend names map to the JSON-backed :class:`VectorStore`, which is the
    dependency-free path that always runs. The requested backend is logged so a
    faiss/chroma index can replace it later without touching callers.
    """
    if cfg.backend not in {"faiss", "chroma", "memory"}:
        log.warning("Unknown vector backend '%s'; using the built-in store.", cfg.backend)
    else:
        log.info("Vector store backend '%s' -> built-in JSON store.", cfg.backend)
    return VectorStore(directory, index_name, metric=cfg.metric)
