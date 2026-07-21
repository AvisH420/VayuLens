"""Shared lightweight text utilities (dependency-free)."""
from __future__ import annotations

import re

STOPWORDS: frozenset[str] = frozenset(
    """a an the and or but if then else of to in on at by for with without within
    is are was were be been being do does did done has have had having this that
    these those it its as from into out up down over under again further can could
    should would may might must will shall not no nor what which who whom whose when
    where why how all any both each few more most other some such only own same so
    than too very just about above below between during before after our your their
    them they we you i he she his her him me my mine ours yours theirs""".split()
)


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def content_tokens(text: str) -> set[str]:
    """Tokens with stopwords and pure numbers-as-noise removed."""
    return {t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1}


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]
