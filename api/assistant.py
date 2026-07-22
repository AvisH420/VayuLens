"""Real grounded assistant: Role 3 RAG over the regulation corpus + an LLM.

Wires the RAG pipeline (retrieval + grounding) to an OpenRouter-hosted LLM so
``/chat`` answers real questions with citations, instead of demo_engine's
canned responses. Everything is lazy and defensive: the module imports without
the RAG stack present, builds the pipeline on first use, and any failure falls
back to a graceful message rather than a 500.

Activation: env ``REAL_ASSISTANT=true``. The LLM model is ``ASSISTANT_MODEL``
(an OpenRouter model id, default ``anthropic/claude-3.5-sonnet``); the key is
``OPEN_ROUTER_API_KEY`` (loaded from .env via ingestion.config). When the key is
absent the RAG layer degrades to the offline extractive generator — still
grounded, just no LLM prose.
"""
from __future__ import annotations

import os
from pathlib import Path

_PIPELINE = None
_ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    """Load repo-root .env into os.environ (no-op if absent, e.g. on Render).

    Kept lightweight and self-contained so importing this module never pulls in
    the heavy ingestion package (apscheduler/pandas) that the API deploy omits.
    On the server the keys come from real env vars and this simply finds none.
    """
    path = _ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_env()


def enabled() -> bool:
    return os.getenv("REAL_ASSISTANT", "").lower() in {"1", "true", "yes", "on"}


def _get_pipeline():
    """Build the RAG pipeline once (index the corpus on first call)."""
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    from rag.config import Settings
    from rag.pipeline import RAGPipeline

    provider = "openrouter" if os.getenv("OPEN_ROUTER_API_KEY") else "extractive"
    settings = Settings()
    settings.llm.provider = provider
    # OpenRouter model id. Haiku 4.5 is fast + cheap and plenty for grounded
    # regulatory QA; override with ASSISTANT_MODEL (e.g. anthropic/claude-sonnet-5).
    settings.llm.model = os.getenv("ASSISTANT_MODEL", "anthropic/claude-haiku-4.5")
    settings.paths.regulations_dir = str(_ROOT / "data" / "regulations")
    settings.paths.interventions_dir = str(_ROOT / "data" / "interventions")
    settings.paths.vector_store_dir = os.getenv(
        "ASSISTANT_INDEX_DIR", str(_ROOT / "storage" / "vectors")
    )
    settings.parser.ocr_enabled = False  # corpus is markdown; no OCR needed
    # The lightweight hashing embedder scores retrieval conservatively; the LLM
    # is itself instructed to answer only from context (else "INSUFFICIENT"),
    # so a lower gate improves recall without inviting hallucination.
    settings.grounding.confidence_threshold = 0.22

    pipe = RAGPipeline(settings)
    if pipe.store.count() == 0:          # first run — index the corpus
        pipe.index_corpus(rebuild=True)
    _PIPELINE = pipe
    return pipe


def answer(query: str) -> dict:
    """Answer *query* and return the gateway's ChatAnswer dict shape."""
    pipe = _get_pipeline()
    g = pipe.ask(query)
    return {
        "text": g.answer,
        "citations": [
            {"doc": c.title or c.source, "ref": c.section or c.doc_type or c.source}
            for c in g.citations
        ][:5],
        "confidence": round(g.confidence, 2),
        "retrieved": len(g.citations),
        "abstained": g.refused,
    }
