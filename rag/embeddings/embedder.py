"""Embedding providers with a swappable adapter interface.

Production path: sentence-transformers (BGE/E5). If unavailable, a deterministic
hashing embedder provides a real, functioning vector space so the whole
pipeline (chunking → indexing → retrieval → rerank) runs and is testable
without heavy ML dependencies.
"""
from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

from rag.config import EmbeddingsCfg
from rag.logging_utils import get_logger

log = get_logger(__name__)


class EmbeddingProvider(ABC):
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


class SentenceTransformerEmbeddings(EmbeddingProvider):
    def __init__(self, cfg: EmbeddingsCfg):
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(cfg.model)
        self.dimension = self._model.get_sentence_embedding_dimension()
        self._normalize = cfg.normalize
        self._batch = cfg.batch_size
        log.info("Loaded SentenceTransformer %s (dim=%d)", cfg.model, self.dimension)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=self._batch,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


class HashingEmbeddings(EmbeddingProvider):
    """Deterministic n-gram hashing embedder — real vectors, zero heavy deps.

    Maps token and char-trigram features into a fixed-dimension space via
    feature hashing with signed buckets (the classic hashing trick). Cosine
    similarity is meaningful, enabling genuine dense retrieval offline.
    """

    def __init__(self, dimension: int, normalize: bool = True):
        self.dimension = dimension
        self._normalize = normalize
        log.warning(
            "Using HashingEmbeddings fallback (dim=%d). Install the 'embeddings' "
            "extra for transformer-quality vectors.",
            dimension,
        )

    def _features(self, text: str) -> list[str]:
        text = text.lower()
        tokens = re.findall(r"\w+", text)
        feats = list(tokens)
        for tok in tokens:
            padded = f"#{tok}#"
            feats.extend(padded[i : i + 3] for i in range(len(padded) - 2))
        return feats

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dimension
            for feat in self._features(text):
                h = int(hashlib.md5(feat.encode()).hexdigest(), 16)
                idx = h % self.dimension
                sign = 1.0 if (h >> 1) & 1 else -1.0
                vec[idx] += sign
            out.append(_normalize(vec) if self._normalize else vec)
        return out


def build_embedding_provider(cfg: EmbeddingsCfg) -> EmbeddingProvider:
    if cfg.provider == "sentence_transformers":
        try:
            return SentenceTransformerEmbeddings(cfg)
        except ImportError:
            log.warning(
                "sentence-transformers not installed; falling back to hashing."
            )
            return HashingEmbeddings(cfg.fallback_dimension, cfg.normalize)
    if cfg.provider == "hash":
        return HashingEmbeddings(cfg.dimension, cfg.normalize)
    raise ValueError(f"Unknown embeddings provider: {cfg.provider}")
