"""Tests for the grounded RAG pipeline: citations, confidence, refusal."""
from __future__ import annotations


def test_ask_returns_grounded_answer_with_citations(pipeline):
    ans = pipeline.ask("What happens to construction under GRAP Stage III?")
    assert ans.grounded is True
    assert ans.refused is False
    assert ans.citations, "grounded answer must carry citations"
    # citations must carry provenance for the dashboard
    c = ans.citations[0]
    assert c.source and c.doc_type
    assert any("GRAP" in (ci.doc_type or "") for ci in ans.citations)


def test_offtopic_query_is_refused(pipeline):
    ans = pipeline.ask("What is the capital of France and its GDP?")
    assert ans.refused is True
    assert ans.grounded is False
    assert ans.confidence < pipeline.settings.grounding.confidence_threshold


def test_retrieve_returns_scored_chunks(pipeline):
    chunks = pipeline.retrieve("industrial closure unapproved fuel", top_k=3)
    assert chunks
    assert chunks == sorted(chunks, key=lambda c: c.score, reverse=True)
    assert all(c.chunk.source for c in chunks)


def test_metadata_filter_restricts_doc_type(pipeline):
    chunks = pipeline.retrieve(
        "construction dust", top_k=5, metadata_filter={"doc_type": "GRAP"}
    )
    assert chunks
    assert all(c.chunk.doc_type == "GRAP" for c in chunks)


def test_answer_never_exceeds_confidence_one(pipeline):
    ans = pipeline.ask("GRAP Stage IV truck ban")
    assert 0.0 <= ans.confidence <= 1.0
