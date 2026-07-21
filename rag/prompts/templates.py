"""Prompt templates for all task types.

Templates are plain string builders (no framework lock-in). Each returns a
system+user message pair. Grounding rules are baked into the system prompts so
every provider enforces citation and refusal behavior.
"""
from __future__ import annotations

from rag.types import ScoredChunk

GROUNDING_RULES = (
    "You are VayuLens, an air-quality regulatory intelligence assistant for India.\n"
    "Rules you MUST follow:\n"
    "1. Answer ONLY from the provided CONTEXT. Never use outside knowledge.\n"
    "2. Cite every claim inline using [n] referring to the numbered sources.\n"
    "3. If the context is insufficient, reply exactly with: INSUFFICIENT_CONTEXT.\n"
    "4. Be precise, quote regulation names, stages, sections and thresholds.\n"
    "5. Never invent document names, section numbers, or figures.\n"
)


def format_context(chunks: list[ScoredChunk]) -> str:
    lines = []
    for i, sc in enumerate(chunks, start=1):
        c = sc.chunk
        loc = []
        if c.doc_type:
            loc.append(c.doc_type)
        if c.section:
            loc.append(f"§{c.section}")
        if c.page is not None:
            loc.append(f"p.{c.page}")
        header = f"[{i}] {c.source}" + (f" ({', '.join(loc)})" if loc else "")
        lines.append(f"{header}\n{c.text}")
    return "\n\n".join(lines)


def qa_prompt(question: str, chunks: list[ScoredChunk]) -> tuple[str, str]:
    context = format_context(chunks)
    user = (
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "Provide a grounded answer with inline [n] citations."
    )
    return GROUNDING_RULES, user


def recommendation_prompt(situation: str, chunks: list[ScoredChunk]) -> tuple[str, str]:
    system = GROUNDING_RULES + (
        "\nYou produce enforcement recommendations. For each action give: the "
        "action, the legal basis (cite [n]), and the expected impact."
    )
    context = format_context(chunks)
    user = (
        f"REGULATORY CONTEXT:\n{context}\n\n"
        f"SITUATION:\n{situation}\n\n"
        "Recommend specific, legally-grounded actions with citations."
    )
    return system, user


def summarization_prompt(topic: str, chunks: list[ScoredChunk]) -> tuple[str, str]:
    system = GROUNDING_RULES + "\nSummarize faithfully; preserve all citations."
    context = format_context(chunks)
    user = f"CONTEXT:\n{context}\n\nSummarize the regulations relevant to: {topic}"
    return system, user


def legal_reasoning_prompt(query: str, chunks: list[ScoredChunk]) -> tuple[str, str]:
    system = GROUNDING_RULES + (
        "\nYou are a legal reasoning engine. Structure the answer as: Issue, "
        "Rule (cite [n]), Application, Conclusion (IRAC)."
    )
    context = format_context(chunks)
    user = f"LEGAL SOURCES:\n{context}\n\nLEGAL QUESTION: {query}"
    return system, user


def citizen_advisory_prompt(
    situation: str, audience: str, language: str, chunks: list[ScoredChunk]
) -> tuple[str, str]:
    system = (
        "You are VayuLens public advisory generator. Produce clear, actionable, "
        "non-alarming health advice grounded in the provided guidance. "
        f"Target audience: {audience}. Write in language code: {language}. "
        "Keep it under 120 words. Cite source guidance with [n] where possible."
    )
    context = format_context(chunks)
    user = (
        f"GUIDANCE:\n{context}\n\nSITUATION:\n{situation}\n\n"
        f"Write an advisory for {audience} in language '{language}'."
    )
    return system, user
