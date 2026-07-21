"""Role 3 — RAG pipeline stubs.

Ingests regulatory / policy / scientific documents, indexes them in a vector
store, retrieves relevant passages, and produces grounded, cited generations.
Includes an eval harness for faithfulness/grounding.

All functions are stubs that raise NotImplementedError.
"""

from __future__ import annotations

from typing import Any


def ingest_documents(paths: list[str]) -> int:
    """Load, chunk, and embed documents into the vector store.

    Args:
        paths: File or directory paths to ingest (regulations, SOPs, reports).

    Returns:
        Number of chunks indexed.
    """
    raise NotImplementedError


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Retrieve the most relevant chunks for a query from the vector store.

    Args:
        query: Natural-language query.
        top_k: Number of chunks to return.

    Returns:
        Ranked chunks, each with text + source metadata for citation.
    """
    raise NotImplementedError


def generate_grounded(query: str, context_chunks: list[dict]) -> dict[str, Any]:
    """Generate an answer grounded in retrieved context, with citations.

    Args:
        query: The user's question.
        context_chunks: Chunks from `retrieve` to ground the answer in.

    Returns:
        {"answer": str, "citations": list[dict]} — answer plus the sources used.
    """
    raise NotImplementedError


def evaluate(dataset: list[dict]) -> dict[str, float]:
    """Run the RAG eval harness (faithfulness, groundedness, retrieval hit-rate).

    Args:
        dataset: Labelled examples of (query, expected sources/answer).

    Returns:
        Metric name -> score.
    """
    raise NotImplementedError
