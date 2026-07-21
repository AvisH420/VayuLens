"""Unit tests for the RAG building blocks."""
from __future__ import annotations

from rag.chunking import chunk_document
from rag.config import get_settings
from rag.embeddings import HashingEmbeddings
from rag.parser import parse_document
from rag.retriever.hybrid import BM25Index
from rag.text_utils import content_tokens
from rag.types import Chunk, DocumentMetadata, ParsedDocument, ParsedElement


def _doc() -> ParsedDocument:
    return ParsedDocument(
        metadata=DocumentMetadata(source="s.md", doc_id="d1", title="T", doc_type="GRAP"),
        elements=[
            ParsedElement(text="Construction is banned under Stage III when AQI "
                          "exceeds 400. This includes excavation.", section="S3", page=3),
            ParsedElement(text="Industries on unapproved fuel must close.",
                          section="S4", page=4),
        ],
    )


def test_chunkers_preserve_metadata():
    cfg = get_settings().chunking
    for strategy in ("sentence", "semantic", "heading", "sliding", "recursive"):
        cfg2 = cfg.model_copy(update={"strategy": strategy, "min_chunk_size": 10})
        chunks = chunk_document(_doc(), cfg2)
        assert chunks, f"{strategy} produced no chunks"
        for c in chunks:
            assert c.doc_id == "d1"
            assert c.source == "s.md"
            assert c.page in (3, 4)


def test_hashing_embeddings_are_deterministic_and_normalized():
    emb = HashingEmbeddings(dimension=128, normalize=True)
    v1 = emb.embed_query("construction ban")
    v2 = emb.embed_query("construction ban")
    assert v1 == v2
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_hashing_embeddings_similarity_orders_correctly():
    emb = HashingEmbeddings(dimension=256, normalize=True)
    from rag.vector_store.store import _cosine

    q = emb.embed_query("construction demolition ban")
    near = emb.embed_query("construction and demolition are banned")
    far = emb.embed_query("hospitals stock oxygen and nebulisers")
    assert _cosine(q, near) > _cosine(q, far)


def test_bm25_ranks_lexical_match_first():
    chunks = [
        Chunk(chunk_id="1", text="Industries on unapproved fuel must close.",
              doc_id="d", source="s"),
        Chunk(chunk_id="2", text="Construction and demolition dust control.",
              doc_id="d", source="s"),
    ]
    idx = BM25Index(chunks)
    res = idx.search("construction demolition", top_k=2)
    assert res[0].chunk.chunk_id == "2"


def test_content_tokens_removes_stopwords():
    toks = content_tokens("the air quality is very poor and hazardous")
    assert "the" not in toks and "is" not in toks
    assert "hazardous" in toks and "quality" in toks


def test_parser_markdown_headings(tmp_path):
    p = tmp_path / "GRAP_test.md"
    p.write_text("# Heading One\n\nBody paragraph about construction.\n", encoding="utf-8")
    doc = parse_document(p)
    assert doc.metadata.doc_type == "GRAP"
    assert any(e.element_type == "heading" for e in doc.elements)
