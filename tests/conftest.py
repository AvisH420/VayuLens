"""Shared pytest fixtures. Forces the dependency-free providers so tests run
deterministically in any environment (CI included)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Force offline-capable providers before any module imports settings.
os.environ.setdefault("VAYULENS__EMBEDDINGS__PROVIDER", "hash")
os.environ.setdefault("VAYULENS__VECTOR_STORE__BACKEND", "memory")
os.environ.setdefault("VAYULENS__RERANKER__PROVIDER", "lexical")
os.environ.setdefault("VAYULENS__LLM__PROVIDER", "extractive")


@pytest.fixture(scope="session")
def pipeline():
    from rag.config import load_settings
    from rag.pipeline import RAGPipeline

    settings = load_settings()
    tmp = Path(tempfile.mkdtemp())
    settings.paths.vector_store_dir = str(tmp / "vectors")
    settings.paths.index_name = "test_index"
    p = RAGPipeline(settings=settings)
    p.index_corpus()
    return p
