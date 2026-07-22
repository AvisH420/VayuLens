"""LLM provider adapters.

A single LLMProvider interface with adapters for OpenAI, Claude (Anthropic),
Gemini (Google), and Ollama. Selected by config; API keys read from env.

The default 'extractive' provider requires no API and produces a real,
grounded answer by extracting and stitching the most query-relevant sentences
from the retrieved context. This guarantees the full system runs offline while
never hallucinating (it only ever emits text present in the sources).
"""
from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod

from rag.config import LLMCfg
from rag.logging_utils import get_logger

log = get_logger(__name__)

INSUFFICIENT = "INSUFFICIENT_CONTEXT"


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system: str, user: str, *, temperature: float | None = None,
                 max_tokens: int | None = None) -> str: ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class OpenAIProvider(LLMProvider):
    def __init__(self, cfg: LLMCfg):
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._cfg = cfg

    def generate(self, system, user, *, temperature=None, max_tokens=None) -> str:
        resp = self._client.chat.completions.create(
            model=self._cfg.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=self._cfg.temperature if temperature is None else temperature,
            max_tokens=self._cfg.max_tokens if max_tokens is None else max_tokens,
        )
        return resp.choices[0].message.content or ""


class OpenRouterProvider(LLMProvider):
    """OpenRouter — one OpenAI-compatible endpoint fronting many models.

    Set ``provider="openrouter"`` and a routed model id in config, e.g.
    ``model="anthropic/claude-opus-4-8"`` or ``"openai/gpt-4o-mini"``.
    Key comes from OPEN_ROUTER_API_KEY (matches the project .env).
    """

    def __init__(self, cfg: LLMCfg):
        from openai import OpenAI  # type: ignore

        key = os.getenv("OPEN_ROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self._client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        self._cfg = cfg

    def generate(self, system, user, *, temperature=None, max_tokens=None) -> str:
        resp = self._client.chat.completions.create(
            model=self._cfg.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=self._cfg.temperature if temperature is None else temperature,
            max_tokens=self._cfg.max_tokens if max_tokens is None else max_tokens,
        )
        return resp.choices[0].message.content or ""


class ClaudeProvider(LLMProvider):
    def __init__(self, cfg: LLMCfg):
        import anthropic  # type: ignore

        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self._cfg = cfg

    def generate(self, system, user, *, temperature=None, max_tokens=None) -> str:
        # Current Claude models (Opus 4.8, Sonnet 5, ...) reject `temperature`
        # with a 400 — it was removed from the API. Steer with the prompt
        # instead; do not pass sampling params.
        resp = self._client.messages.create(
            model=self._cfg.model,
            system=system,
            max_tokens=self._cfg.max_tokens if max_tokens is None else max_tokens,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )


class GeminiProvider(LLMProvider):
    def __init__(self, cfg: LLMCfg):
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self._genai = genai
        self._cfg = cfg

    def generate(self, system, user, *, temperature=None, max_tokens=None) -> str:
        model = self._genai.GenerativeModel(
            self._cfg.model, system_instruction=system
        )
        resp = model.generate_content(
            user,
            generation_config={
                "temperature": self._cfg.temperature if temperature is None else temperature,
                "max_output_tokens": self._cfg.max_tokens if max_tokens is None else max_tokens,
            },
        )
        return resp.text or ""


class OllamaProvider(LLMProvider):
    def __init__(self, cfg: LLMCfg):
        self._cfg = cfg

    def generate(self, system, user, *, temperature=None, max_tokens=None) -> str:
        import json
        import urllib.request

        payload = {
            "model": self._cfg.model,
            "prompt": f"{system}\n\n{user}",
            "stream": False,
            "options": {
                "temperature": self._cfg.temperature if temperature is None else temperature,
                "num_predict": self._cfg.max_tokens if max_tokens is None else max_tokens,
            },
        }
        req = urllib.request.Request(
            f"{self._cfg.ollama_base_url}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode()).get("response", "")


class ExtractiveProvider(LLMProvider):
    """No-API grounded generator: extracts the sentences from the provided
    context most relevant to the question. Cannot hallucinate."""

    def generate(self, system, user, *, temperature=None, max_tokens=None) -> str:
        context, question = self._split(user)
        if not context.strip():
            return INSUFFICIENT
        sources = self._parse_sources(context)
        q_terms = set(re.findall(r"\w+", question.lower()))
        scored: list[tuple[float, int, str]] = []
        for idx, text in sources:
            for sent in re.split(r"(?<=[.!?।])\s+", text):
                terms = set(re.findall(r"\w+", sent.lower()))
                if not terms:
                    continue
                overlap = len(q_terms & terms) / (len(q_terms) or 1)
                if overlap > 0:
                    scored.append((overlap, idx, sent.strip()))
        if not scored:
            return INSUFFICIENT
        scored.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        picked: list[tuple[int, str]] = []
        for _, idx, sent in scored:
            key = sent[:60]
            if key in seen:
                continue
            seen.add(key)
            picked.append((idx, sent))
            if len(picked) >= 4:
                break
        picked_sorted = sorted(picked, key=lambda x: x[0])
        return " ".join(f"{sent} [{idx}]" for idx, sent in picked_sorted)

    @staticmethod
    def _split(user: str) -> tuple[str, str]:
        m = re.search(r"(QUESTION|LEGAL QUESTION|SITUATION):\s*(.*)", user, re.S)
        question = m.group(2).strip() if m else user
        context = user.split("QUESTION:")[0]
        for marker in ("SITUATION:", "LEGAL QUESTION:"):
            context = context.split(marker)[0]
        return context, question

    @staticmethod
    def _parse_sources(context: str) -> list[tuple[int, str]]:
        blocks = re.split(r"\n(?=\[\d+\])", context)
        out: list[tuple[int, str]] = []
        for b in blocks:
            m = re.match(r"\[(\d+)\]", b.strip())
            if not m:
                continue
            idx = int(m.group(1))
            body = b.split("\n", 1)[1].strip() if "\n" in b else ""
            out.append((idx, body))
        return out


_REGISTRY = {
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "extractive": ExtractiveProvider,
}


def build_llm(cfg: LLMCfg) -> LLMProvider:
    provider = cfg.provider.lower()
    if provider not in _REGISTRY:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. Available: {sorted(_REGISTRY)}"
        )
    if provider == "extractive":
        return ExtractiveProvider()
    try:
        return _REGISTRY[provider](cfg)
    except ImportError as e:
        # The provider's SDK isn't installed — this is the intended offline
        # fallback (the whole stack still runs on the extractive provider).
        log.warning(
            "LLM provider '%s' package not installed (%s); falling back to extractive.",
            provider, e,
        )
        return ExtractiveProvider()
