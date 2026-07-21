"""CrossEncoder reranking with a lexical fallback.

Production path: sentence-transformers CrossEncoder (bge-reranker / ms-marco).
Fallback: a real lexical relevance reranker (token overlap + coverage) that
reorders candidates meaningfully without heavy deps.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from rag.config import RerankerCfg
from rag.logging_utils import get_logger
from rag.text_utils import content_tokens
from rag.types import ScoredChunk

log = get_logger(__name__)


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: list[ScoredChunk],
               top_n: int) -> list[ScoredChunk]: ...


class CrossEncoderReranker(Reranker):
    def __init__(self, cfg: RerankerCfg):
        from sentence_transformers import CrossEncoder  # type: ignore

        self._model = CrossEncoder(cfg.model)
        log.info("Loaded CrossEncoder reranker %s", cfg.model)

    def rerank(self, query: str, candidates: list[ScoredChunk],
               top_n: int) -> list[ScoredChunk]:
        if not candidates:
            return []
        pairs = [(query, c.chunk.text) for c in candidates]
        scores = self._model.predict(pairs)
        reranked = [
            ScoredChunk(chunk=c.chunk, score=float(s), retrieval_method="rerank")
            for c, s in zip(candidates, scores)
        ]
        reranked.sort(key=lambda s: s.score, reverse=True)
        return reranked[:top_n]


class LexicalReranker(Reranker):
    """Query-term coverage + density reranker (dependency-free)."""

    def rerank(self, query: str, candidates: list[ScoredChunk],
               top_n: int) -> list[ScoredChunk]:
        q_terms = content_tokens(query)
        if not q_terms:
            return candidates[:top_n]
        rescored: list[ScoredChunk] = []
        for c in candidates:
            terms = content_tokens(c.chunk.text)
            if not terms:
                rescored.append(
                    ScoredChunk(chunk=c.chunk, score=0.0, retrieval_method="rerank")
                )
                continue
            present = q_terms & terms
            coverage = len(present) / len(q_terms)
            density = len(present) / len(terms)
            # blend prior retrieval score with lexical relevance
            score = 0.6 * coverage + 0.25 * density + 0.15 * min(c.score, 1.0)
            rescored.append(
                ScoredChunk(chunk=c.chunk, score=score, retrieval_method="rerank")
            )
        rescored.sort(key=lambda s: s.score, reverse=True)
        return rescored[:top_n]


def build_reranker(cfg: RerankerCfg) -> Reranker | None:
    if not cfg.enabled:
        return None
    if cfg.provider == "cross_encoder":
        try:
            return CrossEncoderReranker(cfg)
        except ImportError:
            log.warning("sentence-transformers not installed; lexical reranker.")
            return LexicalReranker()
    if cfg.provider == "lexical":
        return LexicalReranker()
    raise ValueError(f"Unknown reranker provider: {cfg.provider}")
