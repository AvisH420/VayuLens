"""Hybrid retrieval: dense + BM25 + fusion, metadata filtering, MMR, top-k."""
from __future__ import annotations

import re

from rag.config import RetrieverCfg
from rag.embeddings import EmbeddingProvider
from rag.logging_utils import get_logger
from rag.types import Chunk, ScoredChunk
from rag.vector_store import VectorStore

log = get_logger(__name__)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class BM25Index:
    """Lexical BM25 over the corpus. Uses rank_bm25 if present, else a correct
    built-in Okapi BM25 implementation (identical formula, zero deps)."""

    def __init__(self, chunks: list[Chunk]):
        self._chunks = chunks
        self._corpus = [_tokenize(c.text) for c in chunks]
        self._impl = None
        if not self._corpus:
            self._build_builtin()
            return
        try:
            from rank_bm25 import BM25Okapi  # type: ignore

            self._impl = BM25Okapi(self._corpus)
        except ImportError:
            self._build_builtin()

    def _build_builtin(self) -> None:
        import math
        from collections import Counter

        self._k1, self._b = 1.5, 0.75
        self._doc_len = [len(d) for d in self._corpus]
        self._avgdl = (sum(self._doc_len) / len(self._corpus)) if self._corpus else 0.0
        self._freqs = [Counter(d) for d in self._corpus]
        df: Counter = Counter()
        for d in self._corpus:
            df.update(set(d))
        n = len(self._corpus)
        self._idf = {
            t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()
        }

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        if not self._chunks:
            return []
        tokens = _tokenize(query)
        token_set = set(tokens)
        if self._impl is not None:
            scores = self._impl.get_scores(tokens)
        else:
            scores = self._builtin_scores(tokens)
        ranked = sorted(
            zip(self._chunks, self._corpus, scores),
            key=lambda x: x[2], reverse=True,
        )
        out: list[ScoredChunk] = []
        for chunk, doc_tokens, score in ranked[:top_k]:
            # Keep a hit if it scored positively OR shares a query term.
            # (BM25 Okapi IDF can be ~0 on tiny corpora where a term appears in
            # half the documents; token overlap keeps such matches.)
            if score > 0 or token_set & set(doc_tokens):
                out.append(
                    ScoredChunk(chunk=chunk, score=float(score),
                                retrieval_method="bm25")
                )
        return out

    def _builtin_scores(self, tokens: list[str]) -> list[float]:
        scores = []
        for i, freqs in enumerate(self._freqs):
            dl = self._doc_len[i] or 1
            s = 0.0
            for t in tokens:
                if t not in freqs:
                    continue
                idf = self._idf.get(t, 0.0)
                tf = freqs[t]
                denom = tf + self._k1 * (1 - self._b + self._b * dl / (self._avgdl or 1))
                s += idf * (tf * (self._k1 + 1)) / denom
            scores.append(s)
        return scores


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [1.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _passes_filter(chunk: Chunk, flt: dict | None) -> bool:
    if not flt:
        return True
    for key, val in flt.items():
        actual = getattr(chunk, key, None)
        if actual is None:
            actual = chunk.metadata.get(key)
        if isinstance(val, (list, tuple, set)):
            if actual not in val:
                return False
        elif actual != val:
            return False
    return True


class HybridRetriever:
    def __init__(
        self,
        cfg: RetrieverCfg,
        store: VectorStore,
        embedder: EmbeddingProvider,
    ):
        self.cfg = cfg
        self.store = store
        self.embedder = embedder
        self._bm25 = BM25Index(store.all_chunks())
        self._vec_cache: dict[str, list[float]] = {}

    def refresh(self) -> None:
        self._bm25 = BM25Index(self.store.all_chunks())

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
    ) -> list[ScoredChunk]:
        top_k = top_k or self.cfg.top_k
        fetch_k = max(self.cfg.fetch_k, top_k)
        mode = self.cfg.mode

        dense: list[ScoredChunk] = []
        if mode in {"dense", "hybrid"}:
            qv = self.embedder.embed_query(query)
            dense = self.store.search(qv, fetch_k)

        bm25: list[ScoredChunk] = []
        if mode in {"bm25", "hybrid"}:
            bm25 = self._bm25.search(query, fetch_k)

        fused = self._fuse(dense, bm25, mode)
        fused = [s for s in fused if _passes_filter(s.chunk, metadata_filter)]

        if self.cfg.use_mmr and mode != "bm25":
            fused = self._mmr(query, fused, top_k)
        return fused[:top_k]

    def _fuse(self, dense: list[ScoredChunk], bm25: list[ScoredChunk],
              mode: str) -> list[ScoredChunk]:
        if mode == "dense":
            return dense
        if mode == "bm25":
            return bm25
        alpha = self.cfg.hybrid_alpha
        d_norm = dict(zip([s.chunk.chunk_id for s in dense],
                          _minmax([s.score for s in dense])))
        b_norm = dict(zip([s.chunk.chunk_id for s in bm25],
                          _minmax([s.score for s in bm25])))
        registry: dict[str, ScoredChunk] = {}
        for s in dense + bm25:
            registry.setdefault(s.chunk.chunk_id, s)
        fused: list[ScoredChunk] = []
        for cid, s in registry.items():
            score = alpha * d_norm.get(cid, 0.0) + (1 - alpha) * b_norm.get(cid, 0.0)
            fused.append(
                ScoredChunk(chunk=s.chunk, score=score, retrieval_method="hybrid")
            )
        fused.sort(key=lambda s: s.score, reverse=True)
        return fused

    def _vec(self, chunk: Chunk) -> list[float]:
        if chunk.chunk_id not in self._vec_cache:
            self._vec_cache[chunk.chunk_id] = self.embedder.embed_query(chunk.text)
        return self._vec_cache[chunk.chunk_id]

    def _mmr(self, query: str, candidates: list[ScoredChunk],
             top_k: int) -> list[ScoredChunk]:
        if len(candidates) <= 1:
            return candidates
        from rag.vector_store.store import _cosine

        qv = self.embedder.embed_query(query)
        lam = self.cfg.mmr_lambda
        pool = candidates[: self.cfg.fetch_k]
        selected: list[ScoredChunk] = []
        remaining = list(pool)
        while remaining and len(selected) < top_k:
            best, best_score = None, -1e9
            for cand in remaining:
                relevance = _cosine(qv, self._vec(cand.chunk))
                diversity = max(
                    (_cosine(self._vec(cand.chunk), self._vec(s.chunk))
                     for s in selected),
                    default=0.0,
                )
                mmr = lam * relevance - (1 - lam) * diversity
                if mmr > best_score:
                    best, best_score = cand, mmr
            selected.append(best)
            remaining.remove(best)
        return selected


def build_retriever(
    cfg: RetrieverCfg, store: VectorStore, embedder: EmbeddingProvider
) -> HybridRetriever:
    return HybridRetriever(cfg, store, embedder)
