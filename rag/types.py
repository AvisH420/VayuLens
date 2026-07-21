"""Core data types shared across the RAG pipeline."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Provenance metadata carried through the whole pipeline for citations."""

    source: str = Field(..., description="Original file name or URI")
    doc_id: str = Field(..., description="Stable document identifier")
    title: str | None = None
    doc_type: str | None = Field(None, description="e.g. GRAP, NCAP, CPCB, Air Act")
    jurisdiction: str | None = None
    year: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ParsedElement(BaseModel):
    """A unit of extracted content (paragraph, heading, or table)."""

    text: str
    element_type: str = "paragraph"  # paragraph | heading | table
    page: int | None = None
    section: str | None = None
    heading_level: int | None = None


class ParsedDocument(BaseModel):
    metadata: DocumentMetadata
    elements: list[ParsedElement] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(e.text for e in self.elements)


class Chunk(BaseModel):
    """A retrievable, citable unit of text."""

    chunk_id: str
    text: str
    doc_id: str
    source: str
    title: str | None = None
    doc_type: str | None = None
    page: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float
    retrieval_method: str = "dense"


class Citation(BaseModel):
    doc_id: str
    source: str
    title: str | None = None
    doc_type: str | None = None
    page: int | None = None
    section: str | None = None
    snippet: str
    score: float


class GroundedAnswer(BaseModel):
    answer: str
    confidence: float
    grounded: bool
    citations: list[Citation] = Field(default_factory=list)
    retrieved_sources: list[str] = Field(default_factory=list)
    refused: bool = False
    reasoning: str | None = None
