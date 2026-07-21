"""Smart chunking strategies.

Every strategy consumes a ParsedDocument and yields citable Chunks that
preserve document, page, section, title, and metadata. The active strategy is
selected via config (``chunking.strategy``).
"""
from __future__ import annotations

import re
import uuid
from typing import Callable

from rag.config import ChunkingCfg
from rag.types import Chunk, ParsedDocument, ParsedElement

_SENTENCE_RE = re.compile(r"(?<=[.!?।])\s+(?=[A-Z0-9ऀ-෿])")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _make_chunk(text: str, doc: ParsedDocument, el: ParsedElement,
                idx: int) -> Chunk:
    m = doc.metadata
    return Chunk(
        chunk_id=f"{m.doc_id}:{idx}:{uuid.uuid4().hex[:8]}",
        text=text.strip(),
        doc_id=m.doc_id,
        source=m.source,
        title=m.title,
        doc_type=m.doc_type,
        page=el.page,
        section=el.section,
        metadata={"year": m.year, "jurisdiction": m.jurisdiction, **m.extra},
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
def sentence_chunking(doc: ParsedDocument, cfg: ChunkingCfg) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    for el in doc.elements:
        if el.element_type == "heading":
            continue
        buf: list[str] = []
        size = 0
        for sent in _split_sentences(el.text):
            buf.append(sent)
            size += len(sent)
            if size >= cfg.chunk_size:
                chunks.append(_make_chunk(" ".join(buf), doc, el, idx))
                idx += 1
                buf, size = [], 0
        if buf and size >= cfg.min_chunk_size:
            chunks.append(_make_chunk(" ".join(buf), doc, el, idx))
            idx += 1
    return chunks


def sliding_window_chunking(doc: ParsedDocument, cfg: ChunkingCfg) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    step = max(1, cfg.chunk_size - cfg.chunk_overlap)
    for el in doc.elements:
        if el.element_type == "heading":
            continue
        text = el.text
        for start in range(0, max(1, len(text)), step):
            window = text[start : start + cfg.chunk_size]
            if len(window) >= cfg.min_chunk_size:
                chunks.append(_make_chunk(window, doc, el, idx))
                idx += 1
            if start + cfg.chunk_size >= len(text):
                break
    return chunks


def heading_aware_chunking(doc: ParsedDocument, cfg: ChunkingCfg) -> list[Chunk]:
    """Group content under its nearest heading, then size-limit each group."""
    chunks: list[Chunk] = []
    idx = 0
    buffer: list[str] = []
    anchor: ParsedElement | None = None

    def flush() -> None:
        nonlocal idx, buffer, anchor
        if not buffer or anchor is None:
            buffer = []
            return
        joined = "\n".join(buffer)
        for piece in _size_split(joined, cfg):
            if len(piece) >= cfg.min_chunk_size:
                chunks.append(_make_chunk(piece, doc, anchor, idx))
                idx += 1
        buffer = []

    for el in doc.elements:
        if el.element_type == "heading":
            flush()
            anchor = el
            buffer = []
        else:
            if anchor is None:
                anchor = el
            buffer.append(el.text)
    flush()
    return chunks


def recursive_chunking(doc: ParsedDocument, cfg: ChunkingCfg) -> list[Chunk]:
    """LangChain-style recursive split on decreasing separators."""
    separators = ["\n\n", "\n", ". ", " "]
    chunks: list[Chunk] = []
    idx = 0
    for el in doc.elements:
        if el.element_type == "heading":
            continue
        for piece in _recursive_split(el.text, separators, cfg):
            if len(piece) >= cfg.min_chunk_size:
                chunks.append(_make_chunk(piece, doc, el, idx))
                idx += 1
    return chunks


def semantic_chunking(doc: ParsedDocument, cfg: ChunkingCfg) -> list[Chunk]:
    """Greedy semantic grouping by sentence-lexical similarity.

    Uses Jaccard token overlap as a dependency-free proxy for semantic
    proximity: consecutive sentences are merged while overlap stays high and
    the chunk stays under the size limit.
    """
    chunks: list[Chunk] = []
    idx = 0
    for el in doc.elements:
        if el.element_type == "heading":
            continue
        sents = _split_sentences(el.text)
        if not sents:
            continue
        current = [sents[0]]
        cur_tokens = _tokens(sents[0])
        for sent in sents[1:]:
            tok = _tokens(sent)
            overlap = _jaccard(cur_tokens, tok)
            joined_len = sum(len(s) for s in current) + len(sent)
            if overlap >= 0.12 and joined_len <= cfg.chunk_size:
                current.append(sent)
                cur_tokens |= tok
            else:
                chunks.append(_make_chunk(" ".join(current), doc, el, idx))
                idx += 1
                current = [sent]
                cur_tokens = tok
        if current:
            chunks.append(_make_chunk(" ".join(current), doc, el, idx))
            idx += 1
    return chunks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _size_split(text: str, cfg: ChunkingCfg) -> list[str]:
    if len(text) <= cfg.chunk_size:
        return [text]
    return _recursive_split(text, ["\n\n", "\n", ". ", " "], cfg)


def _recursive_split(text: str, separators: list[str], cfg: ChunkingCfg) -> list[str]:
    if len(text) <= cfg.chunk_size:
        return [text] if text.strip() else []
    if not separators:
        # hard split with overlap
        step = max(1, cfg.chunk_size - cfg.chunk_overlap)
        return [text[i : i + cfg.chunk_size] for i in range(0, len(text), step)]
    sep, *rest = separators
    parts = text.split(sep)
    out: list[str] = []
    buf = ""
    for part in parts:
        candidate = f"{buf}{sep}{part}" if buf else part
        if len(candidate) <= cfg.chunk_size:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            if len(part) > cfg.chunk_size:
                out.extend(_recursive_split(part, rest, cfg))
                buf = ""
            else:
                buf = part
    if buf:
        out.append(buf)
    return [o for o in out if o.strip()]


_STRATEGIES: dict[str, Callable[[ParsedDocument, ChunkingCfg], list[Chunk]]] = {
    "sentence": sentence_chunking,
    "semantic": semantic_chunking,
    "heading": heading_aware_chunking,
    "sliding": sliding_window_chunking,
    "recursive": recursive_chunking,
}


def get_chunker(name: str) -> Callable[[ParsedDocument, ChunkingCfg], list[Chunk]]:
    if name not in _STRATEGIES:
        raise ValueError(
            f"Unknown chunking strategy '{name}'. "
            f"Available: {sorted(_STRATEGIES)}"
        )
    return _STRATEGIES[name]


def chunk_document(doc: ParsedDocument, cfg: ChunkingCfg) -> list[Chunk]:
    return get_chunker(cfg.strategy)(doc, cfg)
