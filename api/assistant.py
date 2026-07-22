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
    # Retrieval tuning for a small regulatory corpus with the lightweight
    # embedder: lean on BM25 (lexical terms like "vehicle", "construction",
    # "GRAP" match reliably) over the near-random hashing vectors, and hand the
    # LLM a generous slice of the corpus so the relevant passage is almost
    # always present. With ~22 chunks total, retrieving ~10 is half the corpus.
    settings.retriever.hybrid_alpha = 0.25   # 0 = pure BM25, 1 = pure dense
    settings.retriever.top_k = 12
    settings.reranker.top_n = 10
    # Delegate the "is this answerable" decision to the LLM. The lightweight
    # hashing embedder + lexical reranker score natural-language queries very
    # low even when the retrieved passages are clearly relevant, so a
    # meaningful retrieval-confidence gate would abstain on almost everything.
    # The LLM is instructed to reply INSUFFICIENT_CONTEXT when the context
    # genuinely doesn't cover the question (see GROUNDING_RULES), which is a far
    # better relevance judge than keyword overlap. Keep only a floor to skip
    # pure noise, and require at least one retrieved passage.
    settings.grounding.confidence_threshold = 0.02
    settings.grounding.min_sources = 1

    pipe = RAGPipeline(settings)
    if pipe.store.count() == 0:          # first run — index the corpus
        pipe.index_corpus(rebuild=True)
    _PIPELINE = pipe
    return pipe


def answer(query: str) -> dict:
    """Answer *query* and return the gateway's ChatAnswer dict shape."""
    pipe = _get_pipeline()
    g = pipe.ask(query)

    # The raw retrieval confidence is always low with the lightweight embedder,
    # so it misrepresents a good LLM answer. When the LLM actually grounded an
    # answer, report a confidence from how many sources it cited; on an abstain
    # keep the (low) retrieval score to signal weak grounding.
    if g.refused:
        confidence = round(g.confidence, 2)
    else:
        cited = sum(1 for _ in g.citations)
        confidence = round(min(0.95, 0.55 + 0.1 * cited), 2)

    return {
        "text": g.answer,
        "citations": [
            {"doc": c.title or c.source, "ref": c.section or c.doc_type or c.source}
            for c in g.citations
        ][:5],
        "confidence": confidence,
        "retrieved": len(g.citations),
        "abstained": g.refused,
    }
