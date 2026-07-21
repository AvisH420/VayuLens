"""Typed configuration models and loader for VayuLens.

All modules consume a single `Settings` instance. Values come from YAML,
overridable by environment variables (prefix ``VAYULENS__`` with ``__`` nesting).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = os.getenv("VAYULENS_CONFIG", "config/config.yaml")


class AppCfg(BaseModel):
    name: str = "VayuLens Decision Intelligence"
    version: str = "1.0.0"
    log_level: str = "INFO"


class PathsCfg(BaseModel):
    data_dir: str = "data"
    regulations_dir: str = "data/regulations"
    interventions_dir: str = "data/interventions"
    vector_store_dir: str = "storage/vectors"
    index_name: str = "vayulens"


class ParserCfg(BaseModel):
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    extract_tables: bool = True


class ChunkingCfg(BaseModel):
    strategy: str = "recursive"
    chunk_size: int = 800
    chunk_overlap: int = 120
    min_chunk_size: int = 80


class EmbeddingsCfg(BaseModel):
    provider: str = "sentence_transformers"
    model: str = "BAAI/bge-small-en-v1.5"
    dimension: int = 384
    normalize: bool = True
    batch_size: int = 32
    fallback_dimension: int = 384


class VectorStoreCfg(BaseModel):
    backend: str = "faiss"
    metric: str = "cosine"


class RetrieverCfg(BaseModel):
    mode: str = "hybrid"
    top_k: int = 8
    fetch_k: int = 30
    hybrid_alpha: float = 0.5
    use_mmr: bool = True
    mmr_lambda: float = 0.6


class RerankerCfg(BaseModel):
    enabled: bool = True
    provider: str = "cross_encoder"
    model: str = "BAAI/bge-reranker-base"
    top_n: int = 5


class GroundingCfg(BaseModel):
    confidence_threshold: float = 0.35
    refuse_message: str = "I cannot answer this reliably from the available corpus."
    min_sources: int = 1


class LLMCfg(BaseModel):
    provider: str = "extractive"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 900
    ollama_base_url: str = "http://localhost:11434"


class DecisionCfg(BaseModel):
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "pollution_contribution": 0.35,
            "population": 0.20,
            "hospitals": 0.15,
            "schools": 0.15,
            "forecast_trend": 0.10,
            "legal_urgency": 0.05,
        }
    )


class AdvisoryCfg(BaseModel):
    default_language: str = "en"
    supported_languages: list[str] = Field(
        default_factory=lambda: ["en", "hi", "mr", "ta", "bn", "te"]
    )
    audiences: list[str] = Field(
        default_factory=lambda: [
            "citizen",
            "hospital",
            "school",
            "outdoor_worker",
            "senior_citizen",
        ]
    )


class EvaluationCfg(BaseModel):
    k_values: list[int] = Field(default_factory=lambda: [1, 3, 5, 10])


class Settings(BaseModel):
    app: AppCfg = Field(default_factory=AppCfg)
    paths: PathsCfg = Field(default_factory=PathsCfg)
    parser: ParserCfg = Field(default_factory=ParserCfg)
    chunking: ChunkingCfg = Field(default_factory=ChunkingCfg)
    embeddings: EmbeddingsCfg = Field(default_factory=EmbeddingsCfg)
    vector_store: VectorStoreCfg = Field(default_factory=VectorStoreCfg)
    retriever: RetrieverCfg = Field(default_factory=RetrieverCfg)
    reranker: RerankerCfg = Field(default_factory=RerankerCfg)
    grounding: GroundingCfg = Field(default_factory=GroundingCfg)
    llm: LLMCfg = Field(default_factory=LLMCfg)
    decision: DecisionCfg = Field(default_factory=DecisionCfg)
    advisory: AdvisoryCfg = Field(default_factory=AdvisoryCfg)
    evaluation: EvaluationCfg = Field(default_factory=EvaluationCfg)

    def ensure_dirs(self) -> None:
        for p in (
            self.paths.data_dir,
            self.paths.regulations_dir,
            self.paths.interventions_dir,
            self.paths.vector_store_dir,
        ):
            Path(p).mkdir(parents=True, exist_ok=True)


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Override nested keys via VAYULENS__section__key=value env vars."""
    prefix = "VAYULENS__"
    for key, val in os.environ.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix):].lower().split("__")
        node = data
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = yaml.safe_load(val)
    return data


def load_settings(path: str | None = None) -> Settings:
    cfg_path = Path(path or DEFAULT_CONFIG_PATH)
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    raw = _apply_env_overrides(raw)
    return Settings(**raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
