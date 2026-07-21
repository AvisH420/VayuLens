"""End-to-end RAG pipeline: ingestion, indexing, and grounded generation.

This is the single orchestration object the decision layer and API consume.
It enforces grounding (Step 7): every answer carries citations, confidence,
retrieved sources, and page numbers; below-threshold confidence triggers a
refusal instead of a hallucinated answer.
"""
from __future__ import annotations

import re
from pathlib import Path

from rag.chunking import chunk_document
from rag.config import Settings, get_settings
from rag.embeddings import build_embedding_provider
from rag.llm import INSUFFICIENT, build_llm
from rag.logging_utils import get_logger
from rag.parser import parse_directory, parse_document
from rag.prompts import (
    citizen_advisory_prompt,
    legal_reasoning_prompt,
    qa_prompt,
    recommendation_prompt,
    summarization_prompt,
)
from rag.reranker import build_reranker
from rag.retriever import build_retriever
from rag.types import Citation, GroundedAnswer, ParsedDocument, ScoredChunk
from rag.vector_store import build_vector_store

log = get_logger(__name__)


class RAGPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.embedder = build_embedding_provider(self.settings.embeddings)
        self.store = build_vector_store(
            self.settings.vector_store,
            self.settings.paths.vector_store_dir,
            self.settings.paths.index_name,
        )
        self.store.load()
        self.retriever = build_retriever(
            self.settings.retriever, self.store, self.embedder
        )
        self.reranker = build_reranker(self.settings.reranker)
        self.llm = build_llm(self.settings.llm)
        log.info(
            "RAGPipeline ready | embed=%s store=%s llm=%s chunks=%d",
            self.settings.embeddings.provider,
            self.settings.vector_store.backend,
            self.settings.llm.provider,
            self.store.count(),
        )

    # ---------------------------- ingestion ----------------------------
    def index_document(self, path: str | Path) -> int:
        doc = parse_document(
            path,
            ocr_enabled=self.settings.parser.ocr_enabled,
            ocr_language=self.settings.parser.ocr_language,
        )
        return self._index_parsed(doc)

    def index_directory(self, directory: str | Path) -> int:
        docs = parse_directory(
            directory,
            ocr_enabled=self.settings.parser.ocr_enabled,
            ocr_language=self.settings.parser.ocr_language,
        )
        total = 0
        for doc in docs:
            total += self._index_parsed(doc, persist=False)
        self.store.persist()
        self.retriever.refresh()
        return total

    def _index_parsed(self, doc: ParsedDocument, persist: bool = True) -> int:
        chunks = chunk_document(doc, self.settings.chunking)
        if not chunks:
            return 0
        vectors = self.embedder.embed([c.text for c in chunks])
        self.store.add(chunks, vectors)
        if persist:
            self.store.persist()
            self.retriever.refresh()
        log.info("Indexed %s -> %d chunks", doc.metadata.source, len(chunks))
        return len(chunks)

    def index_corpus(self, rebuild: bool = True) -> dict[str, int]:
        """Index the regulations + interventions corpora.

        rebuild=True (default) clears the existing index first so re-ingestion
        is idempotent rather than appending duplicates.
        """
        if rebuild:
            self.store.clear()
        results = {}
        for name, path in (
            ("regulations", self.settings.paths.regulations_dir),
            ("interventions", self.settings.paths.interventions_dir),
        ):
            if Path(path).exists():
                docs = parse_directory(
                    path,
                    ocr_enabled=self.settings.parser.ocr_enabled,
                    ocr_language=self.settings.parser.ocr_language,
                )
                total = 0
                for doc in docs:
                    total += self._index_parsed(doc, persist=False)
                results[name] = total
        self.store.persist()
        self.retriever.refresh()
        return results

    # ---------------------------- retrieval ----------------------------
    def retrieve(
        self, query: str, top_k: int | None = None,
        metadata_filter: dict | None = None, rerank: bool = True,
    ) -> list[ScoredChunk]:
        candidates = self.retriever.retrieve(query, top_k=top_k,
                                             metadata_filter=metadata_filter)
        if rerank and self.reranker and candidates:
            candidates = self.reranker.rerank(
                query, candidates, self.settings.reranker.top_n
            )
        return candidates

    # ---------------------------- grounding ----------------------------
    @staticmethod
    def _confidence(chunks: list[ScoredChunk]) -> float:
        """Confidence from the strongest grounding evidence.

        Blends the best hit with the mean of the top-3 (the chunks that
        actually ground the answer), so a long tail of weak retrievals does not
        artificially depress confidence.
        """
        if not chunks:
            return 0.0
        scores = [max(0.0, min(1.0, c.score)) for c in chunks]
        top = scores[0]
        head = scores[:3]
        avg_head = sum(head) / len(head)
        return round(0.7 * top + 0.3 * avg_head, 4)

    @staticmethod
    def _build_citations(chunks: list[ScoredChunk]) -> list[Citation]:
        cites = []
        for sc in chunks:
            c = sc.chunk
            snippet = c.text.strip().replace("\n", " ")
            cites.append(
                Citation(
                    doc_id=c.doc_id, source=c.source, title=c.title,
                    doc_type=c.doc_type, page=c.page, section=c.section,
                    snippet=snippet[:280], score=round(sc.score, 4),
                )
            )
        return cites

    def _ground(
        self, question: str, chunks: list[ScoredChunk],
        system: str, user: str, task: str,
    ) -> GroundedAnswer:
        g = self.settings.grounding
        confidence = self._confidence(chunks)
        citations = self._build_citations(chunks)
        sources = list(dict.fromkeys(c.source for c in citations))

        if (
            not chunks
            or len(chunks) < g.min_sources
            or confidence < g.confidence_threshold
        ):
            return GroundedAnswer(
                answer=g.refuse_message, confidence=confidence, grounded=False,
                citations=citations, retrieved_sources=sources, refused=True,
                reasoning=(
                    f"Confidence {confidence:.2f} < threshold "
                    f"{g.confidence_threshold:.2f}; refusing per grounding policy."
                ),
            )

        raw = self.llm.generate(system, user)
        if INSUFFICIENT in raw or not raw.strip():
            return GroundedAnswer(
                answer=g.refuse_message, confidence=confidence, grounded=False,
                citations=citations, retrieved_sources=sources, refused=True,
                reasoning="Model reported insufficient context.",
            )

        cited_idx = {int(n) for n in re.findall(r"\[(\d+)\]", raw)}
        used = [citations[i - 1] for i in sorted(cited_idx)
                if 1 <= i <= len(citations)] or citations
        return GroundedAnswer(
            answer=raw.strip(), confidence=confidence, grounded=True,
            citations=used, retrieved_sources=sources, refused=False,
            reasoning=f"Grounded via {task} over {len(chunks)} reranked sources.",
        )

    # ---------------------------- public tasks ----------------------------
    def ask(self, question: str, top_k: int | None = None,
            metadata_filter: dict | None = None) -> GroundedAnswer:
        chunks = self.retrieve(question, top_k=top_k, metadata_filter=metadata_filter)
        system, user = qa_prompt(question, chunks)
        return self._ground(question, chunks, system, user, "qa")

    def recommend(self, situation: str, top_k: int | None = None) -> GroundedAnswer:
        chunks = self.retrieve(situation, top_k=top_k)
        system, user = recommendation_prompt(situation, chunks)
        return self._ground(situation, chunks, system, user, "recommendation")

    def summarize(self, topic: str, top_k: int | None = None) -> GroundedAnswer:
        chunks = self.retrieve(topic, top_k=top_k)
        system, user = summarization_prompt(topic, chunks)
        return self._ground(topic, chunks, system, user, "summarization")

    def legal_reason(self, query: str, top_k: int | None = None) -> GroundedAnswer:
        chunks = self.retrieve(query, top_k=top_k)
        system, user = legal_reasoning_prompt(query, chunks)
        return self._ground(query, chunks, system, user, "legal_reasoning")

    def advisory(self, situation: str, audience: str, language: str,
                 top_k: int | None = None) -> GroundedAnswer:
        chunks = self.retrieve(situation, top_k=top_k)
        system, user = citizen_advisory_prompt(situation, audience, language, chunks)
        return self._ground(situation, chunks, system, user, "advisory")


_PIPELINE: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = RAGPipeline()
    return _PIPELINE
