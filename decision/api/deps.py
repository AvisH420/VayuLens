"""Dependency wiring for the API — singletons for the pipeline and engines."""
from __future__ import annotations

from functools import lru_cache

from rag.config import get_settings
from rag.evaluation import Evaluator
from rag.pipeline import RAGPipeline

from decision.advisory_engine import AdvisoryEngine
from decision.recommendation_engine import EnforcementPrioritizer, RecommendationEngine


@lru_cache(maxsize=1)
def get_pipeline() -> RAGPipeline:
    return RAGPipeline()


@lru_cache(maxsize=1)
def get_recommendation_engine() -> RecommendationEngine:
    return RecommendationEngine(get_pipeline())


@lru_cache(maxsize=1)
def get_prioritizer() -> EnforcementPrioritizer:
    return EnforcementPrioritizer(get_settings().decision)


@lru_cache(maxsize=1)
def get_advisory_engine() -> AdvisoryEngine:
    return AdvisoryEngine(get_pipeline())


@lru_cache(maxsize=1)
def get_evaluator() -> Evaluator:
    return Evaluator(get_pipeline())
